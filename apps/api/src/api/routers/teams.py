"""Team management endpoints — create, list, members, invite."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.db.models import Team, TeamMember, User
from api.dependencies import get_current_user, get_db

router = APIRouter(prefix="/teams", tags=["teams"])


class TeamCreate(BaseModel):
    name: str


class MemberAdd(BaseModel):
    email: str
    role: str = "editor"  # owner, editor, viewer


class MemberUpdate(BaseModel):
    role: str


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_team(
    body: TeamCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a team. The creator is auto-added as owner."""
    team = Team(name=body.name, created_by=user.id)
    db.add(team)
    await db.flush()

    member = TeamMember(team_id=team.id, user_id=user.id, role="owner")
    db.add(member)
    await db.commit()
    await db.refresh(team)

    return {
        "id": str(team.id),
        "name": team.name,
        "created_at": team.created_at.isoformat(),
    }


@router.get("")
async def list_teams(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List teams the current user belongs to."""
    result = await db.execute(
        select(Team)
        .join(TeamMember, Team.id == TeamMember.team_id)
        .where(TeamMember.user_id == user.id)
        .options(selectinload(Team.members))
    )
    teams = result.scalars().unique().all()
    return [
        {
            "id": str(t.id),
            "name": t.name,
            "member_count": len(t.members),
            "my_role": next((m.role for m in t.members if m.user_id == user.id), None),
            "created_at": t.created_at.isoformat(),
        }
        for t in teams
    ]


@router.get("/{team_id}/members")
async def list_members(
    team_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List members of a team."""
    # Verify user is a member
    membership = await _get_membership(team_id, user.id, db)
    if membership is None:
        raise HTTPException(status_code=403, detail="Not a member of this team")

    result = await db.execute(
        select(TeamMember, User)
        .join(User, TeamMember.user_id == User.id)
        .where(TeamMember.team_id == team_id)
    )
    rows = result.all()
    return [
        {
            "id": str(m.id),
            "user_id": str(u.id),
            "email": u.email,
            "name": u.name,
            "role": m.role,
            "joined_at": m.joined_at.isoformat(),
        }
        for m, u in rows
    ]


@router.post("/{team_id}/members")
async def add_member(
    team_id: UUID,
    body: MemberAdd,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a member by email. Requires owner role."""
    membership = await _get_membership(team_id, user.id, db)
    if membership is None or membership.role != "owner":
        raise HTTPException(status_code=403, detail="Only team owners can add members")

    # Find user by email
    result = await db.execute(select(User).where(User.email == body.email))
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Check not already member
    existing = await _get_membership(team_id, target_user.id, db)
    if existing:
        raise HTTPException(status_code=409, detail="Already a member")

    member = TeamMember(team_id=team_id, user_id=target_user.id, role=body.role)
    db.add(member)
    await db.commit()
    return {"user_id": str(target_user.id), "email": target_user.email, "role": body.role}


@router.patch("/{team_id}/members/{member_id}")
async def update_member_role(
    team_id: UUID,
    member_id: UUID,
    body: MemberUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a member's role. Requires owner role."""
    membership = await _get_membership(team_id, user.id, db)
    if membership is None or membership.role != "owner":
        raise HTTPException(status_code=403, detail="Only team owners can update roles")

    result = await db.execute(
        select(TeamMember).where(TeamMember.id == member_id, TeamMember.team_id == team_id)
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="Member not found")

    target.role = body.role
    await db.commit()
    return {"id": str(target.id), "role": target.role}


@router.delete("/{team_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    team_id: UUID,
    member_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a member. Requires owner role."""
    membership = await _get_membership(team_id, user.id, db)
    if membership is None or membership.role != "owner":
        raise HTTPException(status_code=403, detail="Only team owners can remove members")

    result = await db.execute(
        select(TeamMember).where(TeamMember.id == member_id, TeamMember.team_id == team_id)
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="Member not found")

    await db.delete(target)
    await db.commit()


async def _get_membership(team_id: UUID, user_id: UUID, db: AsyncSession) -> TeamMember | None:
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()
