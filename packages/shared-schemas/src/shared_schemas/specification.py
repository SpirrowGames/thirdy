from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .common import BaseSchema


class SpecStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"


class SpecCreate(BaseSchema):
    conversation_id: UUID
    title: str
    content: str


class SpecRead(BaseSchema):
    id: UUID
    conversation_id: UUID
    title: str
    content: str
    status: SpecStatus
    created_at: datetime
    updated_at: datetime
