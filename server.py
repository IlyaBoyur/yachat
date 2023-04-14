import asyncio
import json
import logging
import signal
import uuid
from asyncio import StreamReader, StreamWriter
from datetime import datetime, timedelta
from functools import wraps

import pytz

from constants import (
    DEFAULT_BAN_PERIOD_HOURS,
    DEFAULT_DEPTH,
    DEFAULT_MAX_COMPLAINT_COUNT,
    DEFAULT_MODERATION_CYCLE_SECS,
    DEFAULT_MSG_LIMIT,
    DEFAULT_MSG_LIMIT_PERIOD_HOURS,
    ChatType,
)
from db import Chat, ChatStorage, DbEncoder, Message, User
from errors import (
    BannedError,
    MsgLimitExceededError,
    NotExistError,
    ValidationError,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8001
DEFAULT_LIMIT = 64000

SERVER = "server"
MODERATOR = "moderator"


logger = logging.getLogger(__name__)


class Server:
    def __init__(
        self,
        host: int = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        limit: int = DEFAULT_LIMIT,
        msg_limit_enabled: bool = False,
        moderation_cycle_secs: int = DEFAULT_MODERATION_CYCLE_SECS,
    ):
        self.host = host
        self.port = port
        self.limit = limit
        self.MSG_LIMIT_ENABLED = msg_limit_enabled
        self.MODERATION_CYCLE_SECS = moderation_cycle_secs
        self.database = ChatStorage()

    @property
    def URL_METHOD_ACTION_MAP(self):
        return {
            "/connect": {"POST": self.register},
            "/status": {"GET": self.get_status},
            "/send": {"POST": self.add_message},
            "/chats": {"GET": self.get_chats},
            "/connect_p2p": {"POST": self.enter_p2p},
            "/chats/exit": {"POST": self.leave},
            "/report_user": {"POST": self.report_user},
        }

    @staticmethod
    def connect_db(user: str = SERVER):
        def wrapper(func):
            @wraps(func)
            async def inner(self, *args, **kwargs):
                try:
                    cursor = await self.database.connect()
                    logger.info(f"Connected {user} to db")

                    result = func(self, cursor, *args, **kwargs)

                except Exception as exception:
                    logger.exception(exception)
                    result = self.serialize({"fail": str(exception)})
                finally:
                    cursor.disconnect()
                    logger.info(f"Disconnected {user} from db")
                return result

            return inner

        return wrapper

    @staticmethod
    def serialize(data: dict):
        return json.dumps(data, indent=2, cls=DbEncoder)

    @staticmethod
    def now():
        return pytz.timezone("Europe/Moscow").localize(datetime.now())

    async def parse(self, message: str = ""):
        if not message:
            return
        try:
            method, url, body = message.split(" ", maxsplit=2)
            json_body = json.loads(body) if body else dict()
            logger.info(f"body: {json_body}")
            result = await self.URL_METHOD_ACTION_MAP[url][method](json_body)
        except (ValueError, KeyError, TypeError) as error:
            logger.exception(error)
            result = self.serialize({"fail": str(error)})
        else:
            return result

    def check_msg_limit_exceeded(self, cursor, user: User, chat: Chat):
        is_target_msg = lambda obj: (
            obj.author == user.id
            and obj.created
            > self.now() - timedelta(hours=DEFAULT_MSG_LIMIT_PERIOD_HOURS)
        )
        target_is_default_chat = cursor.get_default_chat_id() == str(chat.id)
        msg_count_exceeds_limit = (
            len(list(filter(is_target_msg, chat.messages.values())))
            >= DEFAULT_MSG_LIMIT
        )
        if target_is_default_chat and msg_count_exceeds_limit:
            return True
        return False

    @connect_db()
    def register(self, cursor, body: dict):
        peer = cursor.create_user()
        logger.info(f"New peer: {peer}")
        author = cursor.get_user(peer)
        chat = cursor.get_chat(cursor.get_default_chat_id())
        chat.enter(author)
        return self.serialize({"token": peer})

    @connect_db()
    def get_status(self, cursor, body: dict):
        if (user := cursor.get_user(body.get("user_id"))) is None:
            raise NotExistError
        chats = cursor.get_chat_list()
        chats_with_user = list(
            filter(lambda obj: user.id in obj.authors, chats)
        )
        return self.serialize(
            {
                "time": self.now(),
                "connections_db_max": cursor.db.max_connections,
                "connections_db_now": len(cursor.db.connections),
                "chat_default": cursor.get_default_chat_id(),
                "chats_count": len(chats),
                "chats_with_user_count": len(chats_with_user),
                "user": user,
            }
        )

    @connect_db()
    def get_chats(self, cursor, body: dict):
        if (chat_id := body.get("chat_id")) is not None:
            return self.get_chat(cursor, chat_id, body)
        if (user := cursor.get_user(body.get("user_id"))) is None:
            raise NotExistError
        depth = body.get("depth") or DEFAULT_DEPTH

        chats = cursor.get_chat_list()
        chats_with_user = list(
            filter(lambda obj: user.id in obj.authors, chats)
        )
        return self.serialize(
            {
                "chats": [chat.serialize(depth) for chat in chats_with_user],
            }
        )

    def get_chat(self, cursor, pk, body: dict):
        if (chat := cursor.get_chat(pk)) is None:
            raise NotExistError
        if (
            user := cursor.get_user(body.get("user_id"))
        ) and user.id not in chat.authors:
            raise NotExistError
        depth = body.get("depth") or DEFAULT_DEPTH

        return self.serialize(
            {
                "history": chat.serialize(depth),
            }
        )

    @connect_db()
    def enter_p2p(self, cursor, body: dict):
        user = cursor.get_user(body.get("user_id"))
        other_user = cursor.get_user(body.get("other_user_id"))
        chats = list(
            filter(
                lambda obj: (obj.type == ChatType.PRIVATE)
                and (user.id in obj.authors)
                and (other_user.id in obj.authors),
                cursor.get_chat_list(),
            )
        )
        if not chats:
            p2p_chat_id = cursor.create_p2p_chat(name="p2p")
            p2p_chat = cursor.get_chat(p2p_chat_id)
            p2p_chat.enter(user)
            p2p_chat.enter(other_user)
        else:
            p2p_chat = chats[0]
        return self.serialize({"chat_id": p2p_chat_id})

    @connect_db()
    def leave(self, cursor, body: dict):
        user_id = body.get("user_id")
        chat_id = body.get("chat_id")

        if (author := cursor.get_user(user_id)) is None:
            raise NotExistError
        if (chat := cursor.get_chat(chat_id)) is None:
            raise NotExistError

        chat.leave(author)

    @connect_db()
    def add_message(self, cursor, body: dict):
        author_id = body.get("author_id")
        chat_id = body.get("chat_id") or cursor.get_default_chat_id()
        message = body.get("message")
        if (author := cursor.get_user(author_id)) is None:
            raise NotExistError
        if (chat := cursor.get_chat(chat_id)) is None:
            raise NotExistError
        if self.MSG_LIMIT_ENABLED and self.check_msg_limit_exceeded(
            cursor, author, chat
        ):
            raise MsgLimitExceededError
        comment_on = body.get("comment_on")
        if comment_on is not None and cursor.get_message(comment_on) is None:
            comment_on = None
            logger.warning("Target to comment on is not found")
        if author.is_banned:
            raise BannedError

        new_message = Message(
            uuid.uuid4(),
            self.now(),
            author.id,
            text=message,
            is_comment_on=comment_on,
        )
        chat.add_message(new_message)
        return self.serialize({"id": new_message.id})

    @connect_db()
    def report_user(self, cursor, body: dict):
        user_id = body.get("user_id")
        reported_user_id = body.get("reported_user_id")
        reason = body.get("reason")

        if (author := cursor.get_user(user_id)) is None:
            raise NotExistError
        if (reported_user := cursor.get_user(reported_user_id)) is None:
            raise NotExistError
        if not reason:
            raise ValidationError("Ban reason should be present")
        if (
            len(
                [
                    bid
                    for bid in cursor.get_complaint_list()
                    if bid.author == author.id
                    and bid.reported_user == reported_user.id
                ]
            )
            > 0
        ):
            raise ValidationError("User already reported")

        complaint_id = cursor.create_complaint(
            author=author.id,
            created=self.now(),
            reported_user=reported_user.id,
            reason=reason,
        )
        return self.serialize({"id": complaint_id})

    async def client_connected_callback(
        self, reader: StreamReader, writer: StreamWriter
    ):
        addr = writer.get_extra_info("peername")
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
            self.client_connected_callback,
            self.host,
            self.port,
            limit=self.limit,
        )

        addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)
        logger.info(f"Serving on {addrs}")

        async with server:
            await server.serve_forever()

    async def moderator(self):
        while True:
            await self.check_reported_users()
            await self.check_unban()
            await asyncio.sleep(self.MODERATION_CYCLE_SECS)

    @connect_db(user=MODERATOR)
    def check_reported_users(self, cursor):
        for bid in (
            bid for bid in cursor.get_complaint_list() if not bid.reviewed
        ):
            user = cursor.get_user(str(bid.reported_user))
            if user.reported_times + 1 == DEFAULT_MAX_COMPLAINT_COUNT:
                user.is_banned = True
                user.banned_when = self.now()
            else:
                user.reported_times += 1
            bid.reviewed = True

    @connect_db(user=MODERATOR)
    def check_unban(self, cursor):
        for user in cursor.get_user_list():
            if (
                user.is_banned
                and user.banned_when
                + timedelta(hours=DEFAULT_BAN_PERIOD_HOURS)
                < self.now()
            ):
                user.is_banned = False
                user.banned_when = None

    async def startup(self):
        await asyncio.gather(
            self.listen(), self.moderator(), return_exceptions=True
        )


if __name__ == "__main__":
    logging.basicConfig(
        format="[%(levelname)s] - %(asctime)s - %(message)s",
        level=logging.DEBUG,
        datefmt="%H:%M:%S",
    )

    server = Server()
    asyncio.run(server.startup())
