"""Dashboard API: cross-conversation aggregated views."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select, case, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import (
    Conversation,
    User,
)
from api.db.models.specification import Specification
from api.db.models.design import Design
from api.db.models.generated_task import GeneratedTask
from api.db.models.generated_code import GeneratedCode
from api.db.models.pull_request import PullRequest
from api.db.models.activity import Activity
from api.dependencies import get_current_user, get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# --- Summary ---


class ArtifactCount(BaseModel):
    total: int = 0
    draft: int = 0
    approved: int = 0


class TaskCount(BaseModel):
    total: int = 0
    pending: int = 0
    in_progress: int = 0
    done: int = 0


class PRCount(BaseModel):
    total: int = 0
    created: int = 0
    merged: int = 0
    failed: int = 0


class RepoGroup(BaseModel):
    github_repo: str | None
    conversation_count: int
    spec_count: int
    task_count: int
    pr_count: int


class DashboardSummary(BaseModel):
    conversation_count: int
    specs: ArtifactCount
    designs: ArtifactCount
    tasks: TaskCount
    codes: ArtifactCount
    prs: PRCount
    repos: list[RepoGroup]


@router.get("/summary", response_model=DashboardSummary)
async def get_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_convs = select(Conversation.id).where(Conversation.user_id == user.id).subquery()

    # Conversation count
    conv_count = await db.scalar(
        select(func.count()).select_from(Conversation).where(Conversation.user_id == user.id)
    )

    # Specs
    spec_q = await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(Specification.status == "draft").label("draft"),
            func.count().filter(Specification.status == "approved").label("approved"),
        ).where(Specification.conversation_id.in_(select(user_convs)))
    )
    spec_row = spec_q.one()

    # Designs
    design_q = await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(Design.status == "draft").label("draft"),
            func.count().filter(Design.status == "approved").label("approved"),
        ).where(Design.conversation_id.in_(select(user_convs)))
    )
    design_row = design_q.one()

    # Tasks
    task_q = await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(GeneratedTask.status == "pending").label("pending"),
            func.count().filter(GeneratedTask.status == "in_progress").label("in_progress"),
            func.count().filter(GeneratedTask.status == "done").label("done"),
        ).where(GeneratedTask.conversation_id.in_(select(user_convs)))
    )
    task_row = task_q.one()

    # Codes
    code_q = await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(GeneratedCode.status == "draft").label("draft"),
            func.count().filter(GeneratedCode.status == "approved").label("approved"),
        ).where(GeneratedCode.conversation_id.in_(select(user_convs)))
    )
    code_row = code_q.one()

    # PRs
    pr_q = await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(PullRequest.status == "created").label("created"),
            func.count().filter(PullRequest.status == "merged").label("merged"),
            func.count().filter(PullRequest.status == "failed").label("failed"),
        ).where(PullRequest.conversation_id.in_(select(user_convs)))
    )
    pr_row = pr_q.one()

    # Repo groups
    repo_q = await db.execute(
        select(
            Conversation.github_repo,
            func.count(Conversation.id).label("conv_count"),
        )
        .where(Conversation.user_id == user.id)
        .group_by(Conversation.github_repo)
    )
    repo_groups = []
    for row in repo_q.all():
        gh_repo = row[0]
        c_count = row[1]
        # Get counts per repo group
        repo_conv_ids = select(Conversation.id).where(
            Conversation.user_id == user.id,
            Conversation.github_repo == gh_repo if gh_repo else Conversation.github_repo.is_(None),
        ).subquery()
        s_count = await db.scalar(
            select(func.count()).select_from(Specification).where(
                Specification.conversation_id.in_(select(repo_conv_ids))
            )
        ) or 0
        t_count = await db.scalar(
            select(func.count()).select_from(GeneratedTask).where(
                GeneratedTask.conversation_id.in_(select(repo_conv_ids))
            )
        ) or 0
        p_count = await db.scalar(
            select(func.count()).select_from(PullRequest).where(
                PullRequest.conversation_id.in_(select(repo_conv_ids))
            )
        ) or 0
        repo_groups.append(RepoGroup(
            github_repo=gh_repo,
            conversation_count=c_count,
            spec_count=s_count,
            task_count=t_count,
            pr_count=p_count,
        ))

    return DashboardSummary(
        conversation_count=conv_count or 0,
        specs=ArtifactCount(total=spec_row[0], draft=spec_row[1], approved=spec_row[2]),
        designs=ArtifactCount(total=design_row[0], draft=design_row[1], approved=design_row[2]),
        tasks=TaskCount(total=task_row[0], pending=task_row[1], in_progress=task_row[2], done=task_row[3]),
        codes=ArtifactCount(total=code_row[0], draft=code_row[1], approved=code_row[2]),
        prs=PRCount(total=pr_row[0], created=pr_row[1], merged=pr_row[2], failed=pr_row[3]),
        repos=repo_groups,
    )


# --- Tasks list ---


class DashboardTask(BaseModel):
    id: str
    conversation_id: str
    conversation_title: str | None
    github_repo: str | None
    title: str
    description: str
    priority: str
    status: str
    created_at: str


@router.get("/tasks", response_model=list[DashboardTask])
async def list_tasks(
    status: str | None = Query(None),
    priority: str | None = Query(None),
    github_repo: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(GeneratedTask, Conversation.title.label("conv_title"), Conversation.github_repo)
        .join(Conversation, GeneratedTask.conversation_id == Conversation.id)
        .where(Conversation.user_id == user.id)
    )
    if status:
        q = q.where(GeneratedTask.status == status)
    if priority:
        q = q.where(GeneratedTask.priority == priority)
    if github_repo:
        q = q.where(Conversation.github_repo == github_repo)

    q = q.order_by(GeneratedTask.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(q)

    tasks = []
    for row in result.all():
        task = row[0]
        tasks.append(DashboardTask(
            id=str(task.id),
            conversation_id=str(task.conversation_id),
            conversation_title=row[1],
            github_repo=row[2],
            title=task.title,
            description=task.description,
            priority=task.priority,
            status=task.status,
            created_at=task.created_at.isoformat(),
        ))
    return tasks


# --- PRs list ---


class DashboardPR(BaseModel):
    id: str
    conversation_id: str
    conversation_title: str | None
    github_repo: str | None
    title: str
    pr_number: int | None
    pr_url: str | None
    status: str
    created_at: str


@router.get("/prs", response_model=list[DashboardPR])
async def list_prs(
    status: str | None = Query(None),
    github_repo: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(PullRequest, Conversation.title.label("conv_title"), Conversation.github_repo)
        .join(Conversation, PullRequest.conversation_id == Conversation.id)
        .where(Conversation.user_id == user.id)
    )
    if status:
        q = q.where(PullRequest.status == status)
    if github_repo:
        q = q.where(Conversation.github_repo == github_repo)

    q = q.order_by(PullRequest.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(q)

    prs = []
    for row in result.all():
        pr = row[0]
        prs.append(DashboardPR(
            id=str(pr.id),
            conversation_id=str(pr.conversation_id),
            conversation_title=row[1],
            github_repo=row[2],
            title=pr.title,
            pr_number=pr.pr_number,
            pr_url=pr.pr_url,
            status=pr.status,
            created_at=pr.created_at.isoformat(),
        ))
    return prs


# --- Activity ---


class DashboardActivity(BaseModel):
    id: str
    conversation_id: str | None
    action: str
    entity_type: str | None
    entity_id: str | None
    summary: str | None
    created_at: str


@router.get("/activity", response_model=list[DashboardActivity])
async def list_activity(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Activity)
        .where(Activity.user_id == user.id)
        .order_by(Activity.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(q)
    activities = []
    for a in result.scalars().all():
        activities.append(DashboardActivity(
            id=str(a.id),
            conversation_id=str(a.conversation_id) if a.conversation_id else None,
            action=a.action,
            entity_type=a.entity_type,
            entity_id=str(a.entity_id) if a.entity_id else None,
            summary=a.summary,
            created_at=a.created_at.isoformat(),
        ))
    return activities
