import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Conversation, DecisionOption, DecisionPoint, Message, User


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
    conv = Conversation(user_id=test_user.id, title="Decision Test Conversation")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)
    return conv


@pytest.fixture()
async def conversation_with_messages(
    db_session: AsyncSession, conversation: Conversation
) -> Conversation:
    messages = [
        Message(conversation_id=conversation.id, role="user", content="Should we use React or Vue?"),
        Message(conversation_id=conversation.id, role="assistant", content="Both are good options. What are your priorities?"),
        Message(conversation_id=conversation.id, role="user", content="Performance and team familiarity"),
    ]
    for msg in messages:
        db_session.add(msg)
    await db_session.commit()
    return conversation


@pytest.fixture()
async def decision_point(
    db_session: AsyncSession, conversation: Conversation
) -> DecisionPoint:
    dp = DecisionPoint(
        conversation_id=conversation.id,
        question="Which frontend framework to use?",
        context="User asked about React vs Vue",
        recommendation="React due to team familiarity",
        status="pending",
    )
    db_session.add(dp)
    await db_session.flush()

    options = [
        DecisionOption(
            decision_point_id=dp.id,
            label="React",
            description="Popular component-based framework",
            pros=json.dumps(["Large ecosystem", "Team knows it"]),
            cons=json.dumps(["JSX learning curve"]),
            sort_order=0,
        ),
        DecisionOption(
            decision_point_id=dp.id,
            label="Vue",
            description="Progressive framework",
            pros=json.dumps(["Easy to learn", "Good docs"]),
            cons=json.dumps(["Smaller ecosystem"]),
            sort_order=1,
        ),
    ]
    for opt in options:
        db_session.add(opt)
    await db_session.commit()
    await db_session.refresh(dp)
    return dp


LLM_RESPONSE = json.dumps({
    "decision_points": [
        {
            "question": "Which frontend framework?",
            "context": "User asked about React vs Vue",
            "recommendation": "React",
            "options": [
                {
                    "label": "React",
                    "description": "Component-based UI library",
                    "pros": ["Large ecosystem"],
                    "cons": ["Steep learning curve"],
                },
                {
                    "label": "Vue",
                    "description": "Progressive framework",
                    "pros": ["Easy to learn"],
                    "cons": ["Smaller community"],
                },
            ],
        }
    ]
})


# --- Detection tests ---


