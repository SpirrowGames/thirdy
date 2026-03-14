from datetime import datetime
from uuid import UUID

from .common import BaseSchema


class UserRead(BaseSchema):
    id: UUID
    email: str
    name: str
    picture: str | None = None
    created_at: datetime
    updated_at: datetime
