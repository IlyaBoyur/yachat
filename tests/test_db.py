import asyncio
import uuid

import pytest

from db import ChatStorageCursor, NotConnectedError


pytestmark = pytest.mark.asyncio


async def test(create_storage):
    async def reader():
        cursor = await db.connect()
        chat = cursor.get_default_chat_id()
        data = cursor.get_chat(chat)
        cursor.disconnect()
        return chat, data

    async def dangler():
        cursor = await db.connect()
        await asyncio.sleep(0.1)
        cursor.disconnect()

    db, chats, *_ = await create_storage
    await dangler()
    chat, data = await reader()
    assert data == db.chats[uuid.UUID(chat)]


@pytest.mark.parametrize(
    "db_compliant_method",
    [
        "create_complaint",
        "delete_complaint",
        "get_complaint_list",
    ],
)
async def test_compliant_not_connected(create_storage, db_compliant_method):
    db, *_ = await create_storage
    cursor = ChatStorageCursor(db)

    with pytest.raises(NotConnectedError):
        getattr(cursor, db_compliant_method)()


@pytest.mark.parametrize(
    "db_user_method",
    [
        "create_user",
        "get_user",
        "get_user_list",
    ],
)
async def test_user_not_connected(create_storage, db_user_method):
    db, *_ = await create_storage
    cursor = ChatStorageCursor(db)

    with pytest.raises(NotConnectedError):
        getattr(cursor, db_user_method)()


@pytest.mark.parametrize(
    "db_chat_method",
    [
        "get_default_chat_id",
        "create_chat",
        "create_p2p_chat",
        "get_chat",
        "get_chat_list",
    ],
)
async def test_chat_not_connected(create_storage, db_chat_method):
    db, *_ = await create_storage
    cursor = ChatStorageCursor(db)

    with pytest.raises(NotConnectedError):
        getattr(cursor, db_chat_method)()


async def test_message_not_connected(create_storage):
    db, *_ = await create_storage
    with pytest.raises(NotConnectedError):
        ChatStorageCursor(db).get_message()
