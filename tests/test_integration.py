import asyncio
import json
import pytest
import uuid

from client import ChatClient
from db import User
from server import Server


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
async def create_p2p(client, client_other, server):
    client.port=server.port
    await client.signup()
    client_other.port=server.port
    await client_other.signup()
    response = await client.post(
        "/connect_p2p",
        data=dict(user_id=client.uuid, other_user_id=client_other.uuid)
    )
    return client, client_other, server, json.loads(response)["chat_id"]


@pytest.mark.asyncio
async def test_register(client, server):
    client.port = server.port

    await client.signup()

    assert uuid.UUID(client.uuid) in server.database.users


@pytest.mark.asyncio
async def test_send_message_common(client, server):
    client.port = server.port
    await client.signup()

    TEST_MESSAGE = "test_message"
    data = dict(
        author_id=client.uuid,
        chat_id=None,
        message=TEST_MESSAGE,
    )

    response = await client.post("/send", data=data)
    response_json = json.loads(response)

    _, chat = server.database.chats.popitem()
    assert len(chat.messages) == 1
    assert response_json["id"] == str(chat.messages.pop().id)


@pytest.mark.asyncio
async def test_connect_p2p(client, client_other, server):
    client.port=server.port
    await client.signup()
    client_other.port=server.port
    await client_other.signup()

    response = await client.post(
        "/connect_p2p", data=dict(user_id=client.uuid, other_user_id=client_other.uuid)
    )
    response_json = json.loads(response)
    chat_uuid = uuid.UUID(response_json["chat_id"])

    p2p_chat = server.database.chats[chat_uuid]
    p2p_chat_authors = {str(user.id) for user in p2p_chat.authors}
    assert client.uuid in p2p_chat_authors
    assert client_other.uuid in p2p_chat_authors
    assert p2p_chat.size == 2
    assert len(p2p_chat.messages) == 0


@pytest.mark.asyncio
async def test_send_message_p2p(create_p2p):
    client, client_other, server, chat_id = await create_p2p

    TEST_MESSAGE = "test_message"
    data = dict(
        author_id=client.uuid,
        chat_id=chat_id,
        message=TEST_MESSAGE,
    )
    response = await client.post("/send", data=data)
    response_json = json.loads(response)

    msg_uuid = uuid.UUID(response_json["id"])

    p2p_chat = server.database.chats[uuid.UUID(chat_id)]
    p2p_chat_authors = {str(user.id) for user in p2p_chat.authors}
    assert client.uuid in p2p_chat_authors
    assert client_other.uuid in p2p_chat_authors
    assert p2p_chat.size == 2
    assert len(p2p_chat.messages) == 1
    assert msg_uuid in {msg.id for msg in p2p_chat.messages}



@pytest.mark.asyncio
@pytest.mark.skip
async def test_get_status(client_auth, server):
    response = await client_auth.post_send(message="Hello, world!")
    response_json = json.loads(response)


@pytest.mark.asyncio
@pytest.mark.skip
async def test_get_chats(client, server):
    client.port = server.port
    await client.signup()

    response = await client_auth.post_send(message="Hello, world!")
    response_json = json.loads(response)

    response = await client.get("/chats", data=dict(user_id=client.uuid))

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
