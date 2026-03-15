import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import AuditReport, Conversation, User
from api.services.audit_service import AuditService


@pytest.fixture()
async def conversation(db_session: AsyncSession, test_user: User) -> Conversation:
    conv = Conversation(user_id=test_user.id, title="Audit Test Conversation")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)
    return conv


@pytest.fixture()
async def audit_report(
    db_session: AsyncSession, conversation: Conversation
) -> AuditReport:
    report = AuditReport(
        conversation_id=conversation.id,
        job_id="test-job-123",
        summary={
            "overall_score": 85,
            "quality_badge": "good",
            "total_findings": 2,
            "findings_by_severity": {"warning": 1, "info": 1},
            "analyzed_entities": {
                "specifications": 1,
                "designs": 0,
                "tasks": 0,
                "codes": 0,
            },
        },
        findings=[
            {
                "severity": "warning",
                "category": "completeness",
                "title": "Missing tests section",
                "description": "The specification does not mention testing strategy.",
                "affected_entity_type": "specification",
                "affected_entity_id": None,
                "suggestion": "Add a testing section.",
            },
            {
                "severity": "info",
                "category": "quality",
                "title": "Consider adding examples",
                "description": "Examples would help clarify requirements.",
                "affected_entity_type": None,
                "affected_entity_id": None,
                "suggestion": None,
            },
        ],
        status="completed",
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    return report


# --- API Tests ---


@pytest.mark.asyncio
async def test_trigger_audit(
    client: AsyncClient,
    auth_headers: dict,
    conversation: Conversation,
):
    """POST audit should return 202 with job_id."""
    with patch(
        "api.routers.audits.get_background_job_service"
    ) as mock_get_service:
        mock_service = AsyncMock()
        mock_job = AsyncMock()
        mock_job.job_id = "new-job-456"
        mock_service.enqueue = AsyncMock(return_value=mock_job)
        mock_get_service.return_value = mock_service

        # Override dependency
        from api.dependencies import get_background_job_service

        client._transport.app.dependency_overrides[  # type: ignore[union-attr]
            get_background_job_service
        ] = lambda: mock_service

        response = await client.post(
            f"/conversations/{conversation.id}/audit",
            headers=auth_headers,
            json={"scope": "full"},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["job_id"] == "new-job-456"
        assert data["conversation_id"] == str(conversation.id)
        assert "message" in data

        mock_service.enqueue.assert_called_once()
        call_kwargs = mock_service.enqueue.call_args
        assert call_kwargs.kwargs["job_type"] == "audit"
        assert call_kwargs.kwargs["func_name"] == "audit_conversation_job"


@pytest.mark.asyncio
async def test_list_audit_reports(
    client: AsyncClient,
    auth_headers: dict,
    conversation: Conversation,
    audit_report: AuditReport,
):
    """GET audits list should return reports for the conversation."""
    response = await client.get(
        f"/conversations/{conversation.id}/audits",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(audit_report.id)
    assert data[0]["summary"]["overall_score"] == 85
    assert data[0]["summary"]["quality_badge"] == "good"


@pytest.mark.asyncio
async def test_get_audit_report(
    client: AsyncClient,
    auth_headers: dict,
    audit_report: AuditReport,
):
    """GET audit report by id should return full report."""
    response = await client.get(
        f"/audits/{audit_report.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(audit_report.id)
    assert data["job_id"] == "test-job-123"
    assert data["status"] == "completed"
    assert len(data["findings"]) == 2
    assert data["findings"][0]["severity"] == "warning"
    assert data["findings"][0]["category"] == "completeness"
    assert data["summary"]["total_findings"] == 2


@pytest.mark.asyncio
async def test_delete_audit_report(
    client: AsyncClient,
    auth_headers: dict,
    audit_report: AuditReport,
):
    """DELETE audit report should remove it."""
    response = await client.delete(
        f"/audits/{audit_report.id}",
        headers=auth_headers,
    )
    assert response.status_code == 204

    # Verify it's gone
    get_response = await client.get(
        f"/audits/{audit_report.id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_audit_report_not_found(
    client: AsyncClient,
    auth_headers: dict,
):
    """GET non-existent audit should return 404."""
    fake_id = str(uuid.uuid4())
    response = await client.get(
        f"/audits/{fake_id}",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_audit_unauthorized(
    client: AsyncClient,
    db_session: AsyncSession,
    conversation: Conversation,
    audit_report: AuditReport,
):
    """Access to another user's audit should return 404."""
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

    response = await client.get(
        f"/audits/{audit_report.id}",
        headers=other_headers,
    )
    assert response.status_code == 404


# --- Service Tests ---


@pytest.mark.asyncio
async def test_audit_service_run(
    db_session: AsyncSession,
    mock_lexora_client,
    conversation: Conversation,
):
    """AuditService.run_audit should parse LLM response and save report."""
    audit_response = json.dumps(
        {
            "findings": [
                {
                    "severity": "error",
                    "category": "consistency",
                    "title": "Mismatched API contract",
                    "description": "Design references an endpoint not in the spec.",
                    "affected_entity_type": "design",
                    "affected_entity_id": None,
                    "suggestion": "Align the design with the specification.",
                },
                {
                    "severity": "warning",
                    "category": "completeness",
                    "title": "No error handling",
                    "description": "Tasks lack error handling descriptions.",
                    "affected_entity_type": "task",
                    "affected_entity_id": None,
                    "suggestion": "Add error handling details.",
                },
            ]
        }
    )
    mock_lexora_client.complete = AsyncMock(return_value=audit_response)

    service = AuditService(db_session, mock_lexora_client)
    report = await service.run_audit(conversation.id)

    assert report.status == "completed"
    assert len(report.findings) == 2
    assert report.summary["overall_score"] == 87  # 100 - 10(error) - 3(warning)
    assert report.summary["quality_badge"] == "good"
    assert report.summary["total_findings"] == 2
    assert report.summary["findings_by_severity"] == {"error": 1, "warning": 1}


@pytest.mark.asyncio
async def test_audit_service_empty_conversation(
    db_session: AsyncSession,
    mock_lexora_client,
    conversation: Conversation,
):
    """Empty conversation should produce score=100."""
    mock_lexora_client.complete = AsyncMock(
        return_value=json.dumps({"findings": []})
    )

    service = AuditService(db_session, mock_lexora_client)
    report = await service.run_audit(conversation.id)

    assert report.summary["overall_score"] == 100
    assert report.summary["quality_badge"] == "excellent"
    assert report.summary["total_findings"] == 0
    assert len(report.findings) == 0


@pytest.mark.asyncio
async def test_score_computation(
    db_session: AsyncSession,
    mock_lexora_client,
    conversation: Conversation,
):
    """Verify severity penalty logic: critical=-20, error=-10, warning=-3, info=-1."""
    findings_json = json.dumps(
        {
            "findings": [
                {
                    "severity": "critical",
                    "category": "consistency",
                    "title": "Critical issue",
                    "description": "A critical problem.",
                },
                {
                    "severity": "error",
                    "category": "quality",
                    "title": "Error issue",
                    "description": "An error.",
                },
                {
                    "severity": "warning",
                    "category": "completeness",
                    "title": "Warning issue",
                    "description": "A warning.",
                },
                {
                    "severity": "info",
                    "category": "redundancy",
                    "title": "Info issue",
                    "description": "An info.",
                },
            ]
        }
    )
    mock_lexora_client.complete = AsyncMock(return_value=findings_json)

    service = AuditService(db_session, mock_lexora_client)
    report = await service.run_audit(conversation.id)

    # 100 - 20 - 10 - 3 - 1 = 66
    assert report.summary["overall_score"] == 66
    assert report.summary["quality_badge"] == "needs_improvement"
    assert report.summary["findings_by_severity"] == {
        "critical": 1,
        "error": 1,
        "warning": 1,
        "info": 1,
    }
