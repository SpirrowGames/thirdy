import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Conversation, Message, Specification, User


def parse_sse_events(text: str) -> list[dict]:
    """Parse SSE text into a list of {event, data} dicts."""
    events = []
    current_event = None
    current_data = None

    for line in text.split("\n"):
        if line.startswith("event: "):
            current_event = line[7:]
        elif line.startswith("data: "):
            current_data = json.loads(line[6:])
        elif line == "" and current_event is not None:
            events.append({"event": current_event, "data": current_data})
            current_event = None
            current_data = None

    return events


@pytest.fixture()
async def conversation(db_session: AsyncSession, test_user: User) -> Conversation:
    conv = Conversation(user_id=test_user.id, title="Test Conversation")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)
    return conv


@pytest.fixture()
async def conversation_with_messages(
    db_session: AsyncSession, conversation: Conversation
) -> Conversation:
    messages = [
        Message(conversation_id=conversation.id, role="user", content="I need a login page"),
        Message(conversation_id=conversation.id, role="assistant", content="Sure, what framework?"),
        Message(conversation_id=conversation.id, role="user", content="React with TypeScript"),
    ]
    for msg in messages:
        db_session.add(msg)
    await db_session.commit()
    return conversation


@pytest.fixture()
async def specification(
    db_session: AsyncSession, conversation: Conversation
) -> Specification:
    spec = Specification(
        conversation_id=conversation.id,
        title="Test Spec",
        content="# Test Spec\n\n## Overview\nA test specification.",
        status="draft",
    )
    db_session.add(spec)
    await db_session.commit()
    await db_session.refresh(spec)
    return spec


# --- Extraction tests ---


