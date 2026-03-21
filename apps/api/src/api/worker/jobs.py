"""Job functions for ARQ workers."""
import logging
from datetime import datetime, timezone
from uuid import UUID

from arq.connections import ArqRedis
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


async def spec_review_job(ctx: dict, job_id: str, payload: dict) -> dict:
    """Spec Review job: deep analysis of a specification document."""
    from api.services.spec_review_service import SpecReviewService

    await _update_job_status(ctx, job_id, "running")
    try:
        specification_id = UUID(payload["specification_id"])
        conversation_id = payload["conversation_id"]
        scope = payload.get("scope", "full")

        async with ctx["session_factory"]() as session:
            service = SpecReviewService(session, ctx["lexora_client"])
            review = await service.run_review(
                specification_id,
                UUID(conversation_id),
                job_id=job_id,
                scope=scope,
            )
            # Extract result within session scope to avoid detached instance errors
            result = {
                "review_id": str(review.id),
                "score": review.summary.get("quality_score") if review.summary else None,
                "badge": review.summary.get("quality_badge") if review.summary else None,
                "total_issues": review.summary.get("total_issues") if review.summary else 0,
            }
        await _update_job_status(ctx, job_id, "completed", result=result)

        # Create notification
        try:
            async with ctx["session_factory"]() as session:
                from api.db.models.notification import Notification
                from api.db.models import Conversation
                from sqlalchemy import select as sa_select
                conv_result = await session.execute(
                    sa_select(Conversation).where(Conversation.id == UUID(conversation_id))
                )
                conv = conv_result.scalar_one_or_none()
                if conv:
                    total_issues = result.get("total_issues", 0)
                    badge = result.get("badge", "")
                    notification = Notification(
                        user_id=conv.user_id,
                        type="spec_review_complete",
                        title="仕様書レビュー完了",
                        body=f"品質スコア: {result.get('score', '?')}/100 ({badge}), {total_issues}件の問題を検出",
                        link=f"/chat/{conversation_id}",
                    )
                    session.add(notification)
                    await session.commit()
        except Exception as notify_err:
            logger.warning("Failed to create spec review notification: %s", notify_err)

        return result
    except Exception as exc:
        await _update_job_status(ctx, job_id, "failed", error=str(exc))
        raise


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


async def classify_and_extract_spec_job(
    ctx: dict,
    conversation_id: str,
    user_message: str,
    ai_response: str,
) -> dict:
    """Classify message for spec relevance and extract if relevant.

    Lightweight job (no BackgroundJob record) that runs after each chat response.
    Chains spec_classifier → incremental_extractor.
    """
    from api.services.spec_classifier import classify_message
    from api.services.incremental_spec_extractor import incremental_extract

    lexora = ctx["lexora_client"]

    # Step 1: Classify
    classification = await classify_message(lexora, user_message, ai_response)
    logger.info(
        "Spec classification for %s: relevant=%s categories=%s",
        conversation_id, classification.is_spec_relevant, classification.categories,
    )

    if not classification.is_spec_relevant:
        return {"classified": True, "relevant": False}

    # Step 2: Incremental extraction
    conv_uuid = UUID(conversation_id)
    async with ctx["session_factory"]() as session:
        spec = await incremental_extract(
            session=session,
            lexora=lexora,
            conversation_id=conv_uuid,
            user_message=user_message,
            ai_response=ai_response,
            classification_summary=classification.summary,
            categories=classification.categories,
        )

    if spec is None:
        return {"classified": True, "relevant": True, "extracted": False}

    # Step 3: Create notification
    try:
        async with ctx["session_factory"]() as session:
            from api.db.models.notification import Notification
            from api.db.models import Conversation
            conv_result = await session.execute(
                select(Conversation).where(Conversation.id == conv_uuid)
            )
            conv = conv_result.scalar_one_or_none()
            if conv:
                notification = Notification(
                    user_id=conv.user_id,
                    type="spec_updated",
                    title="仕様が自動更新されました",
                    body=f"会話の内容から仕様を更新しました: {classification.summary[:100]}",
                    link=f"/chat/{conversation_id}",
                )
                session.add(notification)
                await session.commit()
    except Exception as notify_err:
        logger.warning("Failed to create spec notification: %s", notify_err)

    # Step 4: Auto-trigger spec review after N incremental updates
    try:
        from api.config import settings as app_settings
        interval = getattr(app_settings, "spec_review_auto_trigger_interval", 3)
        redis: ArqRedis | None = ctx.get("redis")
        if redis is None:
            # Fallback: try to import and create a connection
            from api.worker.redis_pool import create_redis_pool
            redis = await create_redis_pool()
            ctx["redis"] = redis
        counter_key = f"thirdy:spec_update_count:{spec.id}"
        count = await redis.incr(counter_key)
        if count >= interval:
            await redis.delete(counter_key)
            # Enqueue spec review job
            await redis.enqueue_job(
                "spec_review_job",
                _job_id=f"auto-review-{spec.id}-{count}",
                job_id=f"auto-review-{spec.id}-{count}",
                payload={
                    "specification_id": str(spec.id),
                    "conversation_id": conversation_id,
                    "scope": "quick",
                },
            )
            logger.info(
                "Auto-triggered spec review after %d incremental updates for spec %s",
                count, spec.id,
            )
    except Exception as auto_review_err:
        logger.warning("Failed to auto-trigger spec review: %s", auto_review_err)

    return {
        "classified": True,
        "relevant": True,
        "extracted": True,
        "spec_id": str(spec.id),
    }


