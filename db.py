import uuid
from dataclasses import dataclass, is_dataclass, asdict, field
from datetime import datetime, date
from collections import defaultdict
import json
from json import JSONEncoder
import asyncio
from typing import ClassVar, Iterable, Any
from functools import wraps

from constants import ChatType, DEFAULT_DEPTH
from errors import NotConnectedError


MAX_CONNECTIONS = 1


class DbEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        if getattr(obj, "serialize", None):
            return obj.serialize()
        if is_dataclass(obj):
            return asdict(obj)
        if isinstance(obj, (date, datetime,)):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)


@dataclass(eq=True, frozen=True)
class User:
    id: uuid.UUID


@dataclass(eq=True, frozen=True)
class Message:
    id: uuid.UUID
    created: datetime
    author: uuid.UUID
    text: str
    is_comment_on: uuid.UUID = None


@dataclass
class Chat:
    id: uuid.UUID
    name: str
    type: ClassVar[ChatType] = ChatType.COMMON
    messages: dict[Message] = field(default_factory=dict)
    authors: set[User] = field(default_factory=set)
    size: int = 0

    def add_message(self, message: Message):
        self.messages[message.id] = message

    def enter(self, author: User):
        if author not in self.authors:
            self.authors.add(author)
            self.size += 1

    def leave(self, author: User):
        if author in self.authors:
            self.authors.discard(author)
            self.size -= 1

    def serialize(self, depth=DEFAULT_DEPTH):
        obj = dict(
            id=self.id,
            name=self.name,
            messages=sorted(
                self.messages.values(),
                key=lambda obj: obj.created,
                reverse=True
            )[:depth],
            authors=self.authors,
            size=self.size,
        )
        return obj


@dataclass
class PeerToPeerChat(Chat):
    type: ClassVar[ChatType] = ChatType.PRIVATE
    def enter(self, *args, **kwargs):
        if len(self.authors) == 2:
            raise RuntimeError()
        super().enter(*args, **kwargs)



@dataclass
class Complaint:
    id: uuid.UUID
    author: uuid.UUID
    created: datetime
    reported_about: uuid.UUID
    reviewed: bool = False


@dataclass
class UserBan:
    id: uuid.UUID
    user: uuid.UUID
    created: datetime


class ChatStorage:
    def __init__(self, max_connections=MAX_CONNECTIONS):
        self.connections = set()
        self.max_connections = max_connections
        # db
        self.chats = dict()
        self.users = dict()
        self.user_bans = dict()
        self.complaints = dict()

    async def connect(self):
        while len(self.connections) > self.max_connections:
            await asyncio.sleep(0)
        connection = ChatStorageCursor(self)
        self.connections.add(id(connection))
        return connection

    def disconnect(self, connection: int):
        self.connections.discard(connection)
    
    def check_connected(self, connection: int):
        return connection in self.connections


class ChatStorageCursor:
    def __init__(self, db: ChatStorage=None):
        self.db = db

    def disconnect(self):
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
    def first_non_none(sequence: Iterable[Any]):
        return next(
            (item for item in sequence if item is not None),
            None
        )
    
    @check_connected
    def create_complaint(self) -> str:
        while (new_complaint:= uuid.uuid4()) in self.db.complaints:
            pass
        self.db.complaints[new_complaint] = Complaint(new_complaint)
        return str(new_complaint)

    @check_connected
    def delete_complaint(self, pk: str) -> None:
        self.db.complaints.pop(pk, None)

    @check_connected
    def get_complaint_list(self) -> list[Complaint]:
        return self.db.complaints.values()

    @check_connected
    def create_user(self) -> str:
        while (new_user:= uuid.uuid4()) in self.db.users:
            pass
        self.db.users[new_user] = User(new_user)
        return str(new_user)

    @check_connected
    def get_user(self, pk: str) -> User:
        return self.db.users.get(uuid.UUID(pk), None)

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
        while (new_chat_id:= uuid.uuid4()) in self.db.chats:
            pass
        self.db.chats[new_chat_id] = Chat(id=new_chat_id, **kwargs)
        return str(new_chat_id)

    @check_connected
    def create_p2p_chat(self, **kwargs) -> str:
        kwargs.pop("id", None)
        while (new_chat_id:= uuid.uuid4()) in self.db.chats:
            pass
        self.db.chats[new_chat_id] = PeerToPeerChat(id=new_chat_id, **kwargs)
        return str(new_chat_id)

    @check_connected
    def get_chat(self, pk: str) -> Chat:
        return self.db.chats.get(uuid.UUID(pk), None)

    @check_connected
    def get_chat_list(self) -> list[Chat]:
        return self.db.chats.values()

    @check_connected
    def get_message(self, pk: str) -> Message:
        return self.first_non_none(
            chat.messages.get(uuid.UUID(pk)) for chat in self.db.chats.values()
        )
    
    @check_connected
    def create_user_ban(self, **kwargs) -> str:
        kwargs.pop("id", None)
        while (new_ban_id:= uuid.uuid4()) in self.db.user_bans:
            pass
        self.db.user_bans[new_ban_id] = UserBan(id=new_ban_id, **kwargs)
        return str(new_ban_id)

    @check_connected
    def delete_user_ban(self, pk: str) -> None:
        self.db.user_bans.pop(pk, None)
