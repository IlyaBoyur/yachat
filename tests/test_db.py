import asyncio
import pytest
import uuid

from db import DbEncoder, NotConnectedError, ChatStorageCursor


@pytest.mark.asyncio
async def test(create_storage):
    import json

    
    async def reader():
        cursor = await asyncio.create_task(db.connect())
        chat = cursor.get_default_chat_id()
        data = cursor.get_chat(chat)
        cursor.disconnect()
        return chat, data

    async def dangler():
        cursor = await asyncio.create_task(db.connect())
        await asyncio.sleep(0.1)
        cursor.disconnect()

    db, chats, *_ = await create_storage
    await dangler()
    chat, data = await reader()
    # assert data == json.dumps(db.chats[uuid.UUID(chat)].serialize(), indent=2, cls=DbEncoder)
    assert data == db.chats[uuid.UUID(chat)]


@pytest.mark.asyncio
@pytest.mark.skip
async def test_read_not_connected(create_storage):
    db, *_ = await create_storage
    with pytest.raises(NotConnectedError):
        ChatStorageCursor(db).get_chat(0)


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