@pytest.mark.asyncio
async def test_extract_creates_new_spec(
    client: AsyncClient,
    auth_headers: dict,
    conversation_with_messages: Conversation,
    mock_lexora_client,
):
    """POST extract should create a new spec when none exists."""
    # Set mock to return markdown-like content
    async def markdown_stream(messages, model=None):
        for token in ["# Login", " Page", "\n\n## Overview", "\nA login page."]:
            yield token

    mock_lexora_client.stream = markdown_stream

    conv_id = str(conversation_with_messages.id)
    response = await client.post(
        f"/conversations/{conv_id}/specifications/extract",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = parse_sse_events(response.text)
    event_types = [e["event"] for e in events]

    assert "extraction_started" in event_types
    assert "token" in event_types
    assert "done" in event_types

    started = next(e for e in events if e["event"] == "extraction_started")
    assert started["data"]["conversation_id"] == conv_id
    assert started["data"]["spec_id"] is None
    assert started["data"]["mode"] == "create"

    done = next(e for e in events if e["event"] == "done")
    assert "spec_id" in done["data"]
    assert done["data"]["conversation_id"] == conv_id


@pytest.mark.asyncio
async def test_extract_updates_existing_spec(
    client: AsyncClient,
    auth_headers: dict,
    conversation_with_messages: Conversation,
    specification: Specification,
    mock_lexora_client,
):
    """POST extract should update existing spec when one exists."""
    async def update_stream(messages, model=None):
        for token in ["# Updated", " Spec", "\n\n## Overview", "\nUpdated content."]:
            yield token

    mock_lexora_client.stream = update_stream

    conv_id = str(conversation_with_messages.id)
    response = await client.post(
        f"/conversations/{conv_id}/specifications/extract",
        headers=auth_headers,
    )
    assert response.status_code == 200

    events = parse_sse_events(response.text)
    started = next(e for e in events if e["event"] == "extraction_started")
    assert started["data"]["spec_id"] == str(specification.id)
    assert started["data"]["mode"] == "update"

    done = next(e for e in events if e["event"] == "done")
    assert done["data"]["spec_id"] == str(specification.id)


@pytest.mark.asyncio
async def test_extract_nonexistent_conversation(
    client: AsyncClient, auth_headers: dict
):
    """POST extract with non-existent conversation should return 404."""
    fake_id = str(uuid.uuid4())
    response = await client.post(
        f"/conversations/{fake_id}/specifications/extract",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_extract_unauthorized(client: AsyncClient, conversation: Conversation):
    """POST extract without auth should return 401/403."""
    response = await client.post(
        f"/conversations/{conversation.id}/specifications/extract",
    )
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_extract_other_users_conversation(
    client: AsyncClient,
    db_session: AsyncSession,
    conversation_with_messages: Conversation,
):
    """POST extract on another user's conversation should return 404."""
    other_user = User(
        id=uuid.uuid4(),
        email="other@example.com",
        name="Other User",
        google_sub="google-sub-other",
    )
    db_session.add(other_user)
    await db_session.commit()

    from api.auth.jwt import create_access_token
    token = create_access_token(other_user.id)
    other_headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        f"/conversations/{conversation_with_messages.id}/specifications/extract",
        headers=other_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_extract_stream_error(
    client: AsyncClient,
    auth_headers: dict,
    conversation_with_messages: Conversation,
    mock_lexora_client,
):
    """When LLM streaming fails during extraction, an error event should be sent."""
    async def failing_stream(messages, model=None):
        raise RuntimeError("LLM connection failed")
        yield  # noqa: unreachable

    mock_lexora_client.stream = failing_stream

    conv_id = str(conversation_with_messages.id)
    response = await client.post(
        f"/conversations/{conv_id}/specifications/extract",
        headers=auth_headers,
    )
    assert response.status_code == 200
    events = parse_sse_events(response.text)

    event_types = [e["event"] for e in events]
    assert "extraction_started" in event_types
    assert "error" in event_types

    error_event = next(e for e in events if e["event"] == "error")
    assert "detail" in error_event["data"]


# --- CRUD tests ---


@pytest.mark.asyncio
async def test_list_specifications(
    client: AsyncClient,
    auth_headers: dict,
    conversation: Conversation,
    specification: Specification,
):
    """GET specifications list should return specs for the conversation."""
    response = await client.get(
        f"/conversations/{conversation.id}/specifications",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(specification.id)
    assert data[0]["title"] == "Test Spec"


@pytest.mark.asyncio
async def test_list_specifications_empty(
    client: AsyncClient,
    auth_headers: dict,
    conversation: Conversation,
):
    """GET specifications list should return empty list when none exist."""
    response = await client.get(
        f"/conversations/{conversation.id}/specifications",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_specification(
    client: AsyncClient,
    auth_headers: dict,
    specification: Specification,
):
    """GET specification by id should return the spec."""
    response = await client.get(
        f"/specifications/{specification.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(specification.id)
    assert data["title"] == "Test Spec"
    assert data["status"] == "draft"


@pytest.mark.asyncio
async def test_get_specification_not_found(
    client: AsyncClient, auth_headers: dict
):
    """GET non-existent specification should return 404."""
    fake_id = str(uuid.uuid4())
    response = await client.get(
        f"/specifications/{fake_id}",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_specification(
    client: AsyncClient,
    auth_headers: dict,
    specification: Specification,
):
    """PATCH specification should update fields."""
    response = await client.patch(
        f"/specifications/{specification.id}",
        json={"title": "Updated Title", "status": "in_review"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["status"] == "in_review"


@pytest.mark.asyncio
async def test_update_specification_content(
    client: AsyncClient,
    auth_headers: dict,
    specification: Specification,
):
    """PATCH specification content should update content."""
    response = await client.patch(
        f"/specifications/{specification.id}",
        json={"content": "# New Content\n\nUpdated."},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["content"] == "# New Content\n\nUpdated."


@pytest.mark.asyncio
async def test_delete_specification(
    client: AsyncClient,
    auth_headers: dict,
    specification: Specification,
):
    """DELETE specification should remove it."""
    response = await client.delete(
        f"/specifications/{specification.id}",
        headers=auth_headers,
    )
    assert response.status_code == 204

    # Verify it's gone
    get_response = await client.get(
        f"/specifications/{specification.id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_specification_not_found(
    client: AsyncClient, auth_headers: dict
):
    """DELETE non-existent specification should return 404."""
    fake_id = str(uuid.uuid4())
    response = await client.delete(
        f"/specifications/{fake_id}",
        headers=auth_headers,
    )
    assert response.status_code == 404
