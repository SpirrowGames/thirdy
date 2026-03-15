from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .common import BaseSchema


class PRStatus(StrEnum):
    CREATING = "creating"
    CREATED = "created"
    MERGED = "merged"
    CLOSED = "closed"
    FAILED = "failed"


class PullRequestRead(BaseSchema):
    id: UUID
    conversation_id: UUID
    code_id: UUID
    pr_number: int | None
    pr_url: str | None
    branch_name: str
    title: str
    description: str
    status: PRStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class PullRequestUpdate(BaseSchema):
    status: PRStatus | None = None


class PRCreateRequest(BaseSchema):
    code_id: UUID
