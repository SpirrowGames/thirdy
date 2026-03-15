from __future__ import annotations

import asyncio
import json
import logging
import secrets
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.requests import Request
from starlette.responses import StreamingResponse

from api.db.models import Conversation, DecisionOption, DecisionPoint, User, VoteSession, Vote
from api.dependencies import get_current_user, get_db
from api.services.vote_analyzer import compute_tally, detect_split, generate_meeting_suggestion
from shared_schemas.vote import (
    MeetingSuggestion,
    VoteCast,
    VoteRead,
    VoteSessionCreate,
    VoteSessionRead,
    VoteSessionStatus,
    VoteTally,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["votes"])


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _build_session_read(session: VoteSession, options: list[DecisionOption]) -> VoteSessionRead:
    """Build VoteSessionRead from ORM objects."""
    votes = session.votes or []
    tally = compute_tally(votes, options)
    vote_reads = [
        VoteRead(
            id=v.id,
            vote_session_id=v.vote_session_id,
            option_id=v.option_id,
            voter_name=v.voter_name,
            comment=v.comment,
            created_at=v.created_at,
        )
        for v in votes
    ]
    return VoteSessionRead(
        id=session.id,
        decision_point_id=session.decision_point_id,
        status=VoteSessionStatus(session.status),
        share_token=session.share_token,
        deadline=session.deadline,
        votes=vote_reads,
        tally=tally,
        total_votes=len(votes),
        created_at=session.created_at,
    )


async def _get_user_decision_point(
    decision_id: UUID,
    user: User,
    db: AsyncSession,
) -> DecisionPoint:
    result = await db.execute(
        select(DecisionPoint)
        .join(Conversation, DecisionPoint.conversation_id == Conversation.id)
        .options(selectinload(DecisionPoint.options))
        .where(
            DecisionPoint.id == decision_id,
            Conversation.user_id == user.id,
        )
    )
    dp = result.scalar_one_or_none()
    if dp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision point not found",
        )
    return dp


# --- Authenticated endpoints ---


