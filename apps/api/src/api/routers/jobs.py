from fastapi import APIRouter, Depends, HTTPException, Query, status

from shared_schemas.background_job import (
    BackgroundJobEnqueue,
    BackgroundJobRead,
)

from api.db.models import User
from api.dependencies import get_background_job_service, get_current_user
from api.services.background_job_service import BackgroundJobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[BackgroundJobRead])
async def list_jobs(
    job_type: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _current_user: User = Depends(get_current_user),
    service: BackgroundJobService = Depends(get_background_job_service),
):
    return await service.list_jobs(
        job_type=job_type, status=status_filter, limit=limit, offset=offset
    )


@router.get("/{job_id}", response_model=BackgroundJobRead)
async def get_job(
    job_id: str,
    _current_user: User = Depends(get_current_user),
    service: BackgroundJobService = Depends(get_background_job_service),
):
    job = await service.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )
    return job


@router.post("", response_model=BackgroundJobRead, status_code=status.HTTP_201_CREATED)
async def enqueue_job(
    body: BackgroundJobEnqueue,
    _current_user: User = Depends(get_current_user),
    service: BackgroundJobService = Depends(get_background_job_service),
):
    return await service.enqueue(
        job_type=body.job_type,
        func_name=body.func_name,
        payload=body.payload,
        max_retries=body.max_retries,
    )
