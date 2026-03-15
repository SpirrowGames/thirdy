import uuid

from arq.connections import ArqRedis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models.background_job import BackgroundJob


class BackgroundJobService:
    def __init__(self, redis_pool: ArqRedis, db: AsyncSession):
        self.redis = redis_pool
        self.db = db

    async def enqueue(
        self,
        job_type: str,
        func_name: str,
        payload: dict | None = None,
        max_retries: int = 3,
    ) -> BackgroundJob:
        """Create a DB record and enqueue the job via ARQ."""
        job_id = str(uuid.uuid4())

        job = BackgroundJob(
            job_id=job_id,
            job_type=job_type,
            status="queued",
            payload=payload or {},
            max_retries=max_retries,
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        await self.redis.enqueue_job(func_name, job_id, payload or {})
        return job

    async def get_job(self, job_id: str) -> BackgroundJob | None:
        """Retrieve a single job by job_id."""
        result = await self.db.execute(
            select(BackgroundJob).where(BackgroundJob.job_id == job_id)
        )
        return result.scalar_one_or_none()

    async def list_jobs(
        self,
        job_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BackgroundJob]:
        """List jobs with optional filters."""
        query = select(BackgroundJob).order_by(BackgroundJob.created_at.desc())

        if job_type is not None:
            query = query.where(BackgroundJob.job_type == job_type)
        if status is not None:
            query = query.where(BackgroundJob.status == status)

        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())
