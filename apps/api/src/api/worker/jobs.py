"""Job functions for ARQ workers."""
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


async def audit_conversation_job(ctx: dict, job_id: str, payload: dict) -> dict:
    """Internal Audit job: run LLM-based audit on conversation artifacts."""
    from api.services.audit_service import AuditService

    await _update_job_status(ctx, job_id, "running")
    try:
        conversation_id = payload["conversation_id"]
        model = payload.get("model")
        scope = payload.get("scope", "full")

        async with ctx["session_factory"]() as session:
            service = AuditService(session, ctx["lexora_client"])
            report = await service.run_audit(
                conversation_id,
                job_id=job_id,
                model=model,
                scope=scope,
            )

        result = {
            "report_id": str(report.id),
            "score": report.summary.get("overall_score") if report.summary else None,
            "badge": report.summary.get("quality_badge") if report.summary else None,
        }
        await _update_job_status(ctx, job_id, "completed", result=result)
        return result
    except Exception as exc:
        await _update_job_status(ctx, job_id, "failed", error=str(exc))
        raise


async def watch_conversation_job(ctx: dict, job_id: str, payload: dict) -> dict:
    """External Watch job: analyze project for external risks via LLM."""
    from api.services.watch_service import WatchService

    await _update_job_status(ctx, job_id, "running")
    try:
        conversation_id = payload["conversation_id"]
        model = payload.get("model")
        targets = payload.get("targets")

        async with ctx["session_factory"]() as session:
            service = WatchService(session, ctx["lexora_client"])
            report = await service.run_watch(
                conversation_id,
                job_id=job_id,
                model=model,
                targets=targets,
            )

        result = {
            "report_id": str(report.id),
            "highest_impact": report.summary.get("highest_impact") if report.summary else None,
            "requires_action": report.summary.get("requires_action") if report.summary else False,
            "total_findings": report.summary.get("total_findings") if report.summary else 0,
        }
        await _update_job_status(ctx, job_id, "completed", result=result)
        return result
    except Exception as exc:
        await _update_job_status(ctx, job_id, "failed", error=str(exc))
        raise
