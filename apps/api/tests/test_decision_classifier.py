"""Tests for decision_classifier service."""

import json
from unittest.mock import AsyncMock

import pytest
from llm_client import LexoraClient

from api.services.decision_classifier import DecisionClassificationResult, classify_decision


@pytest.fixture()
def mock_lexora() -> LexoraClient:
    return AsyncMock(spec=LexoraClient)


@pytest.mark.asyncio
async def test_classify_has_decision(mock_lexora):
    mock_lexora.complete = AsyncMock(return_value=json.dumps({
        "has_decision_point": True,
        "question": "REST API vs GraphQL?",
        "options_hint": ["REST", "GraphQL"],
        "context": "Discussing API design approach",
    }))

    result = await classify_decision(mock_lexora, "Should we use REST or GraphQL?", "Both have trade-offs...")

    assert result.has_decision_point is True
    assert "REST" in result.question
    assert len(result.options_hint) == 2


@pytest.mark.asyncio
async def test_classify_no_decision(mock_lexora):
    mock_lexora.complete = AsyncMock(return_value=json.dumps({
        "has_decision_point": False,
        "question": "",
        "options_hint": [],
        "context": "",
    }))

    result = await classify_decision(mock_lexora, "Hello!", "Hi!")
    assert result.has_decision_point is False


@pytest.mark.asyncio
async def test_classify_handles_error(mock_lexora):
    mock_lexora.complete = AsyncMock(side_effect=Exception("timeout"))
    result = await classify_decision(mock_lexora, "test", "test")
    assert result.has_decision_point is False


@pytest.mark.asyncio
async def test_classify_handles_bad_json(mock_lexora):
    mock_lexora.complete = AsyncMock(return_value="not json")
    result = await classify_decision(mock_lexora, "test", "test")
    assert result.has_decision_point is False
