from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Conversation, User, WatchReport
from api.dependencies import get_background_job_service, get_current_user, get_db
from api.services.background_job_service import BackgroundJobService
from shared_schemas.watch_report import (
    WatchReportRead,
    WatchTriggerRequest,
    WatchTriggerResponse,
)

router = APIRouter(tags=["watches"])


async def _get_user_conversation(
    conversation_id: UUID,
    user: User,
    db: AsyncSession,
) -> Conversation:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return conversation


@router.post(
    "/conversations/{conversation_id}/watch",
    response_model=WatchTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_watch(
    conversation_id: UUID,
    body: WatchTriggerRequest | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    job_service: BackgroundJobService = Depends(get_background_job_service),
):
    conversation = await _get_user_conversation(conversation_id, user, db)
    model = body.model if body else None
    targets = body.targets if body else None

    job = await job_service.enqueue(
        job_type="watch",
        func_name="watch_conversation_job",
        payload={
            "conversation_id": str(conversation.id),
            "model": model,
            "targets": targets,
        },
    )
    return WatchTriggerResponse(
        job_id=job.job_id,
        conversation_id=conversation.id,
        message="Watch job enqueued",
    )


@router.get(
    "/conversations/{conversation_id}/watches",
    response_model=list[WatchReportRead],
)
async def list_watch_reports(
    conversation_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_conversation(conversation_id, user, db)
    result = await db.execute(
        select(WatchReport)
        .where(WatchReport.conversation_id == conversation_id)
        .order_by(WatchReport.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get(
    "/watches/{watch_id}",
    response_model=WatchReportRead,
)
async def get_watch_report(
    watch_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WatchReport).where(WatchReport.id == watch_id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watch report not found",
        )
    await _get_user_conversation(report.conversation_id, user, db)
    return report


@router.delete(
    "/watches/{watch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_watch_report(
    watch_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WatchReport).where(WatchReport.id == watch_id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watch report not found",
        )
    await _get_user_conversation(report.conversation_id, user, db)
    await db.delete(report)
    await db.commit()
