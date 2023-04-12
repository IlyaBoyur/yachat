import uuid
from dataclasses import dataclass, is_dataclass, asdict
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
    messages: set[Message]

    def add_message(self, message: Message):
        self.messages.append(message)

    def get_history(self, depth=DEFAULT_DEPTH):
        return sorted(
            self.messages,
            key=lambda obj: obj.created,
            reverse=True
        )[:depth]



class NotConnectedError(RuntimeError):
    """Operation is rejected because no established connection found"""
    pass


class ChatStorage:
    def __init__(self, chats=None, max_connections=MAX_CONNECTIONS):
        self.connections = set()
        self.chats = chats or defaultdict(Chat(uuid.uuid4(), "", set()))
        self.max_connections = max_connections

    async def connect(self):
        while len(self.connections) > self.max_connections:
            await asyncio.sleep(0)
        connection = ChatStorageCursor(self)
        self.connections.add(id(connection))
        return connection

    def disconnect(self, connection):
        self.connections.discard(connection)
    
    def check_connected(self, cursor_id):
        return cursor_id in self.connections


class ChatStorageCursor:
    def __init__(self, db: ChatStorage=None):
        self.db = db
        self.peers = set()

    @staticmethod
    def now():
        return pytz.timezone("Europe/Moscow").localize(datetime.now())

    def disconnect(self):
        self.db.disconnect(self)

    def write_to_chat(self, author_id: uuid.uuid4, chat_id: uuid.uuid4, message: str) -> None:
        if not self.db.check_connected(id(self)):
            raise NotConnectedError
        self.db.chats[chat_id].add_message(Message(uuid.uuid4(), self.now(), author_id))

    def read_from_chat(self, chat_id: uuid.uuid4, depth: int=DEFAULT_DEPTH) -> list[Chat]:
        if not self.db.check_connected(id(self)):
            raise NotConnectedError
        history = self.db.chats[chat_id].get_history(depth)
        return json.dumps(history, indent=2, cls=DbEncoder)
