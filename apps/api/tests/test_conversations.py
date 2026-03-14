import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Conversation, Message, User

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_create_conversation(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/conversations",
        json={"title": "Test conversation"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test conversation"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_conversation_no_title(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/conversations",
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["title"] is None


@pytest.mark.asyncio
async def test_create_conversation_unauthorized(client: AsyncClient):
    response = await client.post("/conversations", json={"title": "Test"})
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_conversations(client: AsyncClient, auth_headers: dict):
    # Create two conversations
    await client.post("/conversations", json={"title": "First"}, headers=auth_headers)
    await client.post("/conversations", json={"title": "Second"}, headers=auth_headers)

    response = await client.get("/conversations", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    titles = {d["title"] for d in data}
    assert titles == {"First", "Second"}


@pytest.mark.asyncio
async def test_list_conversations_pagination(client: AsyncClient, auth_headers: dict):
    for i in range(5):
        await client.post("/conversations", json={"title": f"Conv {i}"}, headers=auth_headers)

    response = await client.get("/conversations?limit=2&offset=0", headers=auth_headers)
    assert len(response.json()) == 2

    response = await client.get("/conversations?limit=2&offset=4", headers=auth_headers)
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_get_conversation(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/conversations", json={"title": "My conv"}, headers=auth_headers
    )
    conv_id = create_resp.json()["id"]

    response = await client.get(f"/conversations/{conv_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["title"] == "My conv"


@pytest.mark.asyncio
async def test_get_conversation_not_found(client: AsyncClient, auth_headers: dict):
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/conversations/{fake_id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_conversation_other_user(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict,
):
    """User cannot access another user's conversation."""
    other_user = User(
        id=uuid.uuid4(),
        email="other@example.com",
        name="Other User",
        google_sub="google-sub-other",
    )
    db_session.add(other_user)
    await db_session.commit()

    other_conv = Conversation(user_id=other_user.id, title="Other's conv")
    db_session.add(other_conv)
    await db_session.commit()
    await db_session.refresh(other_conv)

    response = await client.get(f"/conversations/{other_conv.id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_conversation(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/conversations", json={"title": "Old title"}, headers=auth_headers
    )
    conv_id = create_resp.json()["id"]

    response = await client.patch(
        f"/conversations/{conv_id}",
        json={"title": "New title"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "New title"


@pytest.mark.asyncio
async def test_delete_conversation(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/conversations", json={"title": "To delete"}, headers=auth_headers
    )
    conv_id = create_resp.json()["id"]

    response = await client.delete(f"/conversations/{conv_id}", headers=auth_headers)
    assert response.status_code == 204

    # Verify deleted
    response = await client.get(f"/conversations/{conv_id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_messages(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_user: User,
):
    # Create conversation
    create_resp = await client.post(
        "/conversations", json={"title": "With messages"}, headers=auth_headers
    )
    conv_id = create_resp.json()["id"]

    # Add messages directly to DB
    conv_uuid = uuid.UUID(conv_id)
    for role, content in [
        ("user", "Hello"),
        ("assistant", "Hi there!"),
        ("user", "How are you?"),
    ]:
        msg = Message(conversation_id=conv_uuid, role=role, content=content)
        db_session.add(msg)
    await db_session.commit()

    response = await client.get(f"/conversations/{conv_id}/messages", headers=auth_headers)
    assert response.status_code == 200
    messages = response.json()
    assert len(messages) == 3
    assert messages[0]["content"] == "Hello"
    assert messages[0]["role"] == "user"


@pytest.mark.asyncio
async def test_list_messages_not_found(client: AsyncClient, auth_headers: dict):
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/conversations/{fake_id}/messages", headers=auth_headers)
    assert response.status_code == 404
