import asyncio
import pytest
import uuid
from datetime import datetime, timedelta

from db import ChatStorage, Chat, Message, DbEncoder, NotConnectedError, ChatStorageCursor


@pytest.fixture
def create_storage():
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
        ],
        max_connections=1,
    )
    return db


@pytest.mark.asyncio
async def test(create_storage):
    import json

    
    async def reader():
        cursor = await asyncio.create_task(db.connect())
        data = cursor.read_from_chat(0)
        cursor.disconnect()
        return data

    async def dangler():
        cursor = await asyncio.create_task(db.connect())
        await asyncio.sleep(0.1)
        cursor.disconnect()

    db = create_storage
    await dangler()
    data = await reader()
    print(data)
    assert data == json.dumps(db.chats[0].get_history(), indent=2, cls=DbEncoder)


def test_read_not_connected(create_storage):
    db = create_storage
    with pytest.raises(NotConnectedError):
        ChatStorageCursor(db).read_from_chat(0)


def test_write_not_connected(create_storage):
    db = create_storage
    with pytest.raises(NotConnectedError):
        ChatStorageCursor(db).write_to_chat(0,0,"")
