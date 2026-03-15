import json
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import field_validator

from .common import BaseSchema


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    SKIPPED = "skipped"


class GeneratedTaskRead(BaseSchema):
    id: UUID
    conversation_id: UUID
    design_id: UUID
    title: str
    description: str
    priority: TaskPriority
    status: TaskStatus
    dependencies: list[str]
    sort_order: int
    created_at: datetime
    updated_at: datetime

    @field_validator("dependencies", mode="before")
    @classmethod
    def parse_dependencies(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return json.loads(v)
        if isinstance(v, list):
            return v
        return []


class GeneratedTaskUpdate(BaseSchema):
    title: str | None = None
    description: str | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None


class TaskGenerateRequest(BaseSchema):
    design_id: UUID
    model: str | None = None
