from datetime import datetime
from enum import Enum
from uuid import UUID

from .common import BaseSchema


class VoiceTranscriptStatus(str, Enum):
    processing = "processing"
    completed = "completed"
    failed = "failed"


class TranscriptSegment(BaseSchema):
    start: float
    end: float
    text: str


class VoiceTranscriptRead(BaseSchema):
    id: UUID
    conversation_id: UUID
    filename: str
    duration_seconds: float | None
    language: str | None
    transcript: str
    segments: list[TranscriptSegment]
    classification: dict | None
    status: VoiceTranscriptStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class VoiceTranscribeRequest(BaseSchema):
    language: str | None = None
    add_to_conversation: bool = True
