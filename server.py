import asyncio
from asyncio import StreamReader, StreamWriter
import signal
import logging
import sys
import uuid
from dataclasses import dataclass
import json
from functools import wraps

from db import ChatStorage, DbEncoder


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8001
DEFAULT_LIMIT = 64000


logger = logging.getLogger(__name__)


class Server:
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, limit=DEFAULT_LIMIT):
        self.host = host
        self.port = port
        self.limit = limit
        self.database = ChatStorage()

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
        }

    @staticmethod
    def connect_db(func):
        @wraps(func)
        async def inner(self, *args, **kwargs):
            try:
                cursor = await self.database.connect()
                logger.info("Connected to db")

                result = func(self, cursor, *args, **kwargs)

            except Exception as e:
                logger.exception(e)
                result = {"fail": e}
            finally:
                cursor.disconnect()
            return result
        return inner

    @staticmethod
    def serialize(data: dict):
        return json.dumps(data, indent=2, cls=DbEncoder)

    async def parse(self, message: str=""):
        if not message:
            return
        try:
            method, url, *body = message.split()
            print(method, url, body, sep="||")
            json_body = json.loads("".join(body)) if body else dict()
            logger.info(f"body: {json_body}")
            result = await self.URL_METHOD_ACTION_MAP[url][method](json_body)
        except (ValueError, KeyError, TypeError) as error:
            logger.exception(error)
            return "fail"
        else:
            return result

    @connect_db
    def register(self, cursor, body: dict):
        peer = cursor.create_user()
        logger.info(f"New peer: {peer}")
        cursor.enter_chat(peer, cursor.get_default_chat_id())
        return f"Token: {peer}"

    @connect_db
    def get_status(self, cursor, body: dict):
        user = cursor.get_user(body["user_id"])
        chats = cursor.get_chat_list()
        chats_with_user = list(filter(lambda obj: user in obj.authors, chats))
        return self.serialize({
            "time": cursor.now(),
            "connections_max": cursor.db.max_connections,
            "connections_now": len(cursor.db.connections),
            "chat_default": cursor.get_default_chat_id(),
            "chats_count": len(chats),
            "chats_with_user_count": len(chats_with_user),
        })

    @connect_db
    def add_message(self, cursor, body: dict):
        author_id = body["author_id"]
        chat_id = body["chat_id"] or cursor.get_default_chat_id()
        message = body["message"]
        cursor.write_to_chat(author_id, chat_id, message)
        return ""

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
