import asyncio
import pytest
import uuid
from datetime import datetime, timedelta

from db import Message, ChatStorage


@pytest.mark.asyncio
@pytest.fixture
async def create_storage():
    db = ChatStorage(max_connections=1)
    cursor = await asyncio.create_task(db.connect())

    chats = [cursor.create_chat(name="") for _ in range(2)]
    messages=[Message(msg_id, datetime.now()-timedelta(days=msg_id), uuid.uuid4(), "", None)
                      for msg_id in range(2)]
    [cursor.get_chat(chat).add_message(msg) for chat in chats for msg in messages]
    cursor.disconnect()
    return db, chats, messages
