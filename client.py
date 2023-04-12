import asyncio
import logging
import sys
import uuid
import json
# import aiohttp

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8001
DEFAULT_LIMIT = 64000


logger = logging.Logger(__name__)
logger.addHandler(logging.StreamHandler(stream=sys.stdout))


class Client:
    def __init__(self, server_host: str=DEFAULT_HOST,
                 server_port: int=DEFAULT_PORT, limit: int=DEFAULT_LIMIT):
        self.host = server_host
        self.port = server_port
        self.limit = limit
        self.uuid = None

    async def signup(self):
        data = await self.send("POST /connect")
        _, uuid = data.split()
        logger.info(f"My uuid: {uuid}")
        self.uuid = uuid

    async def get_status(self):
        if self.uuid:
            data = await self.send("GET /status")
            logger.info(f"Current status: {data}")


    async def post_send(self, *, chat_id: uuid.uuid4=None, message=None):
        if self.uuid:
            body = json.dumps(dict(author_id=self.uuid, chat_id=chat_id, message=message))
            data = await self.send(f"POST /send {body}")
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

async def test_common_chat():
    client = Client()
    response = await client.signup()
    response = await client.post_send(message="hello, world!")


if __name__ == "__main__":
    logging.basicConfig(
        format="[%(levelname)s] - %(asctime)s - %(message)s",
        level=logging.INFO,
        datefmt="%H:%M:%S",
    )

    client = Client()
    # asyncio.run(client.send(sys.argv[1] if len(sys.argv) > 1 else "test"))
    asyncio.run(test_common_chat())
