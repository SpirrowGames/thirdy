"""ARQ WorkerSettings – entry point for `arq api.worker.settings.WorkerSettings`."""
import httpx
from llm_client import LexoraClient

from api.config import settings
from api.db.engine import async_session
from api.worker.jobs import spec_review_job, audit_conversation_job, watch_conversation_job, classify_and_extract_spec_job, classify_and_extract_decision_job, auto_pipeline_job
from api.worker.redis_pool import get_redis_settings


async def startup(ctx: dict) -> None:
    """Inject shared resources into worker context."""
    ctx["session_factory"] = async_session

    http_client = httpx.AsyncClient()
    ctx["http_client"] = http_client
    ctx["lexora_client"] = LexoraClient(
        http_client=http_client,
        base_url=settings.lexora_base_url,
        default_model=settings.lexora_default_model,
    )


async def shutdown(ctx: dict) -> None:
    """Cleanup worker resources."""
    http_client = ctx.get("http_client")
    if http_client is not None:
        await http_client.aclose()


class WorkerSettings:
    functions = [spec_review_job, audit_conversation_job, watch_conversation_job, classify_and_extract_spec_job, classify_and_extract_decision_job, auto_pipeline_job]
    redis_settings = get_redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 1800  # 30 min for auto pipeline
    # cron_jobs – Phase 6 で有効化
    # cron_jobs = [cron(audit_conversation_job, hour=0, minute=0)]
