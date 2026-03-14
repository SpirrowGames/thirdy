import uuid

import pytest
from httpx import AsyncClient

from api.auth.jwt import create_access_token, decode_access_token
from api.db.models import User


class TestJWT:
    def test_create_and_decode_token(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        decoded_id = decode_access_token(token)
        assert decoded_id == user_id

    def test_decode_invalid_token(self):
        result = decode_access_token("invalid-token")
        assert result is None

    def test_decode_tampered_token(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        tampered = token[:-5] + "XXXXX"
        result = decode_access_token(tampered)
        assert result is None


@pytest.mark.asyncio
async def test_auth_me_unauthorized(client: AsyncClient):
    response = await client.get("/auth/me")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_auth_me_with_valid_token(client: AsyncClient, test_user: User):
    token = create_access_token(test_user.id)
    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"


@pytest.mark.asyncio
async def test_auth_me_with_invalid_token(client: AsyncClient):
    response = await client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 401
