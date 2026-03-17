"""Tests for spec_classifier service."""

import json
from unittest.mock import AsyncMock

import pytest
from llm_client import LexoraClient

from api.services.spec_classifier import ClassificationResult, classify_message


@pytest.fixture()
def mock_lexora() -> LexoraClient:
    return AsyncMock(spec=LexoraClient)


@pytest.mark.asyncio
async def test_classify_spec_relevant(mock_lexora: LexoraClient):
    mock_lexora.complete = AsyncMock(return_value=json.dumps({
        "is_spec_relevant": True,
        "categories": ["requirement", "architecture"],
        "summary": "User wants a REST API with JWT auth",
    }))

    result = await classify_message(
        mock_lexora,
        user_message="I need a REST API with JWT authentication",
        ai_response="I'll design a REST API with JWT-based auth...",
    )

    assert isinstance(result, ClassificationResult)
    assert result.is_spec_relevant is True
    assert "requirement" in result.categories
    assert "architecture" in result.categories
    assert result.summary != ""
    mock_lexora.complete.assert_called_once()


@pytest.mark.asyncio
async def test_classify_not_relevant(mock_lexora: LexoraClient):
    mock_lexora.complete = AsyncMock(return_value=json.dumps({
        "is_spec_relevant": False,
        "categories": [],
        "summary": "",
    }))

    result = await classify_message(
        mock_lexora,
        user_message="Hello!",
        ai_response="Hi! How can I help you today?",
    )

    assert result.is_spec_relevant is False
    assert result.categories == []
    assert result.summary == ""


@pytest.mark.asyncio
async def test_classify_handles_json_error(mock_lexora: LexoraClient):
    mock_lexora.complete = AsyncMock(return_value="not valid json {{{")

    result = await classify_message(
        mock_lexora,
        user_message="test",
        ai_response="test",
    )

    # Should gracefully return not relevant
    assert result.is_spec_relevant is False
    assert result.categories == []


@pytest.mark.asyncio
async def test_classify_handles_llm_exception(mock_lexora: LexoraClient):
    mock_lexora.complete = AsyncMock(side_effect=Exception("LLM timeout"))

    result = await classify_message(
        mock_lexora,
        user_message="test",
        ai_response="test",
    )

    assert result.is_spec_relevant is False


@pytest.mark.asyncio
async def test_classify_uses_json_model(mock_lexora: LexoraClient):
    mock_lexora.complete = AsyncMock(return_value=json.dumps({
        "is_spec_relevant": False,
        "categories": [],
        "summary": "",
    }))

    await classify_message(mock_lexora, "test", "test")

    call_kwargs = mock_lexora.complete.call_args
    assert call_kwargs.kwargs.get("json_mode") is True
