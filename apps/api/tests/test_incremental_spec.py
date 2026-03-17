"""Tests for incremental_spec_extractor service."""

import uuid
from unittest.mock import AsyncMock

import pytest
from llm_client import LexoraClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Conversation, User
from api.db.models.specification import Specification
from api.services.incremental_spec_extractor import incremental_extract


@pytest.fixture()
def mock_lexora() -> LexoraClient:
    client = AsyncMock(spec=LexoraClient)
    client._strip_think_tags = LexoraClient._strip_think_tags
    return client


@pytest.fixture()
async def user_and_conv(db_session: AsyncSession):
    user = User(
        id=uuid.uuid4(),
        email="spec-test@example.com",
        name="Spec Test User",
        google_sub="spec-google-sub",
    )
    db_session.add(user)
    conv = Conversation(user_id=user.id, title="Test Conversation")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)
    return user, conv


@pytest.mark.asyncio
async def test_creates_new_spec_when_none_exists(db_session, mock_lexora, user_and_conv):
    _, conv = user_and_conv
    mock_lexora.complete = AsyncMock(return_value="# My App Spec\n\n## Overview\nA web app.\n\n## Requirements\n- User auth")

    spec = await incremental_extract(
        session=db_session,
        lexora=mock_lexora,
        conversation_id=conv.id,
        user_message="I need a web app with user auth",
        ai_response="I'll design a web app with authentication...",
        classification_summary="User requires web app with auth",
        categories=["requirement"],
    )

    assert spec is not None
    assert spec.title == "My App Spec"
    assert "Requirements" in spec.content
    assert spec.status == "draft"
    assert spec.conversation_id == conv.id


@pytest.mark.asyncio
async def test_updates_existing_draft_spec(db_session, mock_lexora, user_and_conv):
    _, conv = user_and_conv

    # Create existing draft spec
    existing = Specification(
        conversation_id=conv.id,
        title="Old Spec",
        content="# Old Spec\n\n## Overview\nOriginal content.",
        status="draft",
    )
    db_session.add(existing)
    await db_session.commit()
    await db_session.refresh(existing)
    existing_id = existing.id

    mock_lexora.complete = AsyncMock(return_value="# Updated Spec\n\n## Overview\nOriginal content.\n\n## Requirements\n- New requirement")

    spec = await incremental_extract(
        session=db_session,
        lexora=mock_lexora,
        conversation_id=conv.id,
        user_message="Also add a search feature",
        ai_response="I'll add search functionality...",
        classification_summary="New search requirement",
        categories=["requirement"],
    )

    assert spec is not None
    assert spec.id == existing_id  # Same spec updated
    assert spec.title == "Updated Spec"
    assert "New requirement" in spec.content


@pytest.mark.asyncio
async def test_does_not_touch_approved_spec(db_session, mock_lexora, user_and_conv):
    _, conv = user_and_conv

    # Create approved spec (should not be updated)
    approved = Specification(
        conversation_id=conv.id,
        title="Approved Spec",
        content="# Approved\n\nLocked content.",
        status="approved",
    )
    db_session.add(approved)
    await db_session.commit()

    mock_lexora.complete = AsyncMock(return_value="# New Spec\n\n## Overview\nFresh spec.")

    spec = await incremental_extract(
        session=db_session,
        lexora=mock_lexora,
        conversation_id=conv.id,
        user_message="New requirement",
        ai_response="Noted.",
        classification_summary="New req",
        categories=["requirement"],
    )

    # Should create a NEW spec, not update the approved one
    assert spec is not None
    assert spec.id != approved.id
    assert spec.status == "draft"


@pytest.mark.asyncio
async def test_returns_none_on_empty_response(db_session, mock_lexora, user_and_conv):
    _, conv = user_and_conv
    mock_lexora.complete = AsyncMock(return_value="   ")

    spec = await incremental_extract(
        session=db_session,
        lexora=mock_lexora,
        conversation_id=conv.id,
        user_message="test",
        ai_response="test",
        classification_summary="test",
        categories=[],
    )

    assert spec is None


@pytest.mark.asyncio
async def test_returns_none_on_exception(db_session, mock_lexora, user_and_conv):
    _, conv = user_and_conv
    mock_lexora.complete = AsyncMock(side_effect=Exception("LLM error"))

    spec = await incremental_extract(
        session=db_session,
        lexora=mock_lexora,
        conversation_id=conv.id,
        user_message="test",
        ai_response="test",
        classification_summary="test",
        categories=[],
    )

    assert spec is None