async def classify_and_extract_decision_job(
    ctx: dict,
    conversation_id: str,
    user_message: str,
    ai_response: str,
) -> dict:
    """Classify message for decision points and extract if found.

    Lightweight job (no BackgroundJob record) that runs after each chat response,
    in parallel with spec classification.
    """
    from api.services.decision_classifier import classify_decision
    from api.services.incremental_decision_extractor import incremental_extract_decision
    from api.services.decision_resolver import check_and_resolve_decisions

    lexora = ctx["lexora_client"]
    conv_uuid = UUID(conversation_id)

    # Step 0: Check if any pending decisions are resolved
    resolved_ids: list[str] = []
    try:
        async with ctx["session_factory"]() as session:
            resolved_ids = await check_and_resolve_decisions(
                session, lexora, conv_uuid, user_message, ai_response,
            )
        if resolved_ids:
            logger.info("Auto-resolved %d decision(s) for %s", len(resolved_ids), conversation_id)
            # Notify
            try:
                async with ctx["session_factory"]() as session:
                    from api.db.models.notification import Notification
                    from api.db.models import Conversation
                    conv_result = await session.execute(
                        select(Conversation).where(Conversation.id == conv_uuid)
                    )
                    conv = conv_result.scalar_one_or_none()
                    if conv:
                        notification = Notification(
                            user_id=conv.user_id,
                            type="decision_resolved",
                            title="判断ポイントが自動確定されました",
                            body=f"{len(resolved_ids)}件の判断ポイントが会話から自動確定されました",
                            link=f"/chat/{conversation_id}",
                        )
                        session.add(notification)
                        await session.commit()
            except Exception as notify_err:
                logger.warning("Failed to create resolution notification: %s", notify_err)
    except Exception as resolve_err:
        logger.warning("Decision resolution check failed: %s", resolve_err)

    # Step 1: Classify for new decision points
    classification = await classify_decision(lexora, user_message, ai_response)
    logger.info(
        "Decision classification for %s: has_decision=%s question=%s",
        conversation_id, classification.has_decision_point, classification.question[:80] if classification.question else "",
    )

    if not classification.has_decision_point:
        return {"classified": True, "has_decision": False, "resolved": resolved_ids}

    # Step 2: Extract decision point
    async with ctx["session_factory"]() as session:
        dp = await incremental_extract_decision(
            session=session,
            lexora=lexora,
            conversation_id=conv_uuid,
            user_message=user_message,
            ai_response=ai_response,
            question_hint=classification.question,
            options_hint=classification.options_hint,
            context_hint=classification.context,
        )

    if dp is None:
        return {"classified": True, "has_decision": True, "extracted": False}

    # Step 3: Create notification
    try:
        async with ctx["session_factory"]() as session:
            from api.db.models.notification import Notification
            from api.db.models import Conversation
            conv_result = await session.execute(
                select(Conversation).where(Conversation.id == conv_uuid)
            )
            conv = conv_result.scalar_one_or_none()
            if conv:
                notification = Notification(
                    user_id=conv.user_id,
                    type="decision_detected",
                    title="新しい判断ポイントが検出されました",
                    body=classification.question[:200],
                    link=f"/chat/{conversation_id}",
                )
                session.add(notification)
                await session.commit()
    except Exception as notify_err:
        logger.warning("Failed to create decision notification: %s", notify_err)

    return {
        "classified": True,
        "has_decision": True,
        "extracted": True,
        "decision_point_id": str(dp.id),
        "resolved": resolved_ids,
    }


async def auto_pipeline_job(
    ctx: dict,
    conversation_id: str,
    design_id: str,
) -> dict:
    """Run the full auto pipeline: Tasks → Code → PR for each task."""
    from api.services.auto_pipeline import run_auto_pipeline

    lexora = ctx["lexora_client"]
    session_factory = ctx["session_factory"]

    # Notify start
    conv_uuid = UUID(conversation_id)
    try:
        async with session_factory() as session:
            from api.db.models.notification import Notification
            from api.db.models import Conversation
            conv = (await session.execute(
                select(Conversation).where(Conversation.id == conv_uuid)
            )).scalar_one_or_none()
            if conv:
                notification = Notification(
                    user_id=conv.user_id,
                    type="auto_pipeline_started",
                    title="Auto Pipeline 開始",
                    body="Design承認後の自動パイプラインを開始しました",
                    link=f"/chat/{conversation_id}",
                )
                session.add(notification)
                await session.commit()
    except Exception:
        pass

    result = await run_auto_pipeline(
        session_factory=session_factory,
        lexora=lexora,
        conversation_id=conv_uuid,
        design_id=UUID(design_id),
    )

    # Notify completion
    try:
        async with session_factory() as session:
            from api.db.models.notification import Notification
            from api.db.models import Conversation
            conv = (await session.execute(
                select(Conversation).where(Conversation.id == conv_uuid)
            )).scalar_one_or_none()
            if conv:
                errors = result.get("errors", [])
                status_text = "完了" if not errors else f"完了（{len(errors)}件のエラー）"
                notification = Notification(
                    user_id=conv.user_id,
                    type="auto_pipeline_complete",
                    title=f"Auto Pipeline {status_text}",
                    body=f"{result.get('tasks', 0)}タスク, {result.get('codes', 0)}コード, {result.get('prs', 0)} PR",
                    link=f"/chat/{conversation_id}",
                )
                session.add(notification)
                await session.commit()
    except Exception:
        pass

    return result
