import json

import pytest

from client import ChatClient
from db import User

TEST_CHAT = "test_chat"
TEST_MESSAGE = "test_message"
TEST_USER = "test_user"

pytestmark = pytest.mark.asyncio


async def test_connect(mocker):
    patched_send = mocker.patch(
        "client.ChatClient.send", return_value='{"token":0}'
    )
    client = ChatClient()

    await client.signup()

    patched_send.assert_called_once_with("POST /connect ")


async def test_send(mocker):
    patched_send = mocker.patch("client.ChatClient.send", return_value="1 2")
    client = ChatClient()
    client.force_login(User(TEST_USER))

    await client.post_send(message=TEST_MESSAGE)

    body = json.dumps(
        dict(author_id=TEST_USER, chat_id=None, message=TEST_MESSAGE)
    )
    patched_send.assert_called_once_with(f"POST /send {body}")


async def test_send_chat(mocker):
    patched_send = mocker.patch("client.ChatClient.send", return_value="1 2")
    client = ChatClient()
    client.force_login(User(TEST_USER))
    data = dict(author_id=TEST_USER, chat_id=TEST_CHAT, message=TEST_MESSAGE)

    await client.post_send(chat_id=TEST_CHAT, message=TEST_MESSAGE)

    body = json.dumps(data)
    patched_send.assert_called_once_with(f"POST /send {body}")


async def test_get_status(mocker):
    patched_send = mocker.patch("client.ChatClient.send", return_value="1 2")
    client = ChatClient()
    client.force_login(User(TEST_USER))
    data = dict(user_id=TEST_USER)

    await client.get_status()

    body = json.dumps(data)
    patched_send.assert_called_once_with(f"GET /status {body}")