@pytest.mark.asyncio
async def test_detect_creates_decision_points(
    client: AsyncClient,
    auth_headers: dict,
    conversation_with_messages: Conversation,
    mock_lexora_client,
):
    """POST detect should create decision points from LLM analysis."""
    mock_lexora_client.complete.return_value = LLM_RESPONSE

    conv_id = str(conversation_with_messages.id)
    response = await client.post(
        f"/conversations/{conv_id}/decisions/detect",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = parse_sse_events(response.text)
    event_types = [e["event"] for e in events]

    assert "detection_started" in event_types
    assert "decision_found" in event_types
    assert "done" in event_types

    started = next(e for e in events if e["event"] == "detection_started")
    assert started["data"]["conversation_id"] == conv_id

    found = next(e for e in events if e["event"] == "decision_found")
    assert found["data"]["question"] == "Which frontend framework?"
    assert len(found["data"]["options"]) == 2

    done = next(e for e in events if e["event"] == "done")
    assert done["data"]["count"] == 1
    assert len(done["data"]["decision_point_ids"]) == 1


@pytest.mark.asyncio
async def test_detect_empty_result(
    client: AsyncClient,
    auth_headers: dict,
    conversation_with_messages: Conversation,
    mock_lexora_client,
):
    """POST detect with no decision points found returns done with count 0."""
    mock_lexora_client.complete.return_value = json.dumps({"decision_points": []})

    conv_id = str(conversation_with_messages.id)
    response = await client.post(
        f"/conversations/{conv_id}/decisions/detect",
        headers=auth_headers,
    )
    assert response.status_code == 200

    events = parse_sse_events(response.text)
    done = next(e for e in events if e["event"] == "done")
    assert done["data"]["count"] == 0
    assert done["data"]["decision_point_ids"] == []


@pytest.mark.asyncio
async def test_detect_nonexistent_conversation(
    client: AsyncClient, auth_headers: dict
):
    """POST detect with non-existent conversation should return 404."""
    fake_id = str(uuid.uuid4())
    response = await client.post(
        f"/conversations/{fake_id}/decisions/detect",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_detect_unauthorized(client: AsyncClient, conversation: Conversation):
    """POST detect without auth should return 401/403."""
    response = await client.post(
        f"/conversations/{conversation.id}/decisions/detect",
    )
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_detect_other_users_conversation(
    client: AsyncClient,
    db_session: AsyncSession,
    conversation_with_messages: Conversation,
):
    """POST detect on another user's conversation should return 404."""
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
        f"/conversations/{conversation_with_messages.id}/decisions/detect",
        headers=other_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_detect_llm_error(
    client: AsyncClient,
    auth_headers: dict,
    conversation_with_messages: Conversation,
    mock_lexora_client,
):
    """When LLM call fails, an error event should be sent."""
    mock_lexora_client.complete.side_effect = RuntimeError("LLM connection failed")

    conv_id = str(conversation_with_messages.id)
    response = await client.post(
        f"/conversations/{conv_id}/decisions/detect",
        headers=auth_headers,
    )
    assert response.status_code == 200

    events = parse_sse_events(response.text)
    event_types = [e["event"] for e in events]

    assert "detection_started" in event_types
    assert "error" in event_types

    error_event = next(e for e in events if e["event"] == "error")
    assert "detail" in error_event["data"]


@pytest.mark.asyncio
async def test_detect_json_parse_error(
    client: AsyncClient,
    auth_headers: dict,
    conversation_with_messages: Conversation,
    mock_lexora_client,
):
    """When LLM returns invalid JSON, an error event should be sent."""
    mock_lexora_client.complete.return_value = "This is not valid JSON"

    conv_id = str(conversation_with_messages.id)
    response = await client.post(
        f"/conversations/{conv_id}/decisions/detect",
        headers=auth_headers,
    )
    assert response.status_code == 200

    events = parse_sse_events(response.text)
    event_types = [e["event"] for e in events]

    assert "detection_started" in event_types
    assert "error" in event_types

    error_event = next(e for e in events if e["event"] == "error")
    assert "JSON" in error_event["data"]["detail"]


# --- CRUD tests ---


@pytest.mark.asyncio
async def test_list_decisions(
    client: AsyncClient,
    auth_headers: dict,
    conversation: Conversation,
    decision_point: DecisionPoint,
):
    """GET decisions list should return decision points for the conversation."""
    response = await client.get(
        f"/conversations/{conversation.id}/decisions",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(decision_point.id)
    assert data[0]["question"] == "Which frontend framework to use?"
    assert len(data[0]["options"]) == 2


@pytest.mark.asyncio
async def test_list_decisions_empty(
    client: AsyncClient,
    auth_headers: dict,
    conversation: Conversation,
):
    """GET decisions list should return empty list when none exist."""
    response = await client.get(
        f"/conversations/{conversation.id}/decisions",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_decision(
    client: AsyncClient,
    auth_headers: dict,
    decision_point: DecisionPoint,
):
    """GET decision by id should return the decision point with options."""
    response = await client.get(
        f"/decisions/{decision_point.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(decision_point.id)
    assert data["question"] == "Which frontend framework to use?"
    assert data["status"] == "pending"
    assert len(data["options"]) == 2
    assert data["options"][0]["label"] == "React"
    assert data["options"][0]["pros"] == ["Large ecosystem", "Team knows it"]


@pytest.mark.asyncio
async def test_get_decision_not_found(
    client: AsyncClient, auth_headers: dict
):
    """GET non-existent decision should return 404."""
    fake_id = str(uuid.uuid4())
    response = await client.get(
        f"/decisions/{fake_id}",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_decision_resolve(
    client: AsyncClient,
    auth_headers: dict,
    decision_point: DecisionPoint,
    db_session: AsyncSession,
):
    """PATCH decision should resolve with selected option."""
    # Get the first option id
    from sqlalchemy import select
    result = await db_session.execute(
        select(DecisionOption)
        .where(DecisionOption.decision_point_id == decision_point.id)
        .order_by(DecisionOption.sort_order.asc())
    )
    first_option = result.scalars().first()

    response = await client.patch(
        f"/decisions/{decision_point.id}",
        json={
            "status": "resolved",
            "resolved_option_id": str(first_option.id),
            "resolution_note": "Team prefers React",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "resolved"
    assert data["resolved_option_id"] == str(first_option.id)
    assert data["resolution_note"] == "Team prefers React"


@pytest.mark.asyncio
async def test_update_decision_dismiss(
    client: AsyncClient,
    auth_headers: dict,
    decision_point: DecisionPoint,
):
    """PATCH decision should allow dismissing."""
    response = await client.patch(
        f"/decisions/{decision_point.id}",
        json={"status": "dismissed"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "dismissed"


@pytest.mark.asyncio
async def test_delete_decision(
    client: AsyncClient,
    auth_headers: dict,
    decision_point: DecisionPoint,
):
    """DELETE decision should remove it."""
    response = await client.delete(
        f"/decisions/{decision_point.id}",
        headers=auth_headers,
    )
    assert response.status_code == 204

    # Verify it's gone
    get_response = await client.get(
        f"/decisions/{decision_point.id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_decision_not_found(
    client: AsyncClient, auth_headers: dict
):
    """DELETE non-existent decision should return 404."""
    fake_id = str(uuid.uuid4())
    response = await client.delete(
        f"/decisions/{fake_id}",
        headers=auth_headers,
    )
    assert response.status_code == 404
