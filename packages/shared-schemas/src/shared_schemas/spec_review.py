from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

from .common import BaseSchema


class ReviewIssueSeverity(StrEnum):
    critical = "critical"
    warning = "warning"
    info = "info"


class ReviewIssueCategory(StrEnum):
    contradiction = "contradiction"
    gap = "gap"
    ambiguity = "ambiguity"
    inconsistency = "inconsistency"


class SpecReviewIssue(BaseSchema):
    severity: ReviewIssueSeverity
    category: ReviewIssueCategory
    title: str
    description: str
    location: str | None = None  # Section or line reference in the spec


class SpecReviewSuggestion(BaseSchema):
    severity: ReviewIssueSeverity
    title: str
    description: str
    before: str | None = None  # Original text to replace
    after: str | None = None  # Proposed replacement text
    section: str | None = None  # Section to add/modify
    status: str = "pending"  # pending / applied / dismissed
    related_issue_index: int | None = None  # Index into issues list


class SpecReviewQuestion(BaseSchema):
    question: str
    context: str | None = None  # Why this question matters
    priority: str = "medium"  # high / medium / low


class SpecReviewSummary(BaseSchema):
    quality_score: int  # 0-100
    quality_badge: str  # excellent / good / needs_improvement / poor
    total_issues: int
    total_suggestions: int
    total_questions: int
    issues_by_category: dict[str, int]
    issues_by_severity: dict[str, int]


class SpecReviewRead(BaseSchema):
    id: UUID
    specification_id: UUID
    conversation_id: UUID
    job_id: str | None = None
    status: str
    scope: str
    summary: SpecReviewSummary | None = None
    issues: list[SpecReviewIssue] = []
    suggestions: list[SpecReviewSuggestion] = []
    questions: list[SpecReviewQuestion] = []
    created_at: datetime
    updated_at: datetime


class SpecReviewTriggerRequest(BaseModel):
    scope: str = "full"  # full / quick


class SpecReviewTriggerResponse(BaseSchema):
    job_id: str
    specification_id: UUID
    conversation_id: UUID
    message: str


class SuggestionApplyRequest(BaseModel):
    confirm: bool = False  # Set True to apply, False for preview only


class SuggestionApplyResponse(BaseSchema):
    preview_diff: str | None = None
    applied: bool = False
    updated_content: str | None = None  # Only when applied=True
