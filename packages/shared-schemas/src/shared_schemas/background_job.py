from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BackgroundJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: str
    job_type: str
    status: str
    payload: dict | None = None
    result: dict | None = None
    error: str | None = None
    attempts: int
    max_retries: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class BackgroundJobEnqueue(BaseModel):
    job_type: str
    func_name: str
    payload: dict | None = None
    max_retries: int = 3
