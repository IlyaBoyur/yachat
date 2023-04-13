import asyncio
import pytest

from server import Server
from client import ChatClient
from db import User
import json
import uuid


@pytest.fixture
def server(event_loop, unused_tcp_port):
    server = Server(port=unused_tcp_port)
    cancel_handle = asyncio.ensure_future(server.listen(), loop=event_loop)
    event_loop.run_until_complete(asyncio.sleep(0.01))

    try:
        yield server
    finally:
        cancel_handle.cancel()


@pytest.fixture
def client():
    client = ChatClient()
    return client


@pytest.fixture
def client_other():
    client = ChatClient()
    return client


@pytest.fixture
def client_auth(client):
    user_id = "fdf40ad1-c49b-4dc1-b8b6-ce2d914a7830"
    client.force_login(User(user_id))
    return client, user_id


@pytest.mark.asyncio
@pytest.mark.skip
async def test_register(client, server):
    
    response = await client.signup()
    
    response_json = json.loads(response)
    assert response_json == "Token: 100500"

@pytest.mark.asyncio
@pytest.mark.skip
async def test_send_message_common(client_auth, server):
    response = await client_auth.post_send(message="Hello, world!")
    response_json = json.loads(response)

    _, chat = server.database.chats.popitem()
    assert len(chat.messages) == 1
    assert response_json["id"] == chat.messages.pop()
    print(response_json)

    response = await client.get_status()
    response = await client.get("/chats", data=dict(user_id=client.uuid))


@pytest.mark.asyncio
# @pytest.mark.skip
async def test_connect_p2p(client, client_other, server):
    client.port=server.port
    await client.signup()
    client_other.port=server.port
    await client_other.signup()

    response = await client.post(
        "/connect_p2p", data=dict(user_id=client.uuid, other_user_id=client_other.uuid)
    )
    print(response)
    response_json = json.loads(response)
    print(response_json)
    assert uuid.UUID(response_json["chat_id"]) in server.database.chats


@pytest.mark.asyncio
@pytest.mark.skip
async def test_send_message_p2p(client_auth, server, create_p2p):
    response = await client_auth.post_send(chat_id=chat_id, message="Hello, world!")
    response_json = json.loads(response)

    assert len(chat.messages) == 1

@pytest.mark.asyncio
@pytest.mark.skip
async def test_get_status(client_auth, server):
    response = await client_auth.post_send(message="Hello, world!")
    response_json = json.loads(response)

# @pytest.mark.asyncio
# async def test_common_chat(mocker, create_storage):
#     db = await create_storage
#     server = Server()

#     response = await server.register("POST /connect")
#     assert response == "Token"

#     response = await client.post_send(message="hello, world!")
#     assert response == "success"

#     response = await client.post_send(message="hello, new world!")
#     assert response == "success"

#     response = await client.get_status()
#     assert response == ""
