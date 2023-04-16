import asyncio
import uuid
from datetime import datetime, timedelta

import pytest

from db import ChatStorage, Message

from .factories import ChatFactory, MessageFactory


@pytest.mark.asyncio
@pytest.fixture
async def create_storage():
    db = ChatStorage(max_connections=1)
    messages = [MessageFactory() for _ in range(2)]
    chats = [ChatFactory(name="", messages=messages) for _ in range(2)]
    db.chats = {chat.id: chat for chat in chats}
    return db, chats, messages
