from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .common import BaseSchema


class IssueStatus(StrEnum):
    DRAFT = "draft"
    CREATING = "creating"
    CREATED = "created"
    CLOSED = "closed"
    FAILED = "failed"


class GitHubIssueRead(BaseSchema):
    id: UUID
    conversation_id: UUID
    original_text: str
    title: str
    body: str
    labels: list[str]
    issue_number: int | None
    issue_url: str | None
    status: IssueStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class GitHubIssueUpdate(BaseSchema):
    title: str | None = None
    body: str | None = None
    labels: list[str] | None = None
    status: IssueStatus | None = None


class IssueStructureRequest(BaseSchema):
    text: str
    language: str | None = None


class IssueCreateRequest(BaseSchema):
    issue_id: UUID
