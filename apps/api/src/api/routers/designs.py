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
from sqlalchemy.orm import selectinload
from starlette.responses import StreamingResponse

from api.config import settings
from api.db.models import Conversation, DecisionOption, DecisionPoint, Design, Specification, User
from api.dependencies import get_current_user, get_db, get_lexora_client
from shared_schemas import (
    DecisionPointRead,
    DesignDecomposeRequest,
    DesignRead,
    DesignUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["designs"])


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


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


async def _get_user_design(
    design_id: UUID,
    user: User,
    db: AsyncSession,
) -> Design:
    """Get a design with ownership check via its parent conversation."""
    result = await db.execute(
        select(Design)
        .join(Conversation, Design.conversation_id == Conversation.id)
        .where(
            Design.id == design_id,
            Conversation.user_id == user.id,
        )
    )
    design = result.scalar_one_or_none()
    if design is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Design not found",
        )
    return design


# --- Decompose endpoint ---


@router.post("/conversations/{conversation_id}/designs/decompose")
async def decompose_design(
    conversation_id: UUID,
    request: Request,
    body: DesignDecomposeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    lexora: LexoraClient = Depends(get_lexora_client),
):
    conversation = await _get_user_conversation(conversation_id, user, db)

    # Load and validate specification
    spec_result = await db.execute(
        select(Specification)
        .join(Conversation, Specification.conversation_id == Conversation.id)
        .where(
            Specification.id == body.spec_id,
            Specification.conversation_id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    spec = spec_result.scalar_one_or_none()
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Specification not found",
        )
    if spec.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Specification must be approved before decomposition",
        )

    # Find existing design for this spec
    design_result = await db.execute(
        select(Design)
        .where(
            Design.conversation_id == conversation_id,
            Design.specification_id == body.spec_id,
        )
        .order_by(Design.updated_at.desc())
        .limit(1)
    )
    existing_design = design_result.scalar_one_or_none()

    # Build LLM messages for design generation
    llm_messages: list[ChatMessage] = [
        ChatMessage(role="system", content=settings.localized_prompt(settings.design_decomposition_system_prompt)),
    ]

    if existing_design is not None:
        mode = "update"
        existing_design_id = existing_design.id
        llm_messages.append(
            ChatMessage(
                role="user",
                content=(
                    f"Here is the specification:\n\n{spec.content}\n\n"
                    f"Here is the existing design document:\n\n{existing_design.content}\n\n"
                    "Update the design document based on the current specification."
                ),
            )
        )
    else:
        mode = "create"
        existing_design_id = None
        llm_messages.append(
            ChatMessage(
                role="user",
                content=(
                    f"Here is the specification:\n\n{spec.content}\n\n"
                    "Generate a detailed design document from this specification."
                ),
            )
        )

    conv_id = conversation.id
    spec_id = spec.id
    spec_title = spec.title or "Untitled"
    model = body.model
    get_session = request.app.state.session_factory

    async def event_generator() -> AsyncGenerator[str]:
        yield _sse_event("decompose_started", {
            "conversation_id": str(conv_id),
            "spec_id": str(spec_id),
            "design_id": str(existing_design_id) if existing_design_id else None,
            "mode": mode,
        })

        full_content = ""
        try:
            # Phase 1: Stream design document tokens
            async for token in lexora.stream(llm_messages, model=model):
                full_content += token
                yield _sse_event("token", {"content": token})

            # Strip <think> tags from LLM output before saving
            full_content = LexoraClient._strip_think_tags(full_content)

            # Save design to DB
            title = _extract_title(full_content, f"Design - {spec_title}")

            async with get_session() as stream_db:
                if mode == "update" and existing_design_id is not None:
                    result = await stream_db.execute(
                        select(Design).where(Design.id == existing_design_id)
                    )
                    design = result.scalar_one()
                    design.content = full_content
                    design.title = title
                    await stream_db.commit()
                    await stream_db.refresh(design)
                    design_id = str(design.id)
                else:
                    design = Design(
                        conversation_id=conv_id,
                        specification_id=spec_id,
                        title=title,
                        content=full_content,
                        status="draft",
                    )
                    stream_db.add(design)
                    await stream_db.commit()
                    await stream_db.refresh(design)
                    design_id = str(design.id)

            yield _sse_event("design_saved", {
                "design_id": design_id,
                "conversation_id": str(conv_id),
            })

            # Phase 2: Detect decision points from the design
            decision_llm_messages: list[ChatMessage] = [
                ChatMessage(role="system", content=settings.localized_prompt(settings.design_decision_detection_system_prompt)),
                ChatMessage(
                    role="user",
                    content=(
                        f"Here is the design document:\n\n{full_content}\n\n"
                        "Identify all architectural decisions, trade-offs, and design choices."
                    ),
                ),
            ]

            json_model = settings.lexora_json_model or model
            raw_response = await lexora.complete(decision_llm_messages, model=json_model, json_mode=True)

            try:
                parsed = json.loads(raw_response)
            except json.JSONDecodeError:
                yield _sse_event("error", {"detail": "Failed to parse decision detection response as JSON"})
                return

            decision_points_data = parsed.get("decision_points", [])

            async with get_session() as stream_db:
                for j, dp_data in enumerate(decision_points_data):
                    dp = DecisionPoint(
                        conversation_id=conv_id,
                        design_id=design_id,
                        question=dp_data.get("question", ""),
                        context=dp_data.get("context", ""),
                        recommendation=dp_data.get("recommendation"),
                        status="pending",
                    )
                    stream_db.add(dp)
                    await stream_db.flush()

                    for k, opt_data in enumerate(dp_data.get("options", [])):
                        option = DecisionOption(
                            decision_point_id=dp.id,
                            label=opt_data.get("label", ""),
                            description=opt_data.get("description"),
                            pros=json.dumps(opt_data.get("pros", [])),
                            cons=json.dumps(opt_data.get("cons", [])),
                            sort_order=k,
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

                    dp_read = DecisionPointRead.model_validate(saved_dp)
                    yield _sse_event("decision_found", dp_read.model_dump(mode="json"))

                await stream_db.commit()

            yield _sse_event("done", {
                "design_id": design_id,
                "conversation_id": str(conv_id),
                "decision_count": len(decision_points_data),
            })
        except Exception as e:
            logger.exception("Error during design decomposition")
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
    "/conversations/{conversation_id}/designs",
    response_model=list[DesignRead],
)
async def list_designs(
    conversation_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_conversation(conversation_id, user, db)
    result = await db.execute(
        select(Design)
        .where(Design.conversation_id == conversation_id)
        .order_by(Design.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/designs/{design_id}", response_model=DesignRead)
async def get_design(
    design_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_user_design(design_id, user, db)


@router.patch("/designs/{design_id}", response_model=DesignRead)
async def update_design(
    design_id: UUID,
    body: DesignUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    design = await _get_user_design(design_id, user, db)
    if body.title is not None:
        design.title = body.title
    if body.status is not None:
        design.status = body.status.value
    if body.content is not None:
        design.content = body.content
    await db.commit()
    await db.refresh(design)
    return design


@router.delete(
    "/designs/{design_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_design(
    design_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    design = await _get_user_design(design_id, user, db)
    await db.delete(design)
    await db.commit()
