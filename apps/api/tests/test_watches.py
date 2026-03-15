import json
import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Conversation, User, WatchReport
from api.services.watch_service import WatchService


@pytest.fixture()
async def conversation(db_session: AsyncSession, test_user: User) -> Conversation:
    conv = Conversation(user_id=test_user.id, title="Watch Test Conversation")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)
    return conv


@pytest.fixture()
async def watch_report(
    db_session: AsyncSession, conversation: Conversation
) -> WatchReport:
    report = WatchReport(
        conversation_id=conversation.id,
        job_id="watch-job-123",
        summary={
            "total_findings": 2,
            "findings_by_impact": {"medium": 1, "low": 1},
            "findings_by_source": {"dependency": 1, "security": 1},
            "highest_impact": "medium",
            "requires_action": False,
        },
        findings=[
            {
                "source_type": "dependency",
                "impact_level": "medium",
                "title": "FastAPI 0.115 released",
                "description": "New version includes breaking changes in middleware API.",
                "source_url": "https://github.com/tiangolo/fastapi/releases",
                "affected_area": "backend",
                "recommendation": "Review changelog before upgrading.",
            },
            {
                "source_type": "security",
                "impact_level": "low",
                "title": "SQLAlchemy advisory",
                "description": "Minor security patch available.",
                "source_url": None,
                "affected_area": "backend",
                "recommendation": "Update at next convenience.",
            },
        ],
        watch_targets=["backend"],
        status="completed",
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    return report


# --- API Tests ---


@pytest.mark.asyncio
async def test_trigger_watch(
    client: AsyncClient,
    auth_headers: dict,
    conversation: Conversation,
):
    """POST watch should return 202 with job_id."""
    mock_service = AsyncMock()
    mock_job = AsyncMock()
    mock_job.job_id = "new-watch-job"
    mock_service.enqueue = AsyncMock(return_value=mock_job)

    from api.dependencies import get_background_job_service

    client._transport.app.dependency_overrides[  # type: ignore[union-attr]
        get_background_job_service
    ] = lambda: mock_service

    response = await client.post(
        f"/conversations/{conversation.id}/watch",
        headers=auth_headers,
        json={"targets": ["backend", "frontend"]},
    )
    assert response.status_code == 202
    data = response.json()
    assert data["job_id"] == "new-watch-job"
    assert data["conversation_id"] == str(conversation.id)
    assert "message" in data

    mock_service.enqueue.assert_called_once()
    call_kwargs = mock_service.enqueue.call_args
    assert call_kwargs.kwargs["job_type"] == "watch"
    assert call_kwargs.kwargs["func_name"] == "watch_conversation_job"


@pytest.mark.asyncio
async def test_list_watch_reports(
    client: AsyncClient,
    auth_headers: dict,
    conversation: Conversation,
    watch_report: WatchReport,
):
    """GET watches list should return reports for the conversation."""
    response = await client.get(
        f"/conversations/{conversation.id}/watches",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(watch_report.id)
    assert data[0]["summary"]["highest_impact"] == "medium"
    assert data[0]["summary"]["requires_action"] is False
    assert data[0]["watch_targets"] == ["backend"]


@pytest.mark.asyncio
async def test_get_watch_report(
    client: AsyncClient,
    auth_headers: dict,
    watch_report: WatchReport,
):
    """GET watch report by id should return full report."""
    response = await client.get(
        f"/watches/{watch_report.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(watch_report.id)
    assert data["job_id"] == "watch-job-123"
    assert data["status"] == "completed"
    assert len(data["findings"]) == 2
    assert data["findings"][0]["source_type"] == "dependency"
    assert data["findings"][0]["impact_level"] == "medium"
    assert data["summary"]["total_findings"] == 2


@pytest.mark.asyncio
async def test_delete_watch_report(
    client: AsyncClient,
    auth_headers: dict,
    watch_report: WatchReport,
):
    """DELETE watch report should remove it."""
    response = await client.delete(
        f"/watches/{watch_report.id}",
        headers=auth_headers,
    )
    assert response.status_code == 204

    get_response = await client.get(
        f"/watches/{watch_report.id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_watch_report_not_found(
    client: AsyncClient,
    auth_headers: dict,
):
    """GET non-existent watch should return 404."""
    fake_id = str(uuid.uuid4())
    response = await client.get(
        f"/watches/{fake_id}",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_watch_unauthorized(
    client: AsyncClient,
    db_session: AsyncSession,
    conversation: Conversation,
    watch_report: WatchReport,
):
    """Access to another user's watch report should return 404."""
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
        f"/watches/{watch_report.id}",
        headers=other_headers,
    )
    assert response.status_code == 404


# --- Service Tests ---


@pytest.mark.asyncio
async def test_watch_service_run(
    db_session: AsyncSession,
    mock_lexora_client,
    conversation: Conversation,
):
    """WatchService.run_watch should parse LLM response and save report."""
    watch_response = json.dumps(
        {
            "findings": [
                {
                    "source_type": "dependency",
                    "impact_level": "high",
                    "title": "Major framework update",
                    "description": "Breaking changes in core dependency.",
                    "source_url": "https://example.com",
                    "affected_area": "backend",
                    "recommendation": "Plan migration.",
                },
                {
                    "source_type": "security",
                    "impact_level": "critical",
                    "title": "CVE in auth library",
                    "description": "Remote code execution vulnerability.",
                    "source_url": None,
                    "affected_area": "backend",
                    "recommendation": "Patch immediately.",
                },
            ]
        }
    )
    mock_lexora_client.complete = AsyncMock(return_value=watch_response)

    service = WatchService(db_session, mock_lexora_client)
    report = await service.run_watch(conversation.id, targets=["backend"])

    assert report.status == "completed"
    assert len(report.findings) == 2
    assert report.summary["total_findings"] == 2
    assert report.summary["highest_impact"] == "critical"
    assert report.summary["requires_action"] is True
    assert report.summary["findings_by_impact"] == {"high": 1, "critical": 1}
    assert report.summary["findings_by_source"] == {"dependency": 1, "security": 1}
    assert report.watch_targets == ["backend"]


@pytest.mark.asyncio
async def test_watch_service_no_findings(
    db_session: AsyncSession,
    mock_lexora_client,
    conversation: Conversation,
):
    """Empty findings should produce safe defaults."""
    mock_lexora_client.complete = AsyncMock(
        return_value=json.dumps({"findings": []})
    )

    service = WatchService(db_session, mock_lexora_client)
    report = await service.run_watch(conversation.id)

    assert report.summary["total_findings"] == 0
    assert report.summary["highest_impact"] == "none"
    assert report.summary["requires_action"] is False
    assert len(report.findings) == 0


@pytest.mark.asyncio
async def test_watch_requires_action_threshold(
    db_session: AsyncSession,
    mock_lexora_client,
    conversation: Conversation,
):
    """requires_action should be True only for high or critical impact."""
    # medium impact → requires_action = False
    findings_json = json.dumps(
        {
            "findings": [
                {
                    "source_type": "ecosystem",
                    "impact_level": "medium",
                    "title": "New alternative emerged",
                    "description": "A competing library gained traction.",
                },
            ]
        }
    )
    mock_lexora_client.complete = AsyncMock(return_value=findings_json)

    service = WatchService(db_session, mock_lexora_client)
    report = await service.run_watch(conversation.id)

    assert report.summary["highest_impact"] == "medium"
    assert report.summary["requires_action"] is False

    # high impact → requires_action = True
    findings_json = json.dumps(
        {
            "findings": [
                {
                    "source_type": "api_change",
                    "impact_level": "high",
                    "title": "API deprecation",
                    "description": "Key API endpoint being removed.",
                },
            ]
        }
    )
    mock_lexora_client.complete = AsyncMock(return_value=findings_json)

    report2 = await service.run_watch(conversation.id)

    assert report2.summary["highest_impact"] == "high"
    assert report2.summary["requires_action"] is True