@router.post(
    "/decisions/{decision_id}/vote-sessions",
    response_model=VoteSessionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_vote_session(
    decision_id: UUID,
    body: VoteSessionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    dp = await _get_user_decision_point(decision_id, user, db)

    session = VoteSession(
        decision_point_id=dp.id,
        status="open",
        share_token=secrets.token_urlsafe(32),
        deadline=body.deadline,
        created_by=user.id,
    )
    db.add(session)
    await db.flush()

    # Reload with votes
    result = await db.execute(
        select(VoteSession)
        .options(selectinload(VoteSession.votes))
        .where(VoteSession.id == session.id)
    )
    session = result.scalar_one()
    await db.commit()

    return _build_session_read(session, dp.options)


@router.get(
    "/decisions/{decision_id}/vote-sessions",
    response_model=list[VoteSessionRead],
)
async def list_vote_sessions(
    decision_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    dp = await _get_user_decision_point(decision_id, user, db)

    result = await db.execute(
        select(VoteSession)
        .options(selectinload(VoteSession.votes))
        .where(VoteSession.decision_point_id == decision_id)
        .order_by(VoteSession.created_at.desc())
    )
    sessions = result.scalars().all()
    return [_build_session_read(s, dp.options) for s in sessions]


@router.post(
    "/vote-sessions/{session_id}/close",
    response_model=VoteSessionRead,
)
async def close_vote_session(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VoteSession)
        .options(selectinload(VoteSession.votes))
        .where(VoteSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Vote session not found")

    # Verify ownership via decision point
    dp_result = await db.execute(
        select(DecisionPoint)
        .join(Conversation, DecisionPoint.conversation_id == Conversation.id)
        .options(selectinload(DecisionPoint.options))
        .where(
            DecisionPoint.id == session.decision_point_id,
            Conversation.user_id == user.id,
        )
    )
    dp = dp_result.scalar_one_or_none()
    if dp is None:
        raise HTTPException(status_code=404, detail="Decision point not found")

    tally = compute_tally(session.votes, dp.options)
    is_split = detect_split(tally)
    session.status = "split" if is_split else "closed"

    await db.commit()

    # Reload
    result = await db.execute(
        select(VoteSession)
        .options(selectinload(VoteSession.votes))
        .where(VoteSession.id == session.id)
    )
    session = result.scalar_one()

    return _build_session_read(session, dp.options)


@router.get(
    "/vote-sessions/{session_id}/meeting-suggestion",
    response_model=MeetingSuggestion,
)
async def get_meeting_suggestion(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VoteSession)
        .options(selectinload(VoteSession.votes))
        .where(VoteSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Vote session not found")

    dp_result = await db.execute(
        select(DecisionPoint)
        .join(Conversation, DecisionPoint.conversation_id == Conversation.id)
        .options(selectinload(DecisionPoint.options))
        .where(
            DecisionPoint.id == session.decision_point_id,
            Conversation.user_id == user.id,
        )
    )
    dp = dp_result.scalar_one_or_none()
    if dp is None:
        raise HTTPException(status_code=404, detail="Decision point not found")

    tally = compute_tally(session.votes, dp.options)
    return generate_meeting_suggestion(dp.question, tally)


# --- Public endpoints (no auth) ---


async def _get_session_by_token(
    share_token: str,
    db: AsyncSession,
) -> tuple[VoteSession, DecisionPoint]:
    result = await db.execute(
        select(VoteSession)
        .options(selectinload(VoteSession.votes))
        .where(VoteSession.share_token == share_token)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Vote session not found")

    dp_result = await db.execute(
        select(DecisionPoint)
        .options(selectinload(DecisionPoint.options))
        .where(DecisionPoint.id == session.decision_point_id)
    )
    dp = dp_result.scalar_one()
    return session, dp


@router.get("/vote-sessions/{share_token}/public")
async def get_public_vote_session(
    share_token: str,
    db: AsyncSession = Depends(get_db),
):
    session, dp = await _get_session_by_token(share_token, db)
    session_read = _build_session_read(session, dp.options)

    return {
        "session": session_read.model_dump(mode="json"),
        "decision": {
            "id": str(dp.id),
            "question": dp.question,
            "context": dp.context,
            "recommendation": dp.recommendation,
            "options": [
                {
                    "id": str(opt.id),
                    "label": opt.label,
                    "description": opt.description,
                }
                for opt in dp.options
            ],
        },
    }


@router.post("/vote-sessions/{share_token}/votes")
async def cast_vote(
    share_token: str,
    body: VoteCast,
    db: AsyncSession = Depends(get_db),
):
    session, dp = await _get_session_by_token(share_token, db)

    if session.status != "open":
        raise HTTPException(status_code=400, detail="Voting is closed")

    # Validate option belongs to decision
    valid_option_ids = {opt.id for opt in dp.options}
    if body.option_id not in valid_option_ids:
        raise HTTPException(status_code=400, detail="Invalid option")

    # Upsert: check for existing vote by voter_token
    existing_result = await db.execute(
        select(Vote).where(
            Vote.vote_session_id == session.id,
            Vote.voter_token == body.voter_token,
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        existing.option_id = body.option_id
        existing.voter_name = body.voter_name
        existing.comment = body.comment
    else:
        vote = Vote(
            vote_session_id=session.id,
            option_id=body.option_id,
            voter_name=body.voter_name,
            voter_token=body.voter_token,
            comment=body.comment,
        )
        db.add(vote)

    await db.commit()

    # Return updated tally
    result = await db.execute(
        select(VoteSession)
        .options(selectinload(VoteSession.votes))
        .where(VoteSession.id == session.id)
    )
    session = result.scalar_one()
    tally = compute_tally(session.votes, dp.options)

    return {
        "tally": [t.model_dump(mode="json") for t in tally],
        "total_votes": len(session.votes),
    }


@router.get("/vote-sessions/{share_token}/stream")
async def stream_vote_session(
    share_token: str,
    request: Request,
):
    get_session = request.app.state.session_factory

    async def event_generator() -> AsyncGenerator[str]:
        last_count = -1
        while True:
            if await request.is_disconnected():
                break

            async with get_session() as db:
                result = await db.execute(
                    select(VoteSession)
                    .options(selectinload(VoteSession.votes))
                    .where(VoteSession.share_token == share_token)
                )
                session = result.scalar_one_or_none()
                if session is None:
                    yield _sse_event("error", {"detail": "Session not found"})
                    break

                dp_result = await db.execute(
                    select(DecisionPoint)
                    .options(selectinload(DecisionPoint.options))
                    .where(DecisionPoint.id == session.decision_point_id)
                )
                dp = dp_result.scalar_one()

                current_count = len(session.votes)
                if current_count != last_count:
                    tally = compute_tally(session.votes, dp.options)
                    yield _sse_event("tally_update", {
                        "tally": [t.model_dump(mode="json") for t in tally],
                        "total_votes": current_count,
                        "status": session.status,
                    })
                    last_count = current_count

                if session.status != "open":
                    yield _sse_event("session_closed", {"status": session.status})
                    break

            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
