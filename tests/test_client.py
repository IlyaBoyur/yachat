import asyncio
import pytest
import json

from client import Client
from db import User


@pytest.mark.asyncio
async def test_connect(mocker):
    patched_send = mocker.patch("client.Client.send", return_value="1 2")
    client = Client()

    await client.signup()

    patched_send.assert_called_once_with("POST /connect ")


@pytest.mark.asyncio
async def test_send(mocker):
    patched_send = mocker.patch("client.Client.send", return_value="1 2")
    client = Client()
    user_id = "fdf40ad1-c49b-4dc1-b8b6-ce2d914a7830"
    client.force_login(User(user_id))

    await client.post_send(message="hello, world!")

    body = json.dumps(dict(author_id=user_id, chat_id=None, message="hello, world!"))
    patched_send.assert_called_once_with(f"POST /send {body}")


@pytest.mark.asyncio
async def test_get_status(mocker):
    patched_send = mocker.patch("client.Client.send", return_value="1 2")
    client = Client()
    user_id = "fdf40ad1-c49b-4dc1-b8b6-ce2d914a7830"
    client.force_login(User(user_id))

    await client.get_status()

    body = json.dumps(dict(user_id=user_id))
    patched_send.assert_called_once_with(f"GET /status {body}")


