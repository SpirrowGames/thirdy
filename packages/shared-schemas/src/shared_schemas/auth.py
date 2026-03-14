from uuid import UUID

from .common import BaseSchema


class TokenPayload(BaseSchema):
    sub: UUID
    exp: int


class TokenResponse(BaseSchema):
    access_token: str
    token_type: str = "bearer"


class GoogleUserInfo(BaseSchema):
    sub: str
    email: str
    name: str
    picture: str | None = None
