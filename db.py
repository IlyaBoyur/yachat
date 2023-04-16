import asyncio
import uuid
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime
from functools import wraps
from json import JSONEncoder
from typing import Any, ClassVar, Iterable

import funcy

from constants import ChatType
from errors import MaxMembersError, NotConnectedError
from settings import (
    DEFAULT_DB_CONNECTION_WAIT_SECS,
    DEFAULT_MAX_CONNECTIONS,
    DEFAULT_MSG_COUNT,
)


class DbEncoder(JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, set):
            return list(obj)
        elif getattr(obj, "serialize", None):
            return obj.serialize()
        elif is_dataclass(obj):
            return asdict(obj)
        elif isinstance(obj, (date, datetime)):
            return obj.isoformat()
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)


@dataclass
class User:
    id: uuid.UUID
    banned_when: datetime | None = None
    is_banned: bool = False
    reported_times: int = 0


@dataclass(eq=True, frozen=True)
class Message:
    id: uuid.UUID
    created: datetime
    author: uuid.UUID
    text: str
    is_comment_on: uuid.UUID | None = None


@dataclass
class Chat:
    id: uuid.UUID
    name: str
    type: ClassVar[ChatType] = ChatType.COMMON
    messages: dict[Message] = field(default_factory=dict)
    authors: set[uuid.UUID] = field(default_factory=set)

    @property
    def size(self) -> int:
        return len(self.authors)

    def add_message(self, message: Message) -> None:
        self.messages[message.id] = message

    def enter(self, author: User) -> None:
        if author.id not in self.authors:
            self.authors.add(author.id)

    def leave(self, author: User) -> None:
        if author.id in self.authors:
            self.authors.remove(author.id)

    def serialize(self, count: int = DEFAULT_MSG_COUNT) -> dict:
        obj = dict(
            id=self.id,
            name=self.name,
            messages=sorted(
                self.messages.values(),
                key=lambda obj: obj.created,
                reverse=True,
            )[:count],
            authors=self.authors,
            size=self.size,
        )
        return obj


@dataclass
class PeerToPeerChat(Chat):
    type: ClassVar[ChatType] = ChatType.PRIVATE

    def enter(self, *args, **kwargs) -> None:
        if len(self.authors) == 2:
            raise MaxMembersError
        super().enter(*args, **kwargs)


@dataclass
class Complaint:
    id: uuid.UUID
    author: uuid.UUID
    created: datetime
    reported_user: uuid.UUID
    reason: str
    reviewed: bool = False


class ChatStorage:
    def __init__(self, max_connections: int = DEFAULT_MAX_CONNECTIONS) -> None:
        self.connections = set()
        self.max_connections = max_connections
        # db
        self.chats: dict[uuid.UUID, Chat] = {}
        self.users: dict[uuid.UUID, User] = {}
        self.complaints: dict[uuid.UUID, Complaint] = {}

    async def connect(self) -> "ChatStorageCursor":
        while len(self.connections) > self.max_connections:
            await asyncio.sleep(DEFAULT_DB_CONNECTION_WAIT_SECS)
        connection = ChatStorageCursor(self)
        self.connections.add(id(connection))
        return connection

    def disconnect(self, connection: int) -> None:
        self.connections.discard(connection)

    def check_connected(self, connection: int) -> bool:
        return connection in self.connections


class ChatStorageCursor:
    def __init__(self, db: ChatStorage | None = None) -> None:
        self.db = db

    def disconnect(self) -> None:
        self.db.disconnect(id(self))

    @staticmethod
    def check_connected(func):
        @wraps(func)
        def inner(self, *args, **kwargs):
            if not self.db.check_connected(id(self)):
                raise NotConnectedError
            return func(self, *args, **kwargs)

        return inner

    @staticmethod
    def first_not_none(sequence: Iterable[Any]) -> Any:
        return funcy.first(filter(funcy.notnone, sequence))

    @check_connected
    def create_complaint(self, **kwargs) -> str:
        kwargs.pop("id", None)
        new_complaint_id = uuid.uuid4()
        self.db.complaints[new_complaint_id] = Complaint(
            id=new_complaint_id, **kwargs
        )
        return str(new_complaint_id)

    @check_connected
    def get_complaint_list(self) -> list[Complaint]:
        return self.db.complaints.values()

    @check_connected
    def create_user(self) -> str:
        new_user = uuid.uuid4()
        self.db.users[new_user] = User(new_user)
        return str(new_user)

    @check_connected
    def get_user(self, pk: str) -> User:
        return self.db.users.get(uuid.UUID(pk))

    @check_connected
    def get_user_list(self) -> list[User]:
        return self.db.users.values()

    @check_connected
    def get_default_chat_id(self) -> str:
        if getattr(self.db, "default_chat_id", None) is None:
            self.db.default_chat_id = self.create_chat(name="default")
        return self.db.default_chat_id

    @check_connected
    def create_chat(self, **kwargs) -> str:
        kwargs.pop("id", None)
        new_chat_id = uuid.uuid4()
        self.db.chats[new_chat_id] = Chat(id=new_chat_id, **kwargs)
        return str(new_chat_id)

    @check_connected
    def create_p2p_chat(self, **kwargs) -> str:
        kwargs.pop("id", None)
        new_chat_id = uuid.uuid4()
        self.db.chats[new_chat_id] = PeerToPeerChat(id=new_chat_id, **kwargs)
        return str(new_chat_id)

    @check_connected
    def get_chat(self, pk: str) -> Chat:
        return self.db.chats.get(uuid.UUID(pk))

    @check_connected
    def get_chat_list(self) -> list[Chat]:
        return self.db.chats.values()

    @check_connected
    def get_message(self, pk: str) -> Message:
        return self.first_not_none(
            chat.messages.get(uuid.UUID(pk)) for chat in self.db.chats.values()
        )
