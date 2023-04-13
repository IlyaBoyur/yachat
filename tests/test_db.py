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
    assert data == db.chats[uuid.UUID(chat)]


@pytest.mark.asyncio
async def test_user_not_connected(create_storage):
    db, *_ = await create_storage
    with pytest.raises(NotConnectedError):
        ChatStorageCursor(db).create_user()
    # with pytest.raises(NotConnectedError):
    #     ChatStorageCursor(db).get_user(0)


@pytest.mark.asyncio
async def test_chat_not_connected(create_storage):
    db, *_ = await create_storage
    with pytest.raises(NotConnectedError):
        ChatStorageCursor(db).get_default_chat_id()
    with pytest.raises(NotConnectedError):
        ChatStorageCursor(db).create_chat()
    with pytest.raises(NotConnectedError):
        ChatStorageCursor(db).create_p2p_chat()
    # with pytest.raises(NotConnectedError):
    #     ChatStorageCursor(db).get_chat(0)
    with pytest.raises(NotConnectedError):
        ChatStorageCursor(db).get_chat_list()
        

