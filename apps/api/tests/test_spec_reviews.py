import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Conversation, Specification, SpecReview, User
from api.services.spec_review_service import SpecReviewService


@pytest.fixture()
async def conversation(db_session: AsyncSession, test_user: User) -> Conversation:
    conv = Conversation(user_id=test_user.id, title="Spec Review Test")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)
    return conv


@pytest.fixture()
async def specification(
    db_session: AsyncSession, conversation: Conversation
) -> Specification:
    spec = Specification(
        conversation_id=conversation.id,
        title="Test Spec",
        content=(
            "# Test Spec\n\n"
            "## Overview\nA test specification.\n\n"
            "## Requirements\n- User authentication via JWT\n"
            "- Data stored in PostgreSQL\n\n"
            "## Technical Details\n- REST API with FastAPI\n"
            "- The system uses synchronous processing.\n\n"
            "## Constraints\n- Must handle appropriately.\n"
        ),
        status="draft",
    )
    db_session.add(spec)
    await db_session.commit()
    await db_session.refresh(spec)
    return spec


@pytest.fixture()
async def spec_review(
    db_session: AsyncSession,
    conversation: Conversation,
    specification: Specification,
) -> SpecReview:
    review = SpecReview(
        specification_id=specification.id,
        conversation_id=conversation.id,
        job_id="test-review-job",
        status="completed",
        scope="full",
        summary={
            "quality_score": 75,
            "quality_badge": "good",
            "total_issues": 2,
            "total_suggestions": 2,
            "total_questions": 1,
            "issues_by_category": {"ambiguity": 1, "gap": 1},
            "issues_by_severity": {"warning": 2},
        },
        issues=[
            {
                "severity": "warning",
                "category": "ambiguity",
                "title": "Vague constraint",
                "description": "'Must handle appropriately' is vague.",
                "location": "## Constraints",
            },
            {
                "severity": "warning",
                "category": "gap",
                "title": "Missing error handling",
                "description": "No error handling strategy defined.",
                "location": None,
            },
        ],
        suggestions=[
            {
                "severity": "warning",
                "title": "Clarify constraint",
                "description": "Replace vague language with specific behavior.",
                "before": "Must handle appropriately.",
                "after": "Must return HTTP 400 with a descriptive error message for invalid input.",
                "section": "## Constraints",
                "status": "pending",
                "related_issue_index": 0,
            },
            {
                "severity": "warning",
                "title": "Add error handling section",
                "description": "Define error handling strategy.",
                "before": None,
                "after": "## Error Handling\n- All endpoints return structured error responses\n- 4xx for client errors, 5xx for server errors",
                "section": None,
                "status": "pending",
                "related_issue_index": 1,
            },
        ],
        questions=[
            {
                "question": "What authentication provider will be used besides JWT?",
                "context": "The spec mentions JWT but not the identity provider.",
                "priority": "medium",
            },
        ],
        spec_snapshot="original content",
    )
    db_session.add(review)
    await db_session.commit()
    await db_session.refresh(review)
    return review


# --- API Tests ---


