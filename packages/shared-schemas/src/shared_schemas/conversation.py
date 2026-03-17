from datetime import datetime
from uuid import UUID

from .common import BaseSchema


class ConversationCreate(BaseSchema):
    title: str | None = None
    github_repo: str | None = None


class ConversationUpdate(BaseSchema):
    title: str | None = None
    github_repo: str | None = None


class ConversationRead(BaseSchema):
    id: UUID
    user_id: UUID
    title: str | None = None
    github_repo: str | None = None
    created_at: datetime
    updated_at: datetime
