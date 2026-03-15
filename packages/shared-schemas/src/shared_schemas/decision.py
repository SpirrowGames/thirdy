import json
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import field_validator

from .common import BaseSchema


class DecisionStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class DecisionOptionRead(BaseSchema):
    id: UUID
    label: str
    description: str | None
    pros: list[str]
    cons: list[str]
    sort_order: int

    @field_validator("pros", "cons", mode="before")
    @classmethod
    def parse_json_list(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return json.loads(v)
        return v  # type: ignore[return-value]


class DecisionPointRead(BaseSchema):
    id: UUID
    conversation_id: UUID
    design_id: UUID | None = None
    question: str
    context: str
    recommendation: str | None
    status: DecisionStatus
    resolved_option_id: UUID | None
    resolution_note: str | None
    options: list[DecisionOptionRead]
    created_at: datetime
    updated_at: datetime


class DecisionPointUpdate(BaseSchema):
    status: DecisionStatus | None = None
    resolved_option_id: UUID | None = None
    resolution_note: str | None = None


class DecisionDetectRequest(BaseSchema):
    model: str | None = None