@pytest.mark.asyncio
async def test_trigger_spec_review(
    client: AsyncClient,
    auth_headers: dict,
    conversation: Conversation,
    specification: Specification,
):
    """POST spec review should return 202 with job_id."""
    with patch(
        "api.routers.spec_reviews.get_background_job_service"
    ) as mock_get_service:
        mock_service = AsyncMock()
        mock_job = AsyncMock()
        mock_job.job_id = "review-job-789"
        mock_service.enqueue = AsyncMock(return_value=mock_job)
        mock_get_service.return_value = mock_service

        from api.dependencies import get_background_job_service

        client._transport.app.dependency_overrides[  # type: ignore[union-attr]
            get_background_job_service
        ] = lambda: mock_service

        response = await client.post(
            f"/conversations/{conversation.id}/specs/{specification.id}/review",
            headers=auth_headers,
            json={"scope": "full"},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["job_id"] == "review-job-789"
        assert data["specification_id"] == str(specification.id)
        assert data["conversation_id"] == str(conversation.id)

        mock_service.enqueue.assert_called_once()
        call_kwargs = mock_service.enqueue.call_args
        assert call_kwargs.kwargs["job_type"] == "spec_review"
        assert call_kwargs.kwargs["func_name"] == "spec_review_job"


@pytest.mark.asyncio
async def test_list_spec_reviews(
    client: AsyncClient,
    auth_headers: dict,
    conversation: Conversation,
    specification: Specification,
    spec_review: SpecReview,
):
    """GET reviews list should return reviews for the spec."""
    response = await client.get(
        f"/conversations/{conversation.id}/specs/{specification.id}/reviews",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(spec_review.id)
    assert data[0]["summary"]["quality_score"] == 75


@pytest.mark.asyncio
async def test_get_spec_review(
    client: AsyncClient,
    auth_headers: dict,
    conversation: Conversation,
    specification: Specification,
    spec_review: SpecReview,
):
    """GET spec review by id should return full review."""
    response = await client.get(
        f"/conversations/{conversation.id}/specs/{specification.id}/reviews/{spec_review.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(spec_review.id)
    assert data["status"] == "completed"
    assert len(data["issues"]) == 2
    assert len(data["suggestions"]) == 2
    assert len(data["questions"]) == 1
    assert data["issues"][0]["category"] == "ambiguity"
    assert data["suggestions"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_apply_suggestion_preview(
    client: AsyncClient,
    auth_headers: dict,
    conversation: Conversation,
    specification: Specification,
    spec_review: SpecReview,
):
    """PATCH apply with confirm=False should return preview only."""
    response = await client.patch(
        f"/conversations/{conversation.id}/specs/{specification.id}/reviews/{spec_review.id}/suggestions/0/apply",
        headers=auth_headers,
        json={"confirm": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["applied"] is False
    assert data["preview_diff"] is not None
    assert "Must handle appropriately." in data["preview_diff"]


@pytest.mark.asyncio
async def test_apply_suggestion_confirm(
    client: AsyncClient,
    auth_headers: dict,
    conversation: Conversation,
    specification: Specification,
    spec_review: SpecReview,
):
    """PATCH apply with confirm=True should update spec content."""
    response = await client.patch(
        f"/conversations/{conversation.id}/specs/{specification.id}/reviews/{spec_review.id}/suggestions/0/apply",
        headers=auth_headers,
        json={"confirm": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["applied"] is True
    assert "HTTP 400" in data["updated_content"]
    assert "Must handle appropriately." not in data["updated_content"]


@pytest.mark.asyncio
async def test_dismiss_suggestion(
    client: AsyncClient,
    auth_headers: dict,
    conversation: Conversation,
    specification: Specification,
    spec_review: SpecReview,
):
    """PATCH dismiss should set suggestion status to dismissed."""
    response = await client.patch(
        f"/conversations/{conversation.id}/specs/{specification.id}/reviews/{spec_review.id}/suggestions/0/dismiss",
        headers=auth_headers,
    )
    assert response.status_code == 200

    # Verify the status is now dismissed
    get_response = await client.get(
        f"/conversations/{conversation.id}/specs/{specification.id}/reviews/{spec_review.id}",
        headers=auth_headers,
    )
    review_data = get_response.json()
    assert review_data["suggestions"][0]["status"] == "dismissed"


@pytest.mark.asyncio
async def test_delete_spec_review(
    client: AsyncClient,
    auth_headers: dict,
    conversation: Conversation,
    specification: Specification,
    spec_review: SpecReview,
):
    """DELETE spec review should remove it."""
    response = await client.delete(
        f"/conversations/{conversation.id}/specs/{specification.id}/reviews/{spec_review.id}",
        headers=auth_headers,
    )
    assert response.status_code == 204

    get_response = await client.get(
        f"/conversations/{conversation.id}/specs/{specification.id}/reviews/{spec_review.id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_suggestion_out_of_range(
    client: AsyncClient,
    auth_headers: dict,
    conversation: Conversation,
    specification: Specification,
    spec_review: SpecReview,
):
    """PATCH apply with invalid index should return 400."""
    response = await client.patch(
        f"/conversations/{conversation.id}/specs/{specification.id}/reviews/{spec_review.id}/suggestions/99/apply",
        headers=auth_headers,
        json={"confirm": True},
    )
    assert response.status_code == 400


# --- Service Tests ---


@pytest.mark.asyncio
async def test_spec_review_service_run(
    db_session: AsyncSession,
    mock_lexora_client,
    conversation: Conversation,
    specification: Specification,
):
    """SpecReviewService.run_review should parse LLM response and save review."""
    review_response = json.dumps(
        {
            "issues": [
                {
                    "severity": "warning",
                    "category": "ambiguity",
                    "title": "Vague requirement",
                    "description": "The requirement is not specific enough.",
                    "location": "## Requirements",
                },
            ],
            "suggestions": [
                {
                    "severity": "warning",
                    "title": "Clarify requirement",
                    "description": "Add specific criteria.",
                    "before": "handle appropriately",
                    "after": "return HTTP 400 with error details",
                    "section": "## Requirements",
                    "related_issue_index": 0,
                },
            ],
            "questions": [
                {
                    "question": "What are the expected response times?",
                    "context": "No performance requirements specified.",
                    "priority": "high",
                },
            ],
        }
    )
    mock_lexora_client.complete = AsyncMock(return_value=review_response)

    service = SpecReviewService(db_session, mock_lexora_client)
    review = await service.run_review(
        specification.id, conversation.id, scope="full"
    )

    assert review.status == "completed"
    assert len(review.issues) == 1
    assert len(review.suggestions) == 1
    assert len(review.questions) == 1
    assert review.summary["quality_score"] == 95  # 100 - 5(warning)
    assert review.summary["quality_badge"] == "excellent"
    assert review.summary["issues_by_category"] == {"ambiguity": 1}
    assert review.spec_snapshot is not None


@pytest.mark.asyncio
async def test_spec_review_service_no_issues(
    db_session: AsyncSession,
    mock_lexora_client,
    conversation: Conversation,
    specification: Specification,
):
    """Perfect spec should produce score=100."""
    mock_lexora_client.complete = AsyncMock(
        return_value=json.dumps({"issues": [], "suggestions": [], "questions": []})
    )

    service = SpecReviewService(db_session, mock_lexora_client)
    review = await service.run_review(
        specification.id, conversation.id, scope="full"
    )

    assert review.summary["quality_score"] == 100
    assert review.summary["quality_badge"] == "excellent"
    assert review.summary["total_issues"] == 0


@pytest.mark.asyncio
async def test_spec_review_service_score_computation(
    db_session: AsyncSession,
    mock_lexora_client,
    conversation: Conversation,
    specification: Specification,
):
    """Verify severity penalty logic: critical=-15, warning=-5, info=-1."""
    review_json = json.dumps(
        {
            "issues": [
                {
                    "severity": "critical",
                    "category": "contradiction",
                    "title": "Critical contradiction",
                    "description": "Sync vs async conflict.",
                },
                {
                    "severity": "warning",
                    "category": "gap",
                    "title": "Missing error handling",
                    "description": "No error strategy.",
                },
                {
                    "severity": "info",
                    "category": "inconsistency",
                    "title": "Inconsistent naming",
                    "description": "Minor naming issue.",
                },
            ],
            "suggestions": [],
            "questions": [],
        }
    )
    mock_lexora_client.complete = AsyncMock(return_value=review_json)

    service = SpecReviewService(db_session, mock_lexora_client)
    review = await service.run_review(
        specification.id, conversation.id, scope="full"
    )

    # 100 - 15(critical) - 5(warning) - 1(info) = 79
    assert review.summary["quality_score"] == 79
    assert review.summary["quality_badge"] == "good"
    assert review.summary["issues_by_severity"] == {
        "critical": 1,
        "warning": 1,
        "info": 1,
    }
    assert review.summary["issues_by_category"] == {
        "contradiction": 1,
        "gap": 1,
        "inconsistency": 1,
    }


@pytest.mark.asyncio
async def test_spec_review_service_quick_scope(
    db_session: AsyncSession,
    mock_lexora_client,
    conversation: Conversation,
    specification: Specification,
):
    """Quick scope should use the quick system prompt."""
    mock_lexora_client.complete = AsyncMock(
        return_value=json.dumps({"issues": [], "suggestions": [], "questions": []})
    )

    service = SpecReviewService(db_session, mock_lexora_client)
    review = await service.run_review(
        specification.id, conversation.id, scope="quick"
    )

    assert review.scope == "quick"
    assert review.status == "completed"
    # Verify the quick prompt was used (check call args)
    call_args = mock_lexora_client.complete.call_args
    system_msg = call_args[0][0][0]["content"]
    assert "Quickly scan" in system_msg
