from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from llm_client import ChatMessage, LexoraClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.responses import StreamingResponse

from api.config import settings
from api.db.models import Conversation, DecisionOption, DecisionPoint, Message, User
from api.dependencies import get_current_user, get_db, get_lexora_client
from shared_schemas import DecisionDetectRequest, DecisionPointRead, DecisionPointUpdate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["decisions"])


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _format_messages(messages: list[Message]) -> str:
    parts = []
    for msg in messages:
        parts.append(f"[{msg.role}] {msg.content}")
    return "\n\n".join(parts)


async def _get_user_conversation(
    conversation_id: UUID,
    user: User,
    db: AsyncSession,
) -> Conversation:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return conversation


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


# --- Detect endpoint ---


@router.post("/conversations/{conversation_id}/decisions/detect")
async def detect_decisions(
    conversation_id: UUID,
    request: Request,
    body: DecisionDetectRequest | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    lexora: LexoraClient = Depends(get_lexora_client),
):
    conversation = await _get_user_conversation(conversation_id, user, db)

    # Load conversation messages
    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(settings.chat_history_limit)
    )
    messages = msg_result.scalars().all()

    # Build LLM messages
    formatted = _format_messages(messages)
    llm_messages: list[ChatMessage] = [
        ChatMessage(role="system", content=settings.localized_prompt(settings.decision_detection_system_prompt)),
        ChatMessage(
            role="user",
            content=(
                f"Here is the conversation:\n\n{formatted}\n\n"
                "Identify all decision points, ambiguities, and unresolved questions."
            ),
        ),
    ]

    conv_id = conversation.id
    model = body.model if body else None
    get_session = request.app.state.session_factory

    async def event_generator() -> AsyncGenerator[str]:
        yield _sse_event("detection_started", {"conversation_id": str(conv_id)})

        try:
            # Non-streaming LLM call for structured JSON output
            json_model = settings.lexora_json_model or model
            raw_response = await lexora.complete(llm_messages, model=json_model, json_mode=True)

            # Parse JSON response
            try:
                parsed = json.loads(raw_response)
            except json.JSONDecodeError:
                yield _sse_event("error", {"detail": "Failed to parse LLM response as JSON"})
                return

            decision_points_data = parsed.get("decision_points", [])
            saved_ids: list[str] = []

            async with get_session() as stream_db:
                for i, dp_data in enumerate(decision_points_data):
                    dp = DecisionPoint(
                        conversation_id=conv_id,
                        question=dp_data.get("question", ""),
                        context=dp_data.get("context", ""),
                        recommendation=dp_data.get("recommendation"),
                        status="pending",
                    )
                    stream_db.add(dp)
                    await stream_db.flush()

                    for j, opt_data in enumerate(dp_data.get("options", [])):
                        option = DecisionOption(
                            decision_point_id=dp.id,
                            label=opt_data.get("label", ""),
                            description=opt_data.get("description"),
                            pros=json.dumps(opt_data.get("pros", [])),
                            cons=json.dumps(opt_data.get("cons", [])),
                            sort_order=j,
                        )
                        stream_db.add(option)

                    await stream_db.flush()

                    # Reload with options for serialization
                    result = await stream_db.execute(
                        select(DecisionPoint)
                        .options(selectinload(DecisionPoint.options))
                        .where(DecisionPoint.id == dp.id)
                    )
                    saved_dp = result.scalar_one()
                    saved_ids.append(str(saved_dp.id))

                    dp_read = DecisionPointRead.model_validate(saved_dp)
                    yield _sse_event("decision_found", dp_read.model_dump(mode="json"))

                await stream_db.commit()

            yield _sse_event("done", {
                "conversation_id": str(conv_id),
                "count": len(saved_ids),
                "decision_point_ids": saved_ids,
            })
        except Exception as e:
            logger.exception("Error during decision detection")
            yield _sse_event("error", {"detail": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# --- CRUD endpoints ---


@router.get(
    "/conversations/{conversation_id}/decisions",
    response_model=list[DecisionPointRead],
)
async def list_decisions(
    conversation_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_conversation(conversation_id, user, db)
    result = await db.execute(
        select(DecisionPoint)
        .options(selectinload(DecisionPoint.options))
        .where(DecisionPoint.conversation_id == conversation_id)
        .order_by(DecisionPoint.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/decisions/{decision_id}", response_model=DecisionPointRead)
async def get_decision(
    decision_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_user_decision_point(decision_id, user, db)


@router.patch("/decisions/{decision_id}", response_model=DecisionPointRead)
async def update_decision(
    decision_id: UUID,
    body: DecisionPointUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    dp = await _get_user_decision_point(decision_id, user, db)
    if body.status is not None:
        dp.status = body.status.value
    if body.resolved_option_id is not None:
        dp.resolved_option_id = body.resolved_option_id
    if body.resolution_note is not None:
        dp.resolution_note = body.resolution_note
    await db.commit()
    # Reload with options eagerly loaded
    result = await db.execute(
        select(DecisionPoint)
        .options(selectinload(DecisionPoint.options))
        .where(DecisionPoint.id == dp.id)
    )
    return result.scalar_one()


@router.delete(
    "/decisions/{decision_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_decision(
    decision_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    dp = await _get_user_decision_point(decision_id, user, db)
    await db.delete(dp)
    await db.commit()
