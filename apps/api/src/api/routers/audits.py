from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import AuditReport, Conversation, User
from api.dependencies import get_background_job_service, get_current_user, get_db
from api.services.background_job_service import BackgroundJobService
from shared_schemas.audit_report import (
    AuditReportRead,
    AuditTriggerRequest,
    AuditTriggerResponse,
)

router = APIRouter(tags=["audits"])


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
    "/conversations/{conversation_id}/audit",
    response_model=AuditTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_audit(
    conversation_id: UUID,
    body: AuditTriggerRequest | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    job_service: BackgroundJobService = Depends(get_background_job_service),
):
    conversation = await _get_user_conversation(conversation_id, user, db)
    model = body.model if body else None
    scope = body.scope if body else "full"

    job = await job_service.enqueue(
        job_type="audit",
        func_name="audit_conversation_job",
        payload={
            "conversation_id": str(conversation.id),
            "model": model,
            "scope": scope,
        },
    )
    return AuditTriggerResponse(
        job_id=job.job_id,
        conversation_id=conversation.id,
        message="Audit job enqueued",
    )


@router.get(
    "/conversations/{conversation_id}/audits",
    response_model=list[AuditReportRead],
)
async def list_audit_reports(
    conversation_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_conversation(conversation_id, user, db)
    result = await db.execute(
        select(AuditReport)
        .where(AuditReport.conversation_id == conversation_id)
        .order_by(AuditReport.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get(
    "/audits/{audit_id}",
    response_model=AuditReportRead,
)
async def get_audit_report(
    audit_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AuditReport).where(AuditReport.id == audit_id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit report not found",
        )
    # Ownership check via conversation
    await _get_user_conversation(report.conversation_id, user, db)
    return report


@router.delete(
    "/audits/{audit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_audit_report(
    audit_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AuditReport).where(AuditReport.id == audit_id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit report not found",
        )
    await _get_user_conversation(report.conversation_id, user, db)
    await db.delete(report)
    await db.commit()
