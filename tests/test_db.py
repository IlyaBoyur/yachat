import asyncio
import pytest
import uuid
from datetime import datetime, timedelta

from db import ChatStorage, Chat, Message, DbEncoder, NotConnectedError, ChatStorageCursor


@pytest.mark.asyncio
@pytest.fixture
async def create_storage():
    db = ChatStorage(max_connections=1)
    cursor = await asyncio.create_task(db.connect())
    [
        cursor.create_chat(
            id=chat_id,
            name="",
            messages=[Message(msg_id, datetime.now()-timedelta(days=msg_id),uuid.uuid4())
                      for msg_id in range(2)]
        )
        for chat_id in range(2)
    ]
    cursor.disconnect()
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

    db = await create_storage
    await dangler()
    data = await reader()
    print(data)
    assert data == json.dumps(db.chats[0].get_history(), indent=2, cls=DbEncoder)


@pytest.mark.asyncio
async def test_read_not_connected(create_storage):
    db = await create_storage
    with pytest.raises(NotConnectedError):
        ChatStorageCursor(db).read_from_chat(0)


@pytest.mark.asyncio
async def test_write_not_connected(create_storage):
    db = await create_storage
    with pytest.raises(NotConnectedError):
        ChatStorageCursor(db).write_to_chat(0,0,"")
