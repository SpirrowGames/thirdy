from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .common import BaseSchema


class CodeStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class GeneratedCodeRead(BaseSchema):
    id: UUID
    conversation_id: UUID
    task_id: UUID
    content: str
    status: CodeStatus
    created_at: datetime
    updated_at: datetime


class GeneratedCodeUpdate(BaseSchema):
    content: str | None = None
    status: CodeStatus | None = None


class CodeGenerateRequest(BaseSchema):
    task_id: UUID
    model: str | None = None
