from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .common import BaseSchema


class DesignStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"


class DesignRead(BaseSchema):
    id: UUID
    conversation_id: UUID
    specification_id: UUID
    title: str
    content: str
    status: DesignStatus
    created_at: datetime
    updated_at: datetime


class DesignUpdate(BaseSchema):
    title: str | None = None
    status: DesignStatus | None = None
    content: str | None = None


class DesignDecomposeRequest(BaseSchema):
    spec_id: UUID
    model: str | None = None
