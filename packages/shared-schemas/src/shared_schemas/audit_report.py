from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

from .common import BaseSchema


class FindingSeverity(StrEnum):
    info = "info"
    warning = "warning"
    error = "error"
    critical = "critical"


class FindingCategory(StrEnum):
    consistency = "consistency"
    completeness = "completeness"
    quality = "quality"
    dependency = "dependency"
    redundancy = "redundancy"


class AuditFinding(BaseSchema):
    severity: FindingSeverity
    category: FindingCategory
    title: str
    description: str
    affected_entity_type: str | None = None  # specification / design / task / code
    affected_entity_id: str | None = None
    suggestion: str | None = None


class AuditSummary(BaseSchema):
    overall_score: int  # 0-100
    quality_badge: str  # excellent / good / needs_improvement / poor
    total_findings: int
    findings_by_severity: dict[str, int]
    analyzed_entities: dict[str, int]


class AuditReportRead(BaseSchema):
    id: UUID
    conversation_id: UUID
    job_id: str | None = None
    summary: AuditSummary | None = None
    findings: list[AuditFinding] = []
    status: str
    created_at: datetime
    updated_at: datetime


class AuditTriggerRequest(BaseModel):
    model: str | None = None
    scope: str = "full"


class AuditTriggerResponse(BaseSchema):
    job_id: str
    conversation_id: UUID
    message: str
