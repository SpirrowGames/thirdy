from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .common import BaseSchema


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageCreate(BaseSchema):
    conversation_id: UUID
    role: MessageRole
    content: str


class MessageRead(BaseSchema):
    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    created_at: datetime


class ChatSendRequest(BaseSchema):
    conversation_id: UUID | None = None
    content: str
    model: str | None = None
