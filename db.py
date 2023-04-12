import uuid
from dataclasses import dataclass, is_dataclass, asdict, field
import pytz
from datetime import datetime, date
from collections import defaultdict
import json
from json import JSONEncoder
import asyncio


DEFAULT_DEPTH = 20
MAX_CONNECTIONS = 1


class DbEncoder(JSONEncoder):
    def default(self, obj):
        if is_dataclass(obj):
            return asdict(obj)
        if isinstance(obj, (date, datetime,)):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)


@dataclass
class User:
    id: uuid.uuid4


@dataclass
class Message:
    id: uuid.uuid4
    created: datetime
    author: User


@dataclass
class Chat:
    id: uuid.uuid4
    name: str
    messages: set[Message] = field(default_factory=set)
    authors: set[User] = field(default_factory=set)
    size: int = 0

    def add_message(self, author: uuid.uuid4, message: Message):
        self.messages.add(message)

    def get_history(self, depth=DEFAULT_DEPTH):
        print(self.messages)
        return sorted(
            self.messages,
            key=lambda obj: obj.created,
            reverse=True
        )[:depth]

    def enter(self, author: uuid.uuid4):
        if author not in self.authors:
            self.authors.add(author)
            self.size += 1

    def leave(self, author: uuid.uuid4):
        if author in self.authors:
            self.authors.discard(author)
            self.size -= 1


@dataclass
class PeerToPeerChat(Chat):
    def enter(self, author: uuid.uuid4):
        if len(self.authors) == 2:
            raise RuntimeError()


class NotConnectedError(RuntimeError):
    """Operation is rejected because no established connection found"""
    pass


class ChatStorage:
    def __init__(self, max_connections=MAX_CONNECTIONS):
        self.connections = set()
        # self.chats = chats or defaultdict(Chat(uuid.uuid4(), "", set()))
        self.chats = dict()
        self.users = set()
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
        self.db.disconnect(self)

    def get_default_chat_id(self):
        if not self.db.check_connected(id(self)):
            raise NotConnectedError
        chat_id = getattr(self.db, "default_chat_id", self.create_chat(name="default"))
        self.db.default_chat_id = chat_id
        return chat_id

    def create_chat(self, **kwargs):
        if not self.db.check_connected(id(self)):
            raise NotConnectedError
        chat_id = kwargs.pop("id", uuid.uuid4())
        new_chat = Chat(chat_id, **kwargs)
        self.db.chats[new_chat.id] = new_chat
        return new_chat.id

    def enter_chat(self, author_id: uuid.uuid4, chat_id: uuid.uuid4):
        if not self.db.check_connected(id(self)):
            raise NotConnectedError
        self.db.chats[chat_id].enter(author_id)

    def leave_chat(self, author_id: uuid.uuid4, chat_id: uuid.uuid4):
        if not self.db.check_connected(id(self)):
            raise NotConnectedError
        self.db.chats[chat_id].leave(author_id)

    def write_to_chat(self, author_id: uuid.uuid4, chat_id: uuid.uuid4, message: str) -> None:
        if not self.db.check_connected(id(self)):
            raise NotConnectedError
        self.enter_chat(author_id, chat_id)
        self.db.chats[chat_id].add_message(author_id, Message(uuid.uuid4(), self.now(), author_id))

    def read_from_chat(self, chat_id: uuid.uuid4, depth: int=DEFAULT_DEPTH) -> list[Chat]:
        if not self.db.check_connected(id(self)):
            raise NotConnectedError
        history = self.db.chats[chat_id].get_history(depth)
        return json.dumps(history, indent=2, cls=DbEncoder)




    def create_user(self):
        if not self.db.check_connected(id(self)):
            raise NotConnectedError
        while (new_user:= uuid.uuid4()) in self.db.users:
            pass
        self.db.users.add(new_user)
        return new_user


