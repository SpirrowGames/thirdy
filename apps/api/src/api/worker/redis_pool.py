from urllib.parse import urlparse

from arq.connections import ArqRedis, RedisSettings, create_pool

from api.config import settings


def get_redis_settings() -> RedisSettings:
    """Parse settings.redis_url into ARQ RedisSettings."""
    parsed = urlparse(settings.redis_url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or "0"),
        password=parsed.password,
    )


async def create_redis_pool() -> ArqRedis:
    """Create and return an ARQ Redis connection pool."""
    return await create_pool(get_redis_settings())
