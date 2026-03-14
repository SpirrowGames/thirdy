import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from llm_client import LexoraClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.db.base import Base
from api.db.models import User
from api.dependencies import get_db, get_lexora_client

# In-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite://"


@pytest.fixture()
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture()
async def db_session(test_engine) -> AsyncGenerator[AsyncSession]:
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture()
def mock_lexora_client() -> LexoraClient:
    client = AsyncMock(spec=LexoraClient)

    async def mock_stream(messages, model=None):
        for token in ["Hello", ", ", "world", "!"]:
            yield token

    client.stream = mock_stream
    client.complete = AsyncMock(return_value="Hello, world!")
    return client


@pytest.fixture()
async def client(db_session: AsyncSession, test_engine, mock_lexora_client: LexoraClient) -> AsyncGenerator[AsyncClient]:
    from api.main import create_app

    app = create_app()

    # Use the test async engine for the streaming session factory
    test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    app.state.session_factory = test_session_factory

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_lexora_client] = lambda: mock_lexora_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture()
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User",
        google_sub="google-sub-123",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture()
def auth_headers(test_user: User) -> dict[str, str]:
    from api.auth.jwt import create_access_token
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}
