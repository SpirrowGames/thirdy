import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock

from api.db.models import Conversation, Message, User


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


@pytest.mark.asyncio
async def test_chat_creates_conversation(client: AsyncClient, auth_headers: dict):
    """POST /chat without conversation_id should create a new conversation."""
    response = await client.post(
        "/chat",
        json={"content": "Hello AI"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = parse_sse_events(response.text)
    event_types = [e["event"] for e in events]

    assert "message_saved" in event_types
    assert "token" in event_types
    assert "done" in event_types

    # message_saved should have conversation_id
    msg_saved = next(e for e in events if e["event"] == "message_saved")
    assert "conversation_id" in msg_saved["data"]
    assert "message_id" in msg_saved["data"]


@pytest.mark.asyncio
async def test_chat_auto_title(
    client: AsyncClient,
    auth_headers: dict,
):
    """Auto-created conversation should use first 80 chars of content as title."""
    response = await client.post(
        "/chat",
        json={"content": "What is the meaning of life?"},
        headers=auth_headers,
    )
    events = parse_sse_events(response.text)
    msg_saved = next(e for e in events if e["event"] == "message_saved")
    conv_id = msg_saved["data"]["conversation_id"]

    # Fetch the conversation
    conv_resp = await client.get(
        f"/conversations/{conv_id}",
        headers=auth_headers,
    )
    assert conv_resp.status_code == 200
    assert conv_resp.json()["title"] == "What is the meaning of life?"


@pytest.mark.asyncio
async def test_chat_with_existing_conversation(
    client: AsyncClient,
    auth_headers: dict,
):
    """POST /chat with existing conversation_id should use that conversation."""
    # Create conversation first
    create_resp = await client.post(
        "/conversations",
        json={"title": "Existing conv"},
        headers=auth_headers,
    )
    conv_id = create_resp.json()["id"]

    response = await client.post(
        "/chat",
        json={"content": "Hello", "conversation_id": conv_id},
        headers=auth_headers,
    )
    assert response.status_code == 200
    events = parse_sse_events(response.text)
    msg_saved = next(e for e in events if e["event"] == "message_saved")
    assert msg_saved["data"]["conversation_id"] == conv_id


@pytest.mark.asyncio
async def test_chat_nonexistent_conversation(client: AsyncClient, auth_headers: dict):
    """POST /chat with non-existent conversation_id should return 404."""
    fake_id = str(uuid.uuid4())
    response = await client.post(
        "/chat",
        json={"content": "Hello", "conversation_id": fake_id},
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_chat_sse_format(client: AsyncClient, auth_headers: dict):
    """Verify SSE event format: event: <type>\\ndata: <json>\\n\\n."""
    response = await client.post(
        "/chat",
        json={"content": "Hi"},
        headers=auth_headers,
    )
    events = parse_sse_events(response.text)

    # Check token events contain content
    token_events = [e for e in events if e["event"] == "token"]
    assert len(token_events) > 0
    for te in token_events:
        assert "content" in te["data"]

    # Check done event has conversation_id and message_id
    done_event = next(e for e in events if e["event"] == "done")
    assert "conversation_id" in done_event["data"]
    assert "message_id" in done_event["data"]


@pytest.mark.asyncio
async def test_chat_unauthorized(client: AsyncClient):
    response = await client.post("/chat", json={"content": "Hello"})
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_chat_stream_error(
    client: AsyncClient,
    auth_headers: dict,
    mock_lexora_client,
):
    """When LLM streaming fails, an error SSE event should be sent."""

    async def failing_stream(messages, model=None):
        raise RuntimeError("LLM connection failed")
        # Make it an async generator
        yield  # noqa: unreachable

    mock_lexora_client.stream = failing_stream

    response = await client.post(
        "/chat",
        json={"content": "Hello"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    events = parse_sse_events(response.text)

    # Should have message_saved then error
    event_types = [e["event"] for e in events]
    assert "message_saved" in event_types
    assert "error" in event_types

    error_event = next(e for e in events if e["event"] == "error")
    assert "detail" in error_event["data"]
