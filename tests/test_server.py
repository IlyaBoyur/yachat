import pytest

from server import Server


# @pytest.mark.asyncio
# async def test_register(mocker, create_storage):
#     db = await create_storage
#     server = Server()
    
#     # patched_db = mocker.patch("db.ChatStorageCursor.create_user", return_value=100500)
#     response = await server.parse("POST /connect")
    
#     assert response == "Token: 100500"


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
