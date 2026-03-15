from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from llm_client import LexoraClient
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from api.config import settings
from api.db.engine import async_session, engine
from api.services.whisper_service import WhisperService
from api.worker.redis_pool import create_redis_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify DB connection on startup
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))

    # Session factory for streaming handlers
    app.state.session_factory = async_session

    # Initialize Lexora client
    http_client = httpx.AsyncClient()
    app.state.lexora_client = LexoraClient(
        http_client=http_client,
        base_url=settings.lexora_base_url,
        default_model=settings.lexora_default_model,
    )

    # Initialize Whisper service
    app.state.whisper_service = WhisperService(model_size=settings.whisper_model_size)

    # Initialize Redis pool
    app.state.redis_pool = await create_redis_pool()

    yield

    # Cleanup
    await app.state.redis_pool.aclose()
    await http_client.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="Thirdy API", version="0.1.0", lifespan=lifespan)

    # Session middleware (required by authlib OAuth)
    app.add_middleware(SessionMiddleware, secret_key=settings.jwt_secret_key)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    from api.auth.router import router as auth_router
    from api.routers.chat import router as chat_router
    from api.routers.conversations import router as conversations_router
    from api.routers.health import router as health_router
    from api.routers.specifications import router as specifications_router
    from api.routers.decisions import router as decisions_router
    from api.routers.designs import router as designs_router
    from api.routers.tasks import router as tasks_router
    from api.routers.codes import router as codes_router
    from api.routers.pull_requests import router as pull_requests_router
    from api.routers.votes import router as votes_router
    from api.routers.voice import router as voice_router
    from api.routers.github_issues import router as github_issues_router
    from api.routers.jobs import router as jobs_router
    from api.routers.audits import router as audits_router

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(conversations_router)
    app.include_router(chat_router)
    app.include_router(specifications_router)
    app.include_router(decisions_router)
    app.include_router(designs_router)
    app.include_router(tasks_router)
    app.include_router(codes_router)
    app.include_router(pull_requests_router)
    app.include_router(votes_router)
    app.include_router(voice_router)
    app.include_router(github_issues_router)
    app.include_router(jobs_router)
    app.include_router(audits_router)

    return app


app = create_app()
