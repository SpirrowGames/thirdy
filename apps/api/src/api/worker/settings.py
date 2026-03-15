"""ARQ WorkerSettings – entry point for `arq api.worker.settings.WorkerSettings`."""
from api.db.engine import async_session
from api.worker.jobs import example_audit_job, example_watch_job
from api.worker.redis_pool import get_redis_settings


async def startup(ctx: dict) -> None:
    """Inject shared resources into worker context."""
    ctx["session_factory"] = async_session


async def shutdown(ctx: dict) -> None:
    """Cleanup worker resources."""
    pass


class WorkerSettings:
    functions = [example_audit_job, example_watch_job]
    redis_settings = get_redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 300
    # cron_jobs – Phase 6 で有効化
    # cron_jobs = [cron(example_audit_job, hour=0, minute=0)]
