from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

from .common import BaseSchema


class WatchSourceType(StrEnum):
    dependency = "dependency"
    api_change = "api_change"
    security = "security"
    competitor = "competitor"
    ecosystem = "ecosystem"


class WatchImpactLevel(StrEnum):
    none = "none"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class WatchFinding(BaseSchema):
    source_type: WatchSourceType
    impact_level: WatchImpactLevel
    title: str
    description: str
    source_url: str | None = None
    affected_area: str | None = None  # e.g. "backend", "frontend", "infrastructure"
    recommendation: str | None = None


class WatchSummary(BaseSchema):
    total_findings: int
    findings_by_impact: dict[str, int]
    findings_by_source: dict[str, int]
    highest_impact: str  # none / low / medium / high / critical
    requires_action: bool


class WatchReportRead(BaseSchema):
    id: UUID
    conversation_id: UUID
    job_id: str | None = None
    summary: WatchSummary | None = None
    findings: list[WatchFinding] = []
    watch_targets: list[str] = []
    status: str
    created_at: datetime
    updated_at: datetime


class WatchTriggerRequest(BaseModel):
    model: str | None = None
    targets: list[str] | None = None  # specific areas to watch; None = all


class WatchTriggerResponse(BaseSchema):
    job_id: str
    conversation_id: UUID
    message: str
