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
async def test_send_message_default(client, server):
    """Signed up user can send messages to default chat"""
    client.port = server.port
    await client.signup()

    TEST_MESSAGE = "test message "
    data = dict(
        author_id=client.uuid,
        chat_id=None,
        message=TEST_MESSAGE,
    )

    response = await client.post("/send", data=data)
    response_json = json.loads(response)

    _, chat = server.database.chats.popitem()
    assert len(chat.messages) == 1
    message = chat.messages.pop()
    assert response_json["id"] == str(message.id)
    assert TEST_MESSAGE == str(message.text)
    assert client.uuid == str(message.author.id)


@pytest.mark.asyncio
async def test_connect_p2p(client, client_other, server):
    client.port=server.port
    await client.signup()
    client_other.port=server.port
    await client_other.signup()

    response = await client.post(
        "/connect_p2p", data=dict(user_id=client.uuid, other_user_id=client_other.uuid)
    )

    chat_uuid = uuid.UUID(json.loads(response)["chat_id"])
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
async def test_get_status(client, server):
    client.port = server.port
    await client.signup()

    response = await client.get("/status", data=dict(user_id=client.uuid))
    response_json = json.loads(response)

    assert "time" in response_json
    assert response_json["connections_db_max"] == server.database.max_connections
    assert response_json["connections_db_now"] == 1
    assert "chat_default" in response_json
    assert response_json["chats_count"] == 1
    assert response_json["chats_with_user_count"] == 1


@pytest.mark.asyncio
async def test_get_chats(client, server):
    client.port = server.port
    await client.signup()

    response = await client.get("/chats", data=dict(user_id=client.uuid))
    response_json = json.loads(response)

    assert len(response_json["chats"]) == 1
    chat = response_json["chats"][0]
    assert "id" in chat
    assert "name" in chat
    assert len(chat["messages"]) == 0
    assert len(chat["authors"]) == 1
    assert chat["authors"][0]["id"] == client.uuid


@pytest.mark.asyncio
async def test_sequence(create_p2p):
    client, client_other, server, chat_id = await create_p2p
    TEST_MESSAGE = "test_message"
    data_default = dict(author_id=client.uuid,
                        chat_id=None,
                        message=TEST_MESSAGE)
    data_p2p = dict(author_id=client.uuid,
                    chat_id=chat_id,
                    message=TEST_MESSAGE)
    [await client.post("/send", data=data_default) for _ in range(3)]
    [await client.post("/send", data=data_p2p) for _ in range(2)]

    response = await client.get("/chats", data=dict(user_id=client.uuid))
    response_json = json.loads(response)

    assert len(response_json["chats"]) == 2
    default = response_json["chats"][0]
    assert default["name"] == "default"
    assert len(default["messages"]) == 3
    assert len(default["authors"]) == 2
    p2p = response_json["chats"][1]
    assert p2p["name"] == "p2p"
    assert len(p2p["messages"]) == 2
    assert len(p2p["authors"]) == 2
    


@pytest.mark.asyncio
async def test_default_chat_limit(client, client_other, server):
    """Default number of available messages is 20"""
    client.port = server.port
    await client.signup()
    data_default = dict(author_id=client.uuid,
                        chat_id=None,
                        message="")
    [await client.post("/send", data=data_default) for _ in range(21)]

    # New client connected
    client_other.port = server.port
    await client_other.signup()
    response = await client_other.get("/chats", data=dict(user_id=client_other.uuid))
    response_json = json.loads(response)

    assert len(response_json["chats"]) == 1
    assert len(response_json["chats"][0]["messages"]) == 20


@pytest.mark.asyncio
async def test_no_chat_limit(client, client_other, server):
    """Default number chat limit can be omitted"""
    client.port = server.port
    await client.signup()
    data_default = dict(author_id=client.uuid,
                        chat_id=None,
                        message="")
    [await client.post("/send", data=data_default) for _ in range(25)]

    # New client connected
    client_other.port = server.port
    await client_other.signup()
    response = await client_other.get("/chats", data=dict(user_id=client_other.uuid, depth=100))
    response_json = json.loads(response)

    assert len(response_json["chats"]) == 1
    assert len(response_json["chats"][0]["messages"]) == 25
