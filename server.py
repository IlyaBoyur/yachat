import asyncio
from asyncio import StreamReader, StreamWriter
import signal
import logging
import sys
import uuid
from dataclasses import dataclass

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8001
DEFAULT_LIMIT = 64000


logger = logging.Logger(__name__)
logger.addHandler(logging.StreamHandler(stream=sys.stdout))




class Server:
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, limit=DEFAULT_LIMIT):
        self.host = host
        self.port = port
        self.limit = limit

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

    async def parse(self, message: str=""):
        if not message:
            return
        method, url, body = message.split()
        print(method, url, body, sep=" | ")
        result = self.URL_METHOD_ACTION_MAP[url][method](body)
        return result

    def register(self, body: str):
        while peer:= uuid.uuid4() in self.peers:
            pass
        return f"Toker: {peer}"

    def get_status(self, body: str):
        pass

    def add_message(self, body: str):
        self.connect_to_chat(0)

    async def client_connected_callback(self, reader: StreamReader, writer: StreamWriter):
        addr = writer.get_extra_info('peername')
        data = await reader.read(self.limit)
        message = data.decode()
        logger.debug(f"Received {message} from {addr}")

        response = await self.parse(message)

        logger.debug(f"Sending: {response}")
        writer.write(response)
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
        level=logging.INFO,
        datefmt="%H:%M:%S",
    )

    server = Server()
    asyncio.run(server.listen())

