import asyncio
import logging
import sys
import uuid
import json

from db import User


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8001
DEFAULT_LIMIT = 64000


logger = logging.getLogger(__name__)


class Client:
    def __init__(self, server_host: str=DEFAULT_HOST,
                 server_port: int=DEFAULT_PORT, limit: int=DEFAULT_LIMIT):
        self.host = server_host
        self.port = server_port
        self.limit = limit
        self.uuid = None

    async def get(self, url: str, *, data: dict=""):
        return await self.send(f"GET {url} {json.dumps(data)}")

    async def post(self, url, *, data: dict=""):
        return await self.send(f"POST {url} {json.dumps(data)}")

    async def signup(self):
        data = await self.post("/connect")
        _, uuid = data.split()
        logger.info(f"My uuid: {uuid}")
        self.uuid = uuid

    async def get_status(self):
        if self.uuid:
            body = dict(user_id=self.uuid)
            data = await self.get("/status", data=body)
            logger.info(f"Current status: {data}")


    async def post_send(self, *, chat_id: uuid.uuid4=None, message=None):
        if self.uuid:
            body = dict(author_id=self.uuid, chat_id=chat_id, message=message)
            data = await self.post("/send", data=body)
            logger.info(f"Result: {data}")


    async def send(self, message=""):
        reader, writer = await asyncio.open_connection(
            self.host, self.port, limit=self.limit
        )
        logger.debug(f"Connected {writer.get_extra_info('peername')}")
        logger.debug(f"Sending `{message}`")
        writer.write(message.encode())
        await writer.drain()

        response = await reader.read(self.limit)
        data = response.decode()
        logger.debug(f'Received: {data}')

        logger.debug('Closing the connection')
        writer.close()
        await writer.wait_closed()
        return data

    def force_login(self, user: User):
        self.uuid = user.id


async def test_common_chat():
    client = Client()
    response = await client.signup()
    response = await client.post_send(message="hello, world!")
    response = await client.post_send(message="hello, new world!")
    response = await client.get_status()
    response = await client.get("/chats", data=dict(user_id=client.uuid))


if __name__ == "__main__":
    logging.basicConfig(
        format="[%(levelname)s] - %(asctime)s - %(message)s",
        level=logging.DEBUG,
        datefmt="%H:%M:%S",
    )

    client = Client()
    if len(sys.argv) > 1:
        asyncio.run(client.send(sys.argv[1]))
    else:
        asyncio.run(test_common_chat())
