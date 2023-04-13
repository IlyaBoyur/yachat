import asyncio
from asyncio import StreamReader, StreamWriter
import signal
import logging
import sys
import uuid
from dataclasses import dataclass
import json
import pytz
from functools import wraps
from datetime import datetime, date, timedelta

from constants import ChatType, DEFAULT_DEPTH, DEFAULT_MSG_LIMIT, DEFAULT_MSG_LIMIT_PERIOD_HOURS
from db import ChatStorage, DbEncoder, Message, User, Chat
from errors import NotExistError, MsgLimitExceededError


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8001
DEFAULT_LIMIT = 64000


logger = logging.getLogger(__name__)


class Server:
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, limit=DEFAULT_LIMIT, msg_limit_enabled=False):
        self.host = host
        self.port = port
        self.limit = limit
        self.database = ChatStorage()
        self.msg_limit_enabled = msg_limit_enabled

    @property
    def URL_METHOD_ACTION_MAP(self):
        return {
            "/connect": {
                "POST": self.register
            },
            "/status": {
                "GET": self.get_status
            },
            "/send": {
                "POST": self.add_message
            },
            "/chats": {
                "GET": self.get_chats
            },
            "/connect_p2p": {
                "POST": self.enter_p2p
            },
            "/chats/exit": {
                "POST": self.leave
            }
        }

    @staticmethod
    def connect_db(func):
        @wraps(func)
        async def inner(self, *args, **kwargs):
            try:
                cursor = await self.database.connect()
                logger.info("Connected to db")

                result = func(self, cursor, *args, **kwargs)

            except Exception as exception:
                logger.exception(exception)
                result = self.serialize({"fail": str(exception)})
            finally:
                cursor.disconnect()
            return result
        return inner

    @staticmethod
    def serialize(data: dict):
        return json.dumps(data, indent=2, cls=DbEncoder)

    @staticmethod
    def now():
        return pytz.timezone("Europe/Moscow").localize(datetime.now())

    async def parse(self, message: str=""):
        if not message:
            return
        try:
            method, url, body = message.split(" ", maxsplit=2)
            print(method, url, body, sep=" || ")
            json_body = json.loads(body) if body else dict()
            logger.info(f"body: {json_body}")
            result = await self.URL_METHOD_ACTION_MAP[url][method](json_body)
        except (ValueError, KeyError, TypeError) as error:
            logger.exception(error)
            result = self.serialize({"fail": str(error)})
        else:
            return result

    def check_msg_limit_exceeded(self, cursor, user: User, chat: Chat):
        is_target_msg = (
            lambda obj: (
                obj.author.id == user.id
                and obj.created > self.now() - timedelta(hours=DEFAULT_MSG_LIMIT_PERIOD_HOURS)
            )
        )
        if (
            cursor.get_default_chat_id() == str(chat.id)
            and len(list(filter(is_target_msg, chat.messages))) >= DEFAULT_MSG_LIMIT
        ):
            return True
        return False


    @connect_db
    def register(self, cursor, body: dict):
        peer = cursor.create_user()
        logger.info(f"New peer: {peer}")
        author = cursor.get_user(peer)
        chat = cursor.get_chat(cursor.get_default_chat_id())
        chat.enter(author)
        return self.serialize({"token": peer})

    @connect_db
    def get_status(self, cursor, body: dict):
        user = cursor.get_user(body["user_id"])
        chats = cursor.get_chat_list()
        chats_with_user = list(filter(lambda obj: user in obj.authors, chats))
        return self.serialize({
            "time": self.now(),
            "connections_db_max": cursor.db.max_connections,
            "connections_db_now": len(cursor.db.connections),
            "chat_default": cursor.get_default_chat_id(),
            "chats_count": len(chats),
            "chats_with_user_count": len(chats_with_user),
        })

    @connect_db
    def get_chats(self, cursor, body: dict):
        if (chat_id := body.get("chat_id")) is not None:
            return self.get_chat(cursor, chat_id, body)
        if (user := cursor.get_user(body["user_id"])) is None:
            raise NotExistError
        depth = body.get("depth") or DEFAULT_DEPTH

        chats = cursor.get_chat_list()
        chats_with_user = list(filter(lambda obj: user in obj.authors, chats))
        return self.serialize({
            "chats": [chat.serialize(depth) for chat in chats_with_user],
        })

    @connect_db
    def get_chat(self, cursor, pk, body: dict):
        if (chat := cursor.get_chat(pk)) is None:
            raise NotExistError
        if (user := cursor.get_user(body["user_id"])) not in chat.authors:
            raise NotExistError
        depth = body.get("depth") or DEFAULT_DEPTH

        return self.serialize({
            "history": chat.serialize(depth),
        })

    @connect_db
    def enter_p2p(self, cursor, body: dict):
        user = cursor.get_user(body["user_id"])
        other_user = cursor.get_user(body["other_user_id"])

        chats = list(
            filter(
                lambda obj: (obj.type==ChatType.PRIVATE) and (user in obj.authors) and (other_user in obj.authors),
                cursor.get_chat_list()
            )
        )
        print(chats)

        if not chats:
            p2p_chat_id = cursor.create_p2p_chat(name="p2p")
            p2p_chat = cursor.get_chat(p2p_chat_id)
            p2p_chat.enter(user)
            p2p_chat.enter(other_user)
        else:
            p2p_chat = chats[0]
        return self.serialize({"chat_id": p2p_chat_id})

    @connect_db
    def leave(self, cursor, body: dict):
        user_id = body.get("user_id")
        chat_id = body.get("chat_id")

        if (author := cursor.get_user(user_id)) is None:
            raise NotExistError
        if (chat := cursor.get_chat(chat_id)) is None:
            raise NotExistError

        chat.leave(author)

    @connect_db
    def add_message(self, cursor, body: dict):
        author_id = body.get("author_id")
        chat_id = body.get("chat_id") or cursor.get_default_chat_id()
        message = body.get("message")
        if (author := cursor.get_user(author_id)) is None:
            raise NotExistError
        if (chat := cursor.get_chat(chat_id)) is None:
            raise NotExistError
        if self.msg_limit_enabled and self.check_msg_limit_exceeded(cursor, author, chat):
            raise MsgLimitExceededError
        
        new_message = Message(uuid.uuid4(), self.now(), author, text=message)
        chat.add_message(new_message)
        return self.serialize({"id": new_message.id})

    async def client_connected_callback(self, reader: StreamReader, writer: StreamWriter):
        addr = writer.get_extra_info('peername')
        data = await reader.read(self.limit)
        message = data.decode()
        logger.debug(f"Received {message} from {addr}")

        response = await self.parse(message)

        logger.debug(f"Sending: {response}")
        writer.write(response.encode())
        await writer.drain()

        logger.info("Closing the connection")
        writer.close()
        await writer.wait_closed()

    def sigterm_handler(self):
        logger.warning("SIGTERM called. Finishing")
        loop = asyncio.get_event_loop()
        loop.stop()

    async def listen(self):
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, self.sigterm_handler)

        server = await asyncio.start_server(
            self.client_connected_callback, self.host, self.port, limit=self.limit
        )

        addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
        logger.info(f'Serving on {addrs}')

        async with server:
            await server.serve_forever()


if __name__ == "__main__":
    logging.basicConfig(
        format="[%(levelname)s] - %(asctime)s - %(message)s",
        level=logging.DEBUG,
        datefmt="%H:%M:%S",
    )

    server = Server()
    asyncio.run(server.listen())
