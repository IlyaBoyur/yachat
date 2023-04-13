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

    chats = [cursor.create_chat(name="") for _ in range(2)]
    messages=[Message(msg_id, datetime.now()-timedelta(days=msg_id), uuid.uuid4(), "")
                      for msg_id in range(2)]
    [cursor.get_chat(chat).add_message(msg) for chat in chats for msg in messages]
    cursor.disconnect()
    return db, chats, messages


@pytest.mark.asyncio
async def test(create_storage):
    import json

    
    async def reader():
        cursor = await asyncio.create_task(db.connect())
        chat = cursor.get_default_chat_id()
        data = cursor.read_from_chat(chat)
        cursor.disconnect()
        return chat, data

    async def dangler():
        cursor = await asyncio.create_task(db.connect())
        await asyncio.sleep(0.1)
        cursor.disconnect()

    db, chats, *_ = await create_storage
    await dangler()
    chat, data = await reader()
    assert data == json.dumps(db.chats[uuid.UUID(chat)].get_history(), indent=2, cls=DbEncoder)


@pytest.mark.asyncio
async def test_read_not_connected(create_storage):
    db, *_ = await create_storage
    with pytest.raises(NotConnectedError):
        ChatStorageCursor(db).read_from_chat(0)


@pytest.mark.asyncio
async def test_write_not_connected(create_storage):
    db, *_ = await create_storage
    with pytest.raises(NotConnectedError):
        ChatStorageCursor(db).write_to_chat(0,0,"")


@pytest.mark.asyncio
async def test_leave_not_connected(create_storage):
    db, *_ = await create_storage
    with pytest.raises(NotConnectedError):
        ChatStorageCursor(db).leave_chat(0,0)


@pytest.mark.asyncio
async def test_enter_not_connected(create_storage):
    db, *_ = await create_storage
    with pytest.raises(NotConnectedError):
        ChatStorageCursor(db).enter_chat(0,0)

