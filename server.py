import asyncio
import json
import logging
import signal
import uuid
from asyncio import StreamReader, StreamWriter
from datetime import datetime, timedelta
from functools import wraps
from typing import Callable, Any
from constants import ChatType
from settings import (
    DEFAULT_BAN_PERIOD_HOURS,
    DEFAULT_MSG_COUNT,
    DEFAULT_MAX_COMPLAINT_COUNT,
    DEFAULT_MODERATION_CYCLE_SECS,
    DEFAULT_MSG_LIMIT,
    DEFAULT_MSG_LIMIT_PERIOD_HOURS,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SERVER_BUFFER_LIMIT,
)
from db import Chat, ChatStorage, Message, User, ChatStorageCursor
from errors import (
    BannedError,
    MsgLimitExceededError,
    NotExistError,
    ValidationError,
)
import utils


ERROR_DEFAULT_SERVER = "Server Internal error"
ERROR_NOT_SUPPORTED = "Method or url is not supported"

SERVER = "server"
MODERATOR = "moderator"


logger = logging.getLogger(__name__)


class Server:
    def __init__(
        self,
        host: int = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        limit: int = DEFAULT_SERVER_BUFFER_LIMIT,
        msg_limit_enabled: bool = False,
        moderation_cycle_secs: int = DEFAULT_MODERATION_CYCLE_SECS,
    ):
        self.host = host
        self.port = port
        self.limit = limit
        self.MSG_LIMIT_ENABLED = msg_limit_enabled
        self.MODERATION_CYCLE_SECS = moderation_cycle_secs
        self.database = ChatStorage()
        # URL map
        self.URL_METHOD_ACTION_MAP = self.create_url_method_action_map()

    def create_url_method_action_map(self):
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
    def connect_db(user: str = SERVER) -> Callable:
        def wrapper(func: Callable) -> Callable:
            @wraps(func)
            async def inner(self, *args, **kwargs) -> Any:
                try:
                    cursor = await self.database.connect()
                    logger.info(f"Connected {user} to db")

                    result = func(self, cursor, *args, **kwargs)

                except Exception as exception:
                    logger.exception("Error while running db operation")
                    raise
                finally:
                    cursor.disconnect()
                    logger.info(f"Disconnected {user} from db")
                return result

            return inner

        return wrapper

    @staticmethod
    def get_user_and_chat(
        cursor: ChatStorageCursor, user_id: str, chat_id: str
    ) -> tuple[User, Chat]:
        if (chat := cursor.get_chat(chat_id)) is None:
            raise NotExistError
        if (user := cursor.get_user(user_id)) and user.id not in chat.authors:
            raise NotExistError
        return user, chat

    async def parse(self, message: str = "") -> str:
        if not message:
            return ""
        try:
            method, url, body = message.split(" ", maxsplit=2)
            json_body = json.loads(body) if body else {}
            logger.info(f"body: {json_body}")
            result = await self.URL_METHOD_ACTION_MAP[url][method](json_body)
        except (
            ValidationError,
            BannedError,
            NotExistError,
            MsgLimitExceededError,
        ) as error:
            logger.exception("Error caused by user actions")
            return utils.serialize({"fail": str(error)})
        except (ValueError, KeyError, TypeError) as error:
            logger.exception(ERROR_NOT_SUPPORTED)
            return utils.serialize({"fail": ERROR_NOT_SUPPORTED})
        except Exception:
            logger.exception("Error while running Server.parse")
            return utils.serialize({"fail": ERROR_DEFAULT_SERVER})
        else:
            return result

    def check_msg_limit_exceeded(
        self, cursor: ChatStorageCursor, user: User, chat: Chat
    ) -> bool:
        is_target_msg = lambda obj: (
            obj.author == user.id
            and obj.created
            > utils.now() - timedelta(hours=DEFAULT_MSG_LIMIT_PERIOD_HOURS)
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
    def register(self, cursor: ChatStorageCursor, body: dict) -> str:
        peer = cursor.create_user()
        logger.info(f"New peer: {peer}")
        author = cursor.get_user(peer)
        chat = cursor.get_chat(cursor.get_default_chat_id())
        chat.enter(author)
        return utils.serialize({"token": peer})

    @connect_db()
    def get_status(self, cursor: ChatStorageCursor, body: dict) -> str:
        if (user := cursor.get_user(body.get("user_id"))) is None:
            raise NotExistError
        chats = cursor.get_chat_list()
        chats_with_user = list(
            filter(lambda obj: user.id in obj.authors, chats)
        )
        return utils.serialize(
            {
                "time": utils.now(),
                "connections_db_max": cursor.db.max_connections,
                "connections_db_now": len(cursor.db.connections),
                "chat_default": cursor.get_default_chat_id(),
                "chats_count": len(chats),
                "chats_with_user_count": len(chats_with_user),
                "user": user,
            }
        )

    @connect_db()
    def get_chats(self, cursor: ChatStorageCursor, body: dict) -> str:
        if (chat_id := body.get("chat_id")) is not None:
            return self.get_chat(cursor, chat_id, body)
        if (user := cursor.get_user(body.get("user_id"))) is None:
            raise NotExistError
        msg_count = body.get("msg_count") or DEFAULT_MSG_COUNT

        chats = cursor.get_chat_list()
        chats_with_user = list(
            filter(lambda obj: user.id in obj.authors, chats)
        )
        return utils.serialize(
            {
                "chats": [
                    chat.serialize(msg_count) for chat in chats_with_user
                ],
            }
        )

    def get_chat(self, cursor: ChatStorageCursor, pk: str, body: dict) -> str:
        _, chat = self.get_user_and_chat(cursor, body.get("user_id"), pk)
        msg_count = body.get("msg_count") or DEFAULT_MSG_COUNT
        return utils.serialize({"history": chat.serialize(msg_count)})

    @connect_db()
    def enter_p2p(self, cursor: ChatStorageCursor, body: dict) -> str:
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
        return utils.serialize({"chat_id": p2p_chat_id})

    @connect_db()
    def leave(self, cursor: ChatStorageCursor, body: dict) -> str:
        author, chat = self.get_user_and_chat(
            cursor, body.get("user_id"), body.get("chat_id")
        )
        chat.leave(author)
        return utils.serialize({})

    @connect_db()
    def add_message(self, cursor: ChatStorageCursor, body: dict) -> str:
        author, chat = self.get_user_and_chat(
            cursor,
            body.get("author_id"),
            body.get("chat_id") or cursor.get_default_chat_id(),
        )
        message = body.get("message")

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
            utils.now(),
            author.id,
            text=message,
            is_comment_on=comment_on,
        )
        chat.add_message(new_message)
        return utils.serialize({"id": new_message.id})

    @connect_db()
    def report_user(self, cursor: ChatStorageCursor, body: dict) -> str:
        user_id = body.get("user_id")
        reported_user_id = body.get("reported_user_id")
        reason = body.get("reason")

        if (author := cursor.get_user(user_id)) is None:
            raise NotExistError
        if (reported_user := cursor.get_user(reported_user_id)) is None:
            raise NotExistError
        if not reason:
            raise ValidationError("Ban reason should be present")
        bid_already_exists = (
            len(
                [
                    bid
                    for bid in cursor.get_complaint_list()
                    if bid.author == author.id
                    and bid.reported_user == reported_user.id
                ]
            )
            > 0
        )
        if bid_already_exists:
            raise ValidationError("User already reported")

        complaint_id = cursor.create_complaint(
            author=author.id,
            created=utils.now(),
            reported_user=reported_user.id,
            reason=reason,
        )
        return utils.serialize({"id": complaint_id})

    async def client_connected_callback(
        self, reader: StreamReader, writer: StreamWriter
    ) -> None:
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

    def sigint_handler(self) -> None:
        logger.warning("SIGINT called. Finishing")
        loop = asyncio.get_event_loop()
        loop.stop()

    async def listen(self) -> None:
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, self.sigint_handler)

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

    async def moderator(self) -> None:
        while True:
            await self.check_reported_users()
            await self.check_unban()
            await asyncio.sleep(self.MODERATION_CYCLE_SECS)

    @connect_db(user=MODERATOR)
    def check_reported_users(self, cursor) -> None:
        for bid in cursor.get_complaint_list():
            if bid.reviewed:
                continue
            user = cursor.get_user(str(bid.reported_user))
            if user.reported_times + 1 == DEFAULT_MAX_COMPLAINT_COUNT:
                user.is_banned = True
                user.banned_when = utils.now()
            else:
                user.reported_times += 1
            bid.reviewed = True

    @connect_db(user=MODERATOR)
    def check_unban(self, cursor) -> None:
        for user in cursor.get_user_list():
            if (
                user.is_banned
                and user.banned_when
                + timedelta(hours=DEFAULT_BAN_PERIOD_HOURS)
                < utils.now()
            ):
                user.is_banned = False
                user.banned_when = None

    async def startup(self) -> None:
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
