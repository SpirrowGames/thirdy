from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from llm_client import ChatMessage, LexoraClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from api.config import settings
from api.db.models import Conversation, User
from api.db.models.github_issue import GitHubIssue
from api.dependencies import get_current_user, get_db, get_lexora_client
from api.services.github import GitHubClient, GitHubError
from shared_schemas import IssueCreateRequest, IssueStructureRequest, GitHubIssueUpdate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["github-issues"])


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ---------------------------------------------------------------------------
# POST /conversations/{id}/issues/structure  (SSE)
# Natural language → structured issue via LLM
# ---------------------------------------------------------------------------
@router.post("/conversations/{conversation_id}/issues/structure")
async def structure_issue(
    conversation_id: UUID,
    body: IssueStructureRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    lexora: LexoraClient = Depends(get_lexora_client),
):
    # Verify conversation ownership
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    text = body.text.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text is required",
        )

    conv_id = conversation_id
    get_session = request.app.state.session_factory

    async def event_generator() -> AsyncGenerator[str]:
        yield _sse_event("structuring_started", {"conversation_id": str(conv_id)})

        try:
            # Call LLM to structure the natural language into an issue
            messages = [
                ChatMessage(role="system", content=settings.localized_prompt(settings.issue_structuring_system_prompt)),
                ChatMessage(role="user", content=text),
            ]

            json_model = settings.lexora_json_model or None
            full_response = await lexora.complete(messages, model=json_model, json_mode=True)

            # Parse structured result
            structured = None
            try:
                structured = json.loads(full_response)
            except json.JSONDecodeError:
                logger.warning("Failed to parse issue structure JSON: %s", full_response[:200])
                yield _sse_event("error", {"detail": "Failed to parse LLM response as JSON"})
                return

            title = structured.get("title", "Untitled Issue")
            body_md = structured.get("body", "")
            labels = structured.get("labels", [])

            # Save as draft GitHubIssue
            async with get_session() as stream_db:
                issue = GitHubIssue(
                    conversation_id=conv_id,
                    original_text=text,
                    title=title,
                    body=body_md,
                    labels=labels,
                    status="draft",
                )
                stream_db.add(issue)
                await stream_db.commit()
                await stream_db.refresh(issue)
                issue_id = str(issue.id)

            yield _sse_event("structured", {
                "issue_id": issue_id,
                "title": title,
                "body": body_md,
                "labels": labels,
            })

            yield _sse_event("done", {"issue_id": issue_id})

        except Exception as e:
            logger.exception("Error structuring issue")
            yield _sse_event("error", {"detail": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# POST /conversations/{id}/issues/create  (SSE)
# Publish a draft issue to GitHub
# ---------------------------------------------------------------------------
@router.post("/conversations/{conversation_id}/issues/create")
async def create_github_issue(
    conversation_id: UUID,
    body: IssueCreateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify conversation ownership
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Get the draft issue
    issue = await db.get(GitHubIssue, body.issue_id)
    if issue is None or issue.conversation_id != conversation_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found",
        )

    if not settings.github_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub token not configured",
        )

    issue_id = issue.id
    title = issue.title
    issue_body = issue.body
    labels = issue.labels or []
    get_session = request.app.state.session_factory

    async def event_generator() -> AsyncGenerator[str]:
        yield _sse_event("issue_creating", {"issue_id": str(issue_id)})

        try:
            # Update status to creating
            async with get_session() as stream_db:
                rec = await stream_db.get(GitHubIssue, issue_id)
                rec.status = "creating"
                await stream_db.commit()

            # Create issue on GitHub
            async with httpx.AsyncClient(timeout=30.0) as http:
                gh = GitHubClient(
                    token=settings.github_token,
                    owner=settings.github_owner,
                    repo=settings.github_repo,
                    http=http,
                )
                gh_issue = await gh.create_issue(
                    title=title,
                    body=issue_body,
                    labels=labels if labels else None,
                )

            issue_number = gh_issue["number"]
            issue_url = gh_issue["html_url"]

            yield _sse_event("issue_created", {
                "issue_id": str(issue_id),
                "issue_number": issue_number,
                "issue_url": issue_url,
            })

            # Update record with GitHub data
            async with get_session() as stream_db:
                rec = await stream_db.get(GitHubIssue, issue_id)
                rec.issue_number = issue_number
                rec.issue_url = issue_url
                rec.status = "created"
                await stream_db.commit()

            yield _sse_event("done", {
                "issue_id": str(issue_id),
                "issue_number": issue_number,
                "issue_url": issue_url,
            })

        except GitHubError as e:
            logger.exception("GitHub API error creating issue")
            async with get_session() as stream_db:
                rec = await stream_db.get(GitHubIssue, issue_id)
                if rec:
                    rec.status = "failed"
                    rec.error_message = str(e)
                    await stream_db.commit()
            yield _sse_event("error", {"detail": str(e)})

        except Exception as e:
            logger.exception("Error creating GitHub issue")
            async with get_session() as stream_db:
                rec = await stream_db.get(GitHubIssue, issue_id)
                if rec:
                    rec.status = "failed"
                    rec.error_message = str(e)
                    await stream_db.commit()
            yield _sse_event("error", {"detail": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# GET /conversations/{id}/issues — list issues
# ---------------------------------------------------------------------------
@router.get("/conversations/{conversation_id}/issues")
async def list_issues(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    result = await db.execute(
        select(GitHubIssue)
        .where(GitHubIssue.conversation_id == conversation_id)
        .order_by(GitHubIssue.created_at.desc())
    )
    issues = result.scalars().all()
    return [_build_issue_read(i) for i in issues]


# ---------------------------------------------------------------------------
# GET /issues/{id} — single issue
# ---------------------------------------------------------------------------
@router.get("/issues/{issue_id}")
async def get_issue(
    issue_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    issue = await _get_user_issue(db, issue_id, user.id)
    return _build_issue_read(issue)


# ---------------------------------------------------------------------------
# PATCH /issues/{id} — update draft issue
# ---------------------------------------------------------------------------
@router.patch("/issues/{issue_id}")
async def update_issue(
    issue_id: UUID,
    body: GitHubIssueUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    issue = await _get_user_issue(db, issue_id, user.id)

    if body.title is not None:
        issue.title = body.title
    if body.body is not None:
        issue.body = body.body
    if body.labels is not None:
        issue.labels = body.labels
    if body.status is not None:
        issue.status = body.status

    await db.commit()
    await db.refresh(issue)
    return _build_issue_read(issue)


# ---------------------------------------------------------------------------
# DELETE /issues/{id} — delete issue
# ---------------------------------------------------------------------------
@router.delete("/issues/{issue_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_issue(
    issue_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    issue = await _get_user_issue(db, issue_id, user.id)
    await db.delete(issue)
    await db.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _get_user_issue(db: AsyncSession, issue_id: UUID, user_id: UUID) -> GitHubIssue:
    result = await db.execute(
        select(GitHubIssue)
        .join(Conversation)
        .where(
            GitHubIssue.id == issue_id,
            Conversation.user_id == user_id,
        )
    )
    issue = result.scalar_one_or_none()
    if issue is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found",
        )
    return issue


def _build_issue_read(i: GitHubIssue) -> dict:
    return {
        "id": str(i.id),
        "conversation_id": str(i.conversation_id),
        "original_text": i.original_text,
        "title": i.title,
        "body": i.body,
        "labels": i.labels or [],
        "issue_number": i.issue_number,
        "issue_url": i.issue_url,
        "status": i.status,
        "error_message": i.error_message,
        "created_at": i.created_at.isoformat(),
        "updated_at": i.updated_at.isoformat(),
    }
