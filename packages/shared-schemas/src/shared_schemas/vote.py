from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .common import BaseSchema


class VoteSessionStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    SPLIT = "split"


class VoteRead(BaseSchema):
    id: UUID
    vote_session_id: UUID
    option_id: UUID
    voter_name: str
    comment: str | None
    created_at: datetime


class VoteTally(BaseSchema):
    option_id: UUID
    option_label: str
    count: int
    percentage: float
    voters: list[str]


class VoteSessionRead(BaseSchema):
    id: UUID
    decision_point_id: UUID
    status: VoteSessionStatus
    share_token: str
    deadline: datetime | None
    votes: list[VoteRead]
    tally: list[VoteTally]
    total_votes: int
    created_at: datetime


class VoteSessionCreate(BaseSchema):
    decision_point_id: UUID
    deadline: datetime | None = None


class VoteCast(BaseSchema):
    option_id: UUID
    voter_name: str
    voter_token: str
    comment: str | None = None


class MeetingSuggestion(BaseSchema):
    subject: str
    description: str
    ics_content: str


class CalendarEventPreset(StrEnum):
    QUICK_SYNC = "quick_sync"
    DISCUSSION = "discussion"
    DEEP_DIVE = "deep_dive"


class CalendarEventCreate(BaseSchema):
    vote_session_id: UUID
    preset: CalendarEventPreset
    attendee_emails: list[str] = []
    start_time: datetime | None = None


class CalendarEventResponse(BaseSchema):
    event_id: str
    html_link: str
    summary: str
    start: datetime
    end: datetime
