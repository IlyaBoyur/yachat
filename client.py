import asyncio
import json
import logging
import sys
import uuid

from db import User

logger = logging.getLogger(__name__)


class AsyncClient:
    def __init__(
        self,
        server_host: str = "127.0.0.1",
        server_port: int = 8001,
        limit: int = 64000,
    ):
        self.host = server_host
        self.port = server_port
        self.limit = limit

    async def get(self, url: str, *, data: dict = "") -> str:
        body = json.dumps(data) if data else ""
        return await self.send(f"GET {url} {body}")

    async def post(self, url: str, *, data: dict = "") -> str:
        body = json.dumps(data) if data else ""
        return await self.send(f"POST {url} {body}")

    async def send(self, message: str = "") -> str:
        reader, writer = await asyncio.open_connection(
            self.host, self.port, limit=self.limit
        )
        logger.debug(f"Connected {writer.get_extra_info('peername')}")
        logger.debug(f"Sending `{message}`")
        writer.write(message.encode())
        await writer.drain()

        response = await reader.read(self.limit)
        data = response.decode()
        logger.debug(f"Received: {data}")

        logger.debug("Closing the connection")
        writer.close()
        await writer.wait_closed()
        return data


class ChatClient(AsyncClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.uuid = None

    def force_login(self, user: User) -> None:
        self.uuid = user.id

    async def signup(self) -> None:
        response = await self.post("/connect")
        response_json = json.loads(response)
        uuid = response_json["token"]
        logger.info(f"My uuid: {uuid}")
        self.uuid = uuid

    async def get_status(self) -> None:
        if self.uuid:
            body = dict(user_id=self.uuid)
            data = await self.get("/status", data=body)
            logger.info(f"Current status: {data}")

    async def post_send(
        self, *, chat_id: uuid.UUID | None = None, message: str | None = None
    ) -> None:
        if self.uuid:
            body = dict(author_id=self.uuid, chat_id=chat_id, message=message)
            data = await self.post("/send", data=body)
            logger.info(f"Server responsed: {data}")


async def test_common_chat() -> None:
    client = ChatClient()
    response = await client.signup()
    response = await client.post_send(message="hello, world!")
    response = await client.get_status()
    response = await client.get("/chats", data=dict(user_id=client.uuid))

    client_other = ChatClient()
    response = await client_other.signup()
    response = await client_other.post(
        "/connect_p2p",
        data=dict(user_id=client.uuid, other_user_id=client_other.uuid),
    )
    p2p_chat_id = json.loads(response)["chat_id"]
    response = await client_other.get(
        "/chats", data=dict(user_id=client_other.uuid, chat_id=p2p_chat_id)
    )
    response = await client_other.post(
        "/chats/exit",
        data=dict(user_id=client_other.uuid, chat_id=p2p_chat_id),
    )


if __name__ == "__main__":
    logging.basicConfig(
        format="[%(levelname)s] - %(asctime)s - %(message)s",
        level=logging.DEBUG,
        datefmt="%H:%M:%S",
    )

    client = ChatClient()
    if len(sys.argv) > 1:
        asyncio.run(client.send(sys.argv[1]))
    else:
        asyncio.run(test_common_chat())
