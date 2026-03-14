from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from api.config import settings
from api.db.engine import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify DB connection on startup
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    yield
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
    from api.routers.health import router as health_router

    app.include_router(health_router)
    app.include_router(auth_router)

    return app


app = create_app()
