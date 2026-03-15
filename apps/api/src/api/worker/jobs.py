"""Job functions for ARQ workers.

Phase 6 placeholders for Internal Audit and External Watch jobs.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from api.db.models.background_job import BackgroundJob

logger = logging.getLogger(__name__)


async def _update_job_status(
    ctx: dict,
    job_id: str,
    status: str,
    *,
    result: dict | None = None,
    error: str | None = None,
) -> None:
    """Update job status in the database."""
    async with ctx["session_factory"]() as session:
        row = await session.execute(
            select(BackgroundJob).where(BackgroundJob.job_id == job_id)
        )
        job = row.scalar_one_or_none()
        if job is None:
            logger.warning("Job %s not found in DB", job_id)
            return

        job.status = status
        now = datetime.now(timezone.utc)

        if status == "running":
            job.started_at = now
            job.attempts += 1
        elif status in ("completed", "failed"):
            job.completed_at = now

        if result is not None:
            job.result = result
        if error is not None:
            job.error = error

        await session.commit()


async def example_audit_job(ctx: dict, job_id: str, payload: dict) -> dict:
    """Phase 6 placeholder: Internal Audit job."""
    await _update_job_status(ctx, job_id, "running")
    try:
        # TODO: Phase 6 – implement audit logic
        result = {"message": "audit job completed", "payload": payload}
        await _update_job_status(ctx, job_id, "completed", result=result)
        return result
    except Exception as exc:
        await _update_job_status(ctx, job_id, "failed", error=str(exc))
        raise


async def example_watch_job(ctx: dict, job_id: str, payload: dict) -> dict:
    """Phase 6 placeholder: External Watch job."""
    await _update_job_status(ctx, job_id, "running")
    try:
        # TODO: Phase 6 – implement watch logic
        result = {"message": "watch job completed", "payload": payload}
        await _update_job_status(ctx, job_id, "completed", result=result)
        return result
    except Exception as exc:
        await _update_job_status(ctx, job_id, "failed", error=str(exc))
        raise
