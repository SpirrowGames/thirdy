from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from llm_client import ChatMessage, LexoraClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from api.config import settings
from api.db.models import Conversation, Message, Specification, User
from api.dependencies import get_current_user, get_db, get_lexora_client
from shared_schemas import SpecExtractRequest, SpecRead, SpecUpdate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["specifications"])


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _format_messages(messages: list[Message]) -> str:
    """Format messages as [role] content for LLM context."""
    parts = []
    for msg in messages:
        parts.append(f"[{msg.role}] {msg.content}")
    return "\n\n".join(parts)


def _extract_title(markdown: str, fallback: str) -> str:
    """Extract the first # heading from markdown, or use fallback."""
    match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return fallback


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


async def _get_user_specification(
    spec_id: UUID,
    user: User,
    db: AsyncSession,
) -> Specification:
    """Get a specification with ownership check via its parent conversation."""
    result = await db.execute(
        select(Specification)
        .join(Conversation, Specification.conversation_id == Conversation.id)
        .where(
            Specification.id == spec_id,
            Conversation.user_id == user.id,
        )
    )
    spec = result.scalar_one_or_none()
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Specification not found",
        )
    return spec


# --- Extract endpoint ---


@router.post("/conversations/{conversation_id}/specifications/extract")
async def extract_specification(
    conversation_id: UUID,
    request: Request,
    body: SpecExtractRequest | None = None,
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

    # Find existing spec (most recently updated)
    spec_result = await db.execute(
        select(Specification)
        .where(Specification.conversation_id == conversation_id)
        .order_by(Specification.updated_at.desc())
        .limit(1)
    )
    existing_spec = spec_result.scalar_one_or_none()

    # Build LLM messages
    formatted = _format_messages(messages)
    llm_messages: list[ChatMessage] = [
        ChatMessage(role="system", content=settings.localized_prompt(settings.spec_extraction_system_prompt)),
    ]

    if existing_spec is not None:
        mode = "update"
        existing_spec_id = existing_spec.id
        llm_messages.append(
            ChatMessage(
                role="user",
                content=(
                    f"Here is the existing specification:\n\n{existing_spec.content}\n\n"
                    f"Here is the conversation:\n\n{formatted}\n\n"
                    "Update the specification based on the latest conversation."
                ),
            )
        )
    else:
        mode = "create"
        existing_spec_id = None
        llm_messages.append(
            ChatMessage(
                role="user",
                content=(
                    f"Here is the conversation:\n\n{formatted}\n\n"
                    "Generate a specification document from this conversation."
                ),
            )
        )

    conv_id = conversation.id
    conv_title = conversation.title or "Untitled"
    model = body.model if body else None
    get_session = request.app.state.session_factory

    async def event_generator() -> AsyncGenerator[str]:
        yield _sse_event("extraction_started", {
            "conversation_id": str(conv_id),
            "spec_id": str(existing_spec_id) if existing_spec_id else None,
            "mode": mode,
        })

        full_content = ""
        try:
            async for token in lexora.stream(llm_messages, model=model):
                full_content += token
                yield _sse_event("token", {"content": token})

            # Strip <think> tags from LLM output before saving
            from llm_client import LexoraClient
            full_content = LexoraClient._strip_think_tags(full_content)

            # Save to DB in a new session
            title = _extract_title(full_content, f"Specification - {conv_title}")

            async with get_session() as stream_db:
                if mode == "update" and existing_spec_id is not None:
                    # Update existing spec
                    result = await stream_db.execute(
                        select(Specification).where(
                            Specification.id == existing_spec_id,
                        )
                    )
                    spec = result.scalar_one()
                    spec.content = full_content
                    spec.title = title
                    await stream_db.commit()
                    await stream_db.refresh(spec)
                    spec_id = str(spec.id)
                else:
                    # Create new spec
                    spec = Specification(
                        conversation_id=conv_id,
                        title=title,
                        content=full_content,
                        status="draft",
                    )
                    stream_db.add(spec)
                    await stream_db.commit()
                    await stream_db.refresh(spec)
                    spec_id = str(spec.id)

            yield _sse_event("done", {
                "spec_id": spec_id,
                "conversation_id": str(conv_id),
            })
        except Exception as e:
            logger.exception("Error during specification extraction")
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
    "/conversations/{conversation_id}/specifications",
    response_model=list[SpecRead],
)
async def list_specifications(
    conversation_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_conversation(conversation_id, user, db)
    result = await db.execute(
        select(Specification)
        .where(Specification.conversation_id == conversation_id)
        .order_by(Specification.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/specifications/{spec_id}", response_model=SpecRead)
async def get_specification(
    spec_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_user_specification(spec_id, user, db)


@router.patch("/specifications/{spec_id}", response_model=SpecRead)
async def update_specification(
    spec_id: UUID,
    body: SpecUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    spec = await _get_user_specification(spec_id, user, db)
    if body.title is not None:
        spec.title = body.title
    if body.status is not None:
        spec.status = body.status.value
    if body.content is not None:
        spec.content = body.content
    await db.commit()
    await db.refresh(spec)
    return spec


@router.delete(
    "/specifications/{spec_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_specification(
    spec_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    spec = await _get_user_specification(spec_id, user, db)
    await db.delete(spec)
    await db.commit()
