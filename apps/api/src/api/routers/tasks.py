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
from api.db.models import Conversation, Design, GeneratedTask, User
from api.dependencies import get_current_user, get_db, get_lexora_client
from shared_schemas import (
    GeneratedTaskRead,
    GeneratedTaskUpdate,
    TaskGenerateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tasks"])


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


async def _get_user_task(
    task_id: UUID,
    user: User,
    db: AsyncSession,
) -> GeneratedTask:
    result = await db.execute(
        select(GeneratedTask)
        .join(Conversation, GeneratedTask.conversation_id == Conversation.id)
        .where(
            GeneratedTask.id == task_id,
            Conversation.user_id == user.id,
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return task


# --- Generate endpoint ---


@router.post("/conversations/{conversation_id}/tasks/generate")
async def generate_tasks(
    conversation_id: UUID,
    request: Request,
    body: TaskGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    lexora: LexoraClient = Depends(get_lexora_client),
):
    conversation = await _get_user_conversation(conversation_id, user, db)

    # Load and validate design
    design_result = await db.execute(
        select(Design)
        .join(Conversation, Design.conversation_id == Conversation.id)
        .where(
            Design.id == body.design_id,
            Design.conversation_id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    design = design_result.scalar_one_or_none()
    if design is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Design not found",
        )
    if design.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Design must be approved before task generation",
        )

    conv_id = conversation.id
    design_id = design.id
    design_content = design.content
    model = body.model
    get_session = request.app.state.session_factory

    async def event_generator() -> AsyncGenerator[str]:
        yield _sse_event("generation_started", {
            "conversation_id": str(conv_id),
            "design_id": str(design_id),
        })

        try:
            llm_messages: list[ChatMessage] = [
                ChatMessage(role="system", content=settings.task_generation_system_prompt),
                ChatMessage(
                    role="user",
                    content=(
                        f"Here is the design document:\n\n{design_content}\n\n"
                        "Generate implementation tasks with dependencies."
                    ),
                ),
            ]

            raw_response = await lexora.complete(llm_messages, model=model)

            try:
                parsed = json.loads(raw_response)
            except json.JSONDecodeError:
                yield _sse_event("error", {"detail": "Failed to parse task generation response as JSON"})
                return

            tasks_data = parsed.get("tasks", [])

            # First pass: save tasks and build title→UUID map
            title_to_id: dict[str, str] = {}

            async with get_session() as stream_db:
                for i, task_data in enumerate(tasks_data):
                    task = GeneratedTask(
                        conversation_id=conv_id,
                        design_id=design_id,
                        title=task_data.get("title", ""),
                        description=task_data.get("description", ""),
                        priority=task_data.get("priority", "medium"),
                        status="pending",
                        dependencies="[]",
                        sort_order=i,
                    )
                    stream_db.add(task)
                    await stream_db.flush()
                    title_to_id[task.title] = str(task.id)

                # Second pass: resolve dependencies (title → UUID)
                for i, task_data in enumerate(tasks_data):
                    title = task_data.get("title", "")
                    dep_titles = task_data.get("dependencies", [])
                    dep_ids = [title_to_id[t] for t in dep_titles if t in title_to_id]

                    task_id = title_to_id[title]
                    result = await stream_db.execute(
                        select(GeneratedTask).where(GeneratedTask.id == task_id)
                    )
                    task = result.scalar_one()
                    task.dependencies = json.dumps(dep_ids)
                    await stream_db.flush()

                    task_read = GeneratedTaskRead.model_validate(task)
                    yield _sse_event("task_found", task_read.model_dump(mode="json"))

                await stream_db.commit()

            yield _sse_event("done", {
                "conversation_id": str(conv_id),
                "design_id": str(design_id),
                "task_count": len(tasks_data),
            })
        except Exception as e:
            logger.exception("Error during task generation")
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
    "/conversations/{conversation_id}/tasks",
    response_model=list[GeneratedTaskRead],
)
async def list_tasks(
    conversation_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_conversation(conversation_id, user, db)
    result = await db.execute(
        select(GeneratedTask)
        .where(GeneratedTask.conversation_id == conversation_id)
        .order_by(GeneratedTask.sort_order.asc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/tasks/{task_id}", response_model=GeneratedTaskRead)
async def get_task(
    task_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_user_task(task_id, user, db)


@router.patch("/tasks/{task_id}", response_model=GeneratedTaskRead)
async def update_task(
    task_id: UUID,
    body: GeneratedTaskUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _get_user_task(task_id, user, db)
    if body.title is not None:
        task.title = body.title
    if body.description is not None:
        task.description = body.description
    if body.priority is not None:
        task.priority = body.priority.value
    if body.status is not None:
        task.status = body.status.value
    await db.commit()
    await db.refresh(task)
    return task


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_task(
    task_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _get_user_task(task_id, user, db)
    await db.delete(task)
    await db.commit()
