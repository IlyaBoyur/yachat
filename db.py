import uuid
from dataclasses import dataclass, is_dataclass, asdict, field
import pytz
from datetime import datetime, date
from collections import defaultdict
import json
from json import JSONEncoder
import asyncio
from typing import ClassVar

from constants import ChatType


DEFAULT_DEPTH = 20
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
    id: uuid.uuid4


@dataclass(eq=True, frozen=True)
class Message:
    id: uuid.uuid4
    created: datetime
    author: User
    text: str


@dataclass
class Chat:
    id: uuid.uuid4
    name: str
    type: ClassVar[ChatType] = ChatType.COMMON
    messages: set[Message] = field(default_factory=set)
    authors: set[User] = field(default_factory=set)
    size: int = 0

    def add_message(self, message: Message):
        self.messages.add(message)

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
                self.messages,
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
    def enter(self, author: User):
        if len(self.authors) == 2:
            raise RuntimeError()


class NotConnectedError(RuntimeError):
    """Operation is rejected because no established connection found"""
    pass


class NotExistError(RuntimeError):
    """Requested object is not present in database"""
    pass


class ChatStorage:
    def __init__(self, max_connections=MAX_CONNECTIONS):
        self.connections = set()
        self.chats = dict()
        self.users = dict()
        self.max_connections = max_connections

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

    @staticmethod
    def now():
        return pytz.timezone("Europe/Moscow").localize(datetime.now())

    def disconnect(self):
        self.db.disconnect(id(self))

    def get_default_chat_id(self) -> str:
        if not self.db.check_connected(id(self)):
            raise NotConnectedError
        if getattr(self.db, "default_chat_id", None) is None:
            self.db.default_chat_id = self.create_chat(name="default")
        return self.db.default_chat_id

    def enter_chat(self, author_id: str, chat_id: str):
        if not self.db.check_connected(id(self)):
            raise NotConnectedError
        if (author := self.get_user(author_id)) is None:
            raise NotExistError
        if (chat := self.get_chat(chat_id)) is None:
            raise NotExistError

        self.db.chats[uuid.UUID(chat_id)].enter(self.get_user(author_id))
        # chat.enter(author)

    def leave_chat(self, author_id: str, chat_id: str):
        if not self.db.check_connected(id(self)):
            raise NotConnectedError
        if (author := self.get_user(author_id)) is None:
            raise NotExistError
        if (chat := self.get_chat(chat_id)) is None:
            raise NotExistError

        self.db.chats[uuid.UUID(chat_id)].leave(self.get_user(author_id))
        # chat.leave(author)

    def write_to_chat(self, author_id: str, chat_id: str, message: str) -> None:
        if not self.db.check_connected(id(self)):
            raise NotConnectedError
        if (author := self.get_user(author_id)) is None:
            raise NotExistError
        if (chat := self.get_chat(chat_id)) is None:
            raise NotExistError
        
        self.db.chats[uuid.UUID(chat_id)].enter(self.get_user(author_id))
        message = Message(uuid.uuid4(), self.now(), self.get_user(author_id),text=message)
        self.db.chats[uuid.UUID(chat_id)].add_message(message)
        return message.id
        # chat.enter(author)
        # chat.add_message(Message(uuid.uuid4(), self.now(), author, text=message))

    def read_from_chat(self, chat_id: str, depth: int=DEFAULT_DEPTH) -> list[Chat]:
        if not self.db.check_connected(id(self)):
            raise NotConnectedError
        if (chat := self.get_chat(chat_id)) is None:
            raise NotExistError
        # history = self.db.chats[chat_id].get_history(depth)
        history = chat.serialize(depth)
        return json.dumps(history, indent=2, cls=DbEncoder)

    def create_user(self) -> str:
        if not self.db.check_connected(id(self)):
            raise NotConnectedError
        while (new_user:= uuid.uuid4()) in self.db.users:
            pass
        self.db.users[new_user] = User(new_user)
        return str(new_user)

    def get_user(self, id: str) -> User:
        return self.db.users.get(uuid.UUID(id), None)

    def create_chat(self, **kwargs) -> str:
        if not self.db.check_connected(id(self)):
            raise NotConnectedError
        kwargs.pop("id", None)
        while (new_chat_id:= uuid.uuid4()) in self.db.chats:
            pass
        self.db.chats[new_chat_id] = Chat(id=new_chat_id, **kwargs)
        return str(new_chat_id)

    def get_chat(self, id: str) -> Chat:
        return self.db.chats.get(uuid.UUID(id), None)

    def get_chat_list(self) -> list[Chat]:
        return self.db.chats.values()
