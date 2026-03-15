from datetime import datetime
from uuid import UUID

from pydantic import model_validator

from .common import BaseSchema


class UserRead(BaseSchema):
    id: UUID
    email: str
    name: str
    picture: str | None = None
    google_calendar_connected: bool = False
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="wrap")
    @classmethod
    def _compute_calendar_connected(cls, values, handler):
        # When constructing from ORM, check for google_refresh_token
        if hasattr(values, "google_refresh_token"):
            obj = handler(values)
            obj.google_calendar_connected = values.google_refresh_token is not None
            return obj
        return handler(values)
