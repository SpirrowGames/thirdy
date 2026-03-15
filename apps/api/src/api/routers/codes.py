from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from llm_client import ChatMessage, LexoraClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from api.config import settings
from api.db.models import Conversation, Design, GeneratedCode, GeneratedTask, Specification, User
from api.dependencies import get_current_user, get_db, get_lexora_client
from shared_schemas import (
    CodeGenerateRequest,
    GeneratedCodeRead,
    GeneratedCodeUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["codes"])


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


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


async def _get_user_code(
    code_id: UUID,
    user: User,
    db: AsyncSession,
) -> GeneratedCode:
    result = await db.execute(
        select(GeneratedCode)
        .join(Conversation, GeneratedCode.conversation_id == Conversation.id)
        .where(
            GeneratedCode.id == code_id,
            Conversation.user_id == user.id,
        )
    )
    code = result.scalar_one_or_none()
    if code is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated code not found",
        )
    return code


# --- Generate endpoint ---


@router.post("/conversations/{conversation_id}/codes/generate")
async def generate_code(
    conversation_id: UUID,
    request: Request,
    body: CodeGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    lexora: LexoraClient = Depends(get_lexora_client),
):
    conversation = await _get_user_conversation(conversation_id, user, db)

    # Load task
    task_result = await db.execute(
        select(GeneratedTask)
        .join(Conversation, GeneratedTask.conversation_id == Conversation.id)
        .where(
            GeneratedTask.id == body.task_id,
            GeneratedTask.conversation_id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    task = task_result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # Load design (parent of task)
    design_result = await db.execute(
        select(Design).where(Design.id == task.design_id)
    )
    design = design_result.scalar_one_or_none()
    if design is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Design not found",
        )

    # Load spec (parent of design)
    spec_result = await db.execute(
        select(Specification).where(Specification.id == design.specification_id)
    )
    spec = spec_result.scalar_one_or_none()
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Specification not found",
        )

    conv_id = conversation.id
    task_id = task.id
    task_title = task.title
    task_description = task.description
    design_content = design.content
    spec_content = spec.content
    model = body.model
    get_session = request.app.state.session_factory

    async def event_generator() -> AsyncGenerator[str]:
        yield _sse_event("generation_started", {
            "conversation_id": str(conv_id),
            "task_id": str(task_id),
        })

        try:
            user_content = (
                f"## Specification\n\n{spec_content}\n\n"
                f"## Design Document\n\n{design_content}\n\n"
                f"## Task\n\n**{task_title}**\n\n{task_description}\n\n"
                "Generate the implementation code and tests for this task."
            )

            llm_messages: list[ChatMessage] = [
                ChatMessage(role="system", content=settings.code_generation_system_prompt),
                ChatMessage(role="user", content=user_content),
            ]

            accumulated = ""
            async for token in lexora.stream(llm_messages, model=model):
                accumulated += token
                yield _sse_event("token", {"content": token})

            # Save to DB
            async with get_session() as stream_db:
                code = GeneratedCode(
                    conversation_id=conv_id,
                    task_id=task_id,
                    content=accumulated,
                    status="draft",
                )
                stream_db.add(code)
                await stream_db.commit()
                await stream_db.refresh(code)

                code_read = GeneratedCodeRead.model_validate(code)
                yield _sse_event("done", code_read.model_dump(mode="json"))

        except Exception as e:
            logger.exception("Error during code generation")
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
    "/conversations/{conversation_id}/codes",
    response_model=list[GeneratedCodeRead],
)
async def list_codes(
    conversation_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_conversation(conversation_id, user, db)
    result = await db.execute(
        select(GeneratedCode)
        .where(GeneratedCode.conversation_id == conversation_id)
        .order_by(GeneratedCode.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/codes/{code_id}", response_model=GeneratedCodeRead)
async def get_code(
    code_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_user_code(code_id, user, db)


@router.patch("/codes/{code_id}", response_model=GeneratedCodeRead)
async def update_code(
    code_id: UUID,
    body: GeneratedCodeUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    code = await _get_user_code(code_id, user, db)
    if body.content is not None:
        code.content = body.content
    if body.status is not None:
        code.status = body.status.value
    await db.commit()
    await db.refresh(code)
    return code


@router.delete(
    "/codes/{code_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_code(
    code_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    code = await _get_user_code(code_id, user, db)
    await db.delete(code)
    await db.commit()
