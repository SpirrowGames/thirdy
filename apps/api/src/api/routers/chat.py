from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from llm_client import ChatMessage, LexoraClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from api.config import settings
from api.db.models import Conversation, Message, User
from api.dependencies import get_current_user, get_db, get_lexora_client
from shared_schemas import ChatSendRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


from fastapi import Request


@router.post("/chat")
async def chat(
    body: ChatSendRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    lexora: LexoraClient = Depends(get_lexora_client),
):
    # Resolve or create conversation
    if body.conversation_id is not None:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == body.conversation_id,
                Conversation.user_id == user.id,
            )
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
    else:
        conversation = Conversation(
            user_id=user.id,
            title=body.content[:80],
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

    # Save user message
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=body.content,
    )
    db.add(user_message)
    await db.commit()
    await db.refresh(user_message)

    # Load conversation history
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
        .limit(settings.chat_history_limit)
    )
    history_messages = history_result.scalars().all()

    # Build LLM messages
    llm_messages: list[ChatMessage] = [
        ChatMessage(role="system", content=settings.chat_system_prompt),
    ]
    for msg in history_messages:
        llm_messages.append(ChatMessage(role=msg.role, content=msg.content))

    conversation_id = conversation.id
    user_message_id = user_message.id
    model = body.model
    get_session = request.app.state.session_factory

    async def event_generator() -> AsyncGenerator[str]:
        # Send message_saved event
        yield _sse_event("message_saved", {
            "conversation_id": str(conversation_id),
            "message_id": str(user_message_id),
        })

        full_response = ""
        try:
            async for token in lexora.stream(llm_messages, model=model):
                full_response += token
                yield _sse_event("token", {"content": token})

            # Save assistant message in a new DB session
            async with get_session() as stream_db:
                assistant_message = Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=full_response,
                )
                stream_db.add(assistant_message)
                await stream_db.commit()
                await stream_db.refresh(assistant_message)
                assistant_message_id = str(assistant_message.id)

            yield _sse_event("done", {
                "conversation_id": str(conversation_id),
                "message_id": assistant_message_id,
            })
        except Exception as e:
            logger.exception("Error during LLM streaming")
            yield _sse_event("error", {"detail": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
