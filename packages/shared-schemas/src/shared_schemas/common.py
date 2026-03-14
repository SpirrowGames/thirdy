from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseSchema):
    status: str
    db_connected: bool


class PaginationParams(BaseModel):
    offset: int = 0
    limit: int = 50
