from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Conversation, Message, User
from api.db.models.specification import Specification
from api.db.models.design import Design
from api.db.models.generated_task import GeneratedTask
from api.db.models.generated_code import GeneratedCode
from api.db.models.decision_point import DecisionPoint, DecisionOption
from api.dependencies import get_current_user, get_db
from shared_schemas import (
    ConversationCreate,
    ConversationRead,
    ConversationUpdate,
    MessageRead,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


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


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ConversationRead)
async def create_conversation(
    body: ConversationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conversation = Conversation(user_id=user.id, title=body.title, github_repo=body.github_repo, team_id=body.team_id)
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


@router.get("", response_model=list[ConversationRead])
async def list_conversations(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{conversation_id}", response_model=ConversationRead)
async def get_conversation(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_user_conversation(conversation_id, user, db)


@router.patch("/{conversation_id}", response_model=ConversationRead)
async def update_conversation(
    conversation_id: UUID,
    body: ConversationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conversation = await _get_user_conversation(conversation_id, user, db)
    if body.title is not None:
        conversation.title = body.title
    if body.github_repo is not None:
        conversation.github_repo = body.github_repo if body.github_repo else None
    if body.team_id is not None:
        conversation.team_id = body.team_id
    await db.commit()
    await db.refresh(conversation)
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conversation = await _get_user_conversation(conversation_id, user, db)
    await db.delete(conversation)
    await db.commit()


@router.get("/{conversation_id}/messages", response_model=list[MessageRead])
async def list_messages(
    conversation_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_conversation(conversation_id, user, db)
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


# --- Branching ---


class BranchRequest(BaseModel):
    message_id: UUID | None = None  # Branch point; None = branch from latest


@router.post("/{conversation_id}/branch", status_code=status.HTTP_201_CREATED, response_model=ConversationRead)
async def branch_conversation(
    conversation_id: UUID,
    body: BranchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    parent = await _get_user_conversation(conversation_id, user, db)

    # Load messages up to branch point
    msg_query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    if body.message_id:
        bp_msg = await db.execute(
            select(Message).where(
                Message.id == body.message_id,
                Message.conversation_id == conversation_id,
            )
        )
        branch_msg = bp_msg.scalar_one_or_none()
        if branch_msg is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        msg_query = msg_query.where(Message.created_at <= branch_msg.created_at)

    messages_result = await db.execute(msg_query)
    source_messages = messages_result.scalars().all()

    branch = Conversation(
        user_id=user.id,
        title=f"Branch: {parent.title or 'Untitled'}",
        github_repo=parent.github_repo,
        team_id=parent.team_id,
        parent_id=parent.id,
        branch_point_message_id=body.message_id,
        branch_status="active",
    )
    db.add(branch)
    await db.flush()

    for msg in source_messages:
        new_msg = Message(
            conversation_id=branch.id,
            role=msg.role,
            content=msg.content,
        )
        db.add(new_msg)

    await db.commit()
    await db.refresh(branch)
    return branch


@router.get("/{conversation_id}/branches", response_model=list[ConversationRead])
async def list_branches(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_conversation(conversation_id, user, db)
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.parent_id == conversation_id,
            Conversation.user_id == user.id,
        )
        .order_by(Conversation.created_at.desc())
    )
    return result.scalars().all()


class MergeResponse(BaseModel):
    merged: bool
    specs_copied: int = 0
    designs_copied: int = 0
    tasks_copied: int = 0
    codes_copied: int = 0
    decisions_copied: int = 0


@router.post("/{conversation_id}/merge", response_model=MergeResponse)
async def merge_branch(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Merge a branch's artifacts into its parent conversation."""
    branch = await _get_user_conversation(conversation_id, user, db)

    if not branch.parent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This conversation is not a branch",
        )
    if branch.branch_status == "merged":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Branch already merged",
        )

    parent_id = branch.parent_id
    counts = MergeResponse(merged=True)

    # Copy specs (overwrite parent draft if exists, else add)
    branch_specs = (await db.execute(
        select(Specification).where(Specification.conversation_id == conversation_id)
    )).scalars().all()
    for spec in branch_specs:
        # Check if parent has a draft spec
        parent_draft = (await db.execute(
            select(Specification).where(
                Specification.conversation_id == parent_id,
                Specification.status == "draft",
            ).limit(1)
        )).scalar_one_or_none()
        if parent_draft:
            parent_draft.title = spec.title
            parent_draft.content = spec.content
        else:
            new_spec = Specification(
                conversation_id=parent_id,
                title=spec.title,
                content=spec.content,
                status="draft",
            )
            db.add(new_spec)
        counts.specs_copied += 1

    # Copy designs
    branch_designs = (await db.execute(
        select(Design).where(Design.conversation_id == conversation_id)
    )).scalars().all()
    for d in branch_designs:
        new_d = Design(
            conversation_id=parent_id,
            specification_id=d.specification_id,
            title=d.title,
            content=d.content,
            status="draft",
        )
        db.add(new_d)
        counts.designs_copied += 1

    # Copy tasks
    branch_tasks = (await db.execute(
        select(GeneratedTask).where(GeneratedTask.conversation_id == conversation_id)
    )).scalars().all()
    for t in branch_tasks:
        new_t = GeneratedTask(
            conversation_id=parent_id,
            design_id=t.design_id,
            title=t.title,
            description=t.description,
            priority=t.priority,
            status=t.status,
            sort_order=t.sort_order,
        )
        db.add(new_t)
        counts.tasks_copied += 1

    # Copy codes
    branch_codes = (await db.execute(
        select(GeneratedCode).where(GeneratedCode.conversation_id == conversation_id)
    )).scalars().all()
    for c in branch_codes:
        new_c = GeneratedCode(
            conversation_id=parent_id,
            task_id=c.task_id,
            content=c.content,
            status="draft",
        )
        db.add(new_c)
        counts.codes_copied += 1

    # Copy decision points + options
    branch_decisions = (await db.execute(
        select(DecisionPoint).where(DecisionPoint.conversation_id == conversation_id)
    )).scalars().all()
    for dp in branch_decisions:
        new_dp = DecisionPoint(
            conversation_id=parent_id,
            question=dp.question,
            context=dp.context,
            recommendation=dp.recommendation,
            status=dp.status,
        )
        db.add(new_dp)
        await db.flush()
        # Copy options
        opts = (await db.execute(
            select(DecisionOption).where(DecisionOption.decision_point_id == dp.id)
        )).scalars().all()
        for opt in opts:
            new_opt = DecisionOption(
                decision_point_id=new_dp.id,
                label=opt.label,
                description=opt.description,
                pros=opt.pros,
                cons=opt.cons,
                sort_order=opt.sort_order,
            )
            db.add(new_opt)
        counts.decisions_copied += 1

    # Mark branch as merged
    branch.branch_status = "merged"
    await db.commit()

    return counts
