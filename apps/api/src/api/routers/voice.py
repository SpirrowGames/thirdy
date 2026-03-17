from __future__ import annotations

import json
import logging
import tempfile
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from api.config import settings
from api.db.models import Conversation, Message, User
from api.db.models.voice_transcript import VoiceTranscript
from api.dependencies import get_current_user, get_db, get_whisper_service
from api.services.whisper_service import WhisperService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voice"])

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/conversations/{conversation_id}/voice/transcribe")
async def transcribe_voice(
    conversation_id: UUID,
    request: Request,
    file: UploadFile = File(...),
    language: str | None = Form(None),
    add_to_conversation: bool = Form(True),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    whisper: WhisperService = Depends(get_whisper_service),
):
    # Verify conversation ownership
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

    # Read and validate file size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB",
        )

    # Write to temp file
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}")
    tmp.write(content)
    tmp.flush()
    tmp_path = tmp.name
    tmp.close()

    # Create VoiceTranscript record
    transcript_record = VoiceTranscript(
        conversation_id=conversation_id,
        filename=file.filename or "unknown",
        status="processing",
    )
    db.add(transcript_record)
    await db.commit()
    await db.refresh(transcript_record)

    transcript_id = transcript_record.id
    get_session = request.app.state.session_factory
    lexora = request.app.state.lexora_client

    async def event_generator() -> AsyncGenerator[str]:
        import os
        try:
            yield _sse_event("transcription_started", {
                "transcript_id": str(transcript_id),
                "filename": file.filename or "unknown",
            })

            # Run whisper transcription
            result = await whisper.transcribe(tmp_path, language=language if language else None)

            # Stream segments
            segments_data = []
            for i, seg in enumerate(result.segments):
                seg_dict = {"start": seg.start, "end": seg.end, "text": seg.text}
                segments_data.append(seg_dict)
                yield _sse_event("segment", {"index": i, **seg_dict})

            full_text = " ".join(seg.text for seg in result.segments)

            yield _sse_event("transcription_complete", {
                "transcript_id": str(transcript_id),
                "full_text": full_text,
                "language": result.language,
                "duration": result.duration,
            })

            # Update transcript record with results
            async with get_session() as stream_db:
                tr = await stream_db.get(VoiceTranscript, transcript_id)
                tr.transcript = full_text
                tr.segments = segments_data
                tr.language = result.language
                tr.duration_seconds = result.duration
                await stream_db.commit()

            # Classify with LLM
            yield _sse_event("classification_started", {})

            from llm_client import ChatMessage
            classify_messages = [
                ChatMessage(role="system", content=settings.localized_prompt(settings.voice_classification_system_prompt)),
                ChatMessage(role="user", content=full_text),
            ]

            classification_text = await lexora.complete(classify_messages, json_mode=True)

            # Parse classification JSON
            classification = None
            try:
                classification = json.loads(classification_text)
            except json.JSONDecodeError:
                logger.warning("Failed to parse classification JSON: %s", classification_text[:200])

            yield _sse_event("classification_complete", {
                "classification": classification,
            })

            # Save classification
            async with get_session() as stream_db:
                tr = await stream_db.get(VoiceTranscript, transcript_id)
                tr.classification = classification
                tr.status = "completed"
                await stream_db.commit()

            # Add transcript to conversation messages if requested
            message_ids = []
            if add_to_conversation and full_text.strip():
                async with get_session() as stream_db:
                    msg = Message(
                        conversation_id=conversation_id,
                        role="user",
                        content=f"[Voice Transcript: {file.filename}]\n\n{full_text}",
                    )
                    stream_db.add(msg)
                    await stream_db.commit()
                    await stream_db.refresh(msg)
                    message_ids.append(str(msg.id))

                yield _sse_event("messages_added", {"message_ids": message_ids})

            yield _sse_event("done", {"transcript_id": str(transcript_id)})

        except Exception as e:
            logger.exception("Error during voice transcription")
            # Update status to failed
            try:
                async with get_session() as stream_db:
                    tr = await stream_db.get(VoiceTranscript, transcript_id)
                    if tr:
                        tr.status = "failed"
                        tr.error_message = str(e)
                        await stream_db.commit()
            except Exception:
                logger.exception("Failed to update transcript status")

            yield _sse_event("error", {"detail": str(e)})
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations/{conversation_id}/voice/transcripts")
async def list_transcripts(
    conversation_id: UUID,
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

    result = await db.execute(
        select(VoiceTranscript)
        .where(VoiceTranscript.conversation_id == conversation_id)
        .order_by(VoiceTranscript.created_at.desc())
    )
    transcripts = result.scalars().all()
    return [_build_transcript_read(t) for t in transcripts]


@router.get("/voice/transcripts/{transcript_id}")
async def get_transcript(
    transcript_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    transcript = await _get_user_transcript(db, transcript_id, user.id)
    return _build_transcript_read(transcript)


@router.delete("/voice/transcripts/{transcript_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transcript(
    transcript_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    transcript = await _get_user_transcript(db, transcript_id, user.id)
    await db.delete(transcript)
    await db.commit()


async def _get_user_transcript(db: AsyncSession, transcript_id: UUID, user_id: UUID) -> VoiceTranscript:
    result = await db.execute(
        select(VoiceTranscript)
        .join(Conversation)
        .where(
            VoiceTranscript.id == transcript_id,
            Conversation.user_id == user_id,
        )
    )
    transcript = result.scalar_one_or_none()
    if transcript is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found",
        )
    return transcript


def _build_transcript_read(t: VoiceTranscript) -> dict:
    return {
        "id": str(t.id),
        "conversation_id": str(t.conversation_id),
        "filename": t.filename,
        "duration_seconds": t.duration_seconds,
        "language": t.language,
        "transcript": t.transcript,
        "segments": t.segments or [],
        "classification": t.classification,
        "status": t.status,
        "error_message": t.error_message,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
    }
