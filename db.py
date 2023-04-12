import uuid
from dataclasses import dataclass, is_dataclass, asdict
import pytz
from datetime import datetime, date
from collections import defaultdict
import json
from json import JSONEncoder



DEFAULT_DEPTH = 20


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
    def __init__(self, chats=None):
        self.chats = chats or defaultdict(Chat(uuid.uuid4(), "", set()))
        self.connected = False

    @staticmethod
    def now():
        return pytz.timezone("Europe/Moscow").localize(datetime.now())

    def connect(self):
        self.connected = True
    
    def disconnect(self):
        self.connected = False

    def send_to_chat(self, author_id: uuid.uuid4, chat_id: uuid.uuid4, message: str) -> None:
        if not self.connected:
            raise NotConnectedError
        self.chats[chat_id].add_message(Message(uuid.uuid4(), now(), author_id))

    def read_from_chat(self, chat_id: uuid.uuid4, depth: int=DEFAULT_DEPTH) -> list[Chat]:
        if not self.connected:
            raise NotConnectedError
        history = self.chats[chat_id].get_history(depth)
        return json.dumps(history, indent=2, cls=DbEncoder)




if __name__ == "__main__":
    from datetime import timedelta

    db = ChatStorage(
        chats=[
            Chat(
                x,
                "",
                [
                    Message(y, datetime.now()-timedelta(days=y),uuid.uuid4())
                    for y in range(2)
                ]
            )
            for x in range(2)
        ]
    )
    db.connect()
    JSONData = db.read_from_chat(0)
    print(JSONData)
    db.disconnect()
