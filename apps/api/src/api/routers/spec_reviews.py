from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Conversation, Specification, SpecReview, User
from api.dependencies import get_background_job_service, get_current_user, get_db
from api.services.background_job_service import BackgroundJobService
from shared_schemas.spec_review import (
    SpecReviewRead,
    SpecReviewTriggerRequest,
    SpecReviewTriggerResponse,
    SuggestionApplyRequest,
    SuggestionApplyResponse,
)

router = APIRouter(tags=["spec-reviews"])


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


async def _get_specification(
    spec_id: UUID,
    conversation_id: UUID,
    db: AsyncSession,
) -> Specification:
    result = await db.execute(
        select(Specification).where(
            Specification.id == spec_id,
            Specification.conversation_id == conversation_id,
        )
    )
    spec = result.scalar_one_or_none()
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Specification not found",
        )
    return spec


@router.post(
    "/conversations/{conversation_id}/specs/{spec_id}/review",
    response_model=SpecReviewTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_spec_review(
    conversation_id: UUID,
    spec_id: UUID,
    body: SpecReviewTriggerRequest | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    job_service: BackgroundJobService = Depends(get_background_job_service),
):
    conversation = await _get_user_conversation(conversation_id, user, db)
    spec = await _get_specification(spec_id, conversation_id, db)
    scope = body.scope if body else "full"

    job = await job_service.enqueue(
        job_type="spec_review",
        func_name="spec_review_job",
        payload={
            "specification_id": str(spec.id),
            "conversation_id": str(conversation.id),
            "scope": scope,
        },
    )
    return SpecReviewTriggerResponse(
        job_id=job.job_id,
        specification_id=spec.id,
        conversation_id=conversation.id,
        message="Spec review job enqueued",
    )


@router.get(
    "/conversations/{conversation_id}/specs/{spec_id}/reviews",
    response_model=list[SpecReviewRead],
)
async def list_spec_reviews(
    conversation_id: UUID,
    spec_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_conversation(conversation_id, user, db)
    await _get_specification(spec_id, conversation_id, db)
    result = await db.execute(
        select(SpecReview)
        .where(
            SpecReview.specification_id == spec_id,
            SpecReview.conversation_id == conversation_id,
        )
        .order_by(SpecReview.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get(
    "/conversations/{conversation_id}/specs/{spec_id}/reviews/{review_id}",
    response_model=SpecReviewRead,
)
async def get_spec_review(
    conversation_id: UUID,
    spec_id: UUID,
    review_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_conversation(conversation_id, user, db)
    result = await db.execute(
        select(SpecReview).where(
            SpecReview.id == review_id,
            SpecReview.specification_id == spec_id,
        )
    )
    review = result.scalar_one_or_none()
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Spec review not found",
        )
    return review


@router.patch(
    "/conversations/{conversation_id}/specs/{spec_id}/reviews/{review_id}/suggestions/{suggestion_idx}/apply",
    response_model=SuggestionApplyResponse,
)
async def apply_suggestion(
    conversation_id: UUID,
    spec_id: UUID,
    review_id: UUID,
    suggestion_idx: int,
    body: SuggestionApplyRequest | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_conversation(conversation_id, user, db)
    spec = await _get_specification(spec_id, conversation_id, db)

    result = await db.execute(
        select(SpecReview).where(
            SpecReview.id == review_id,
            SpecReview.specification_id == spec_id,
        )
    )
    review = result.scalar_one_or_none()
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Spec review not found",
        )

    suggestions = review.suggestions or []
    if suggestion_idx < 0 or suggestion_idx >= len(suggestions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Suggestion index {suggestion_idx} out of range (0-{len(suggestions) - 1})",
        )

    suggestion = suggestions[suggestion_idx]
    if suggestion.get("status") == "applied":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Suggestion already applied",
        )

    confirm = body.confirm if body else False
    before_text = suggestion.get("before")
    after_text = suggestion.get("after")

    # Generate diff preview
    preview_diff = _generate_diff(spec.content, before_text, after_text)

    if not confirm:
        return SuggestionApplyResponse(
            preview_diff=preview_diff,
            applied=False,
        )

    # Apply the suggestion
    if before_text and after_text and before_text in spec.content:
        spec.content = spec.content.replace(before_text, after_text, 1)
    elif after_text:
        # Append to the relevant section or end
        section = suggestion.get("section")
        if section and section in spec.content:
            # Insert after section header
            section_pos = spec.content.find(section)
            next_section = spec.content.find("\n## ", section_pos + len(section))
            if next_section != -1:
                spec.content = (
                    spec.content[:next_section]
                    + "\n" + after_text + "\n"
                    + spec.content[next_section:]
                )
            else:
                spec.content = spec.content + "\n\n" + after_text
        else:
            spec.content = spec.content + "\n\n" + after_text

    # Update suggestion status
    suggestions[suggestion_idx]["status"] = "applied"
    review.suggestions = suggestions
    # Force SQLAlchemy to detect the change on JSON column
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(review, "suggestions")

    await db.commit()
    await db.refresh(spec)

    return SuggestionApplyResponse(
        preview_diff=preview_diff,
        applied=True,
        updated_content=spec.content,
    )


@router.patch(
    "/conversations/{conversation_id}/specs/{spec_id}/reviews/{review_id}/suggestions/{suggestion_idx}/dismiss",
    response_model=SuggestionApplyResponse,
)
async def dismiss_suggestion(
    conversation_id: UUID,
    spec_id: UUID,
    review_id: UUID,
    suggestion_idx: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_conversation(conversation_id, user, db)
    result = await db.execute(
        select(SpecReview).where(
            SpecReview.id == review_id,
            SpecReview.specification_id == spec_id,
        )
    )
    review = result.scalar_one_or_none()
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Spec review not found",
        )

    suggestions = review.suggestions or []
    if suggestion_idx < 0 or suggestion_idx >= len(suggestions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Suggestion index {suggestion_idx} out of range",
        )

    suggestions[suggestion_idx]["status"] = "dismissed"
    review.suggestions = suggestions
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(review, "suggestions")

    await db.commit()

    return SuggestionApplyResponse(applied=False)


@router.delete(
    "/conversations/{conversation_id}/specs/{spec_id}/reviews/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_spec_review(
    conversation_id: UUID,
    spec_id: UUID,
    review_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_conversation(conversation_id, user, db)
    result = await db.execute(
        select(SpecReview).where(
            SpecReview.id == review_id,
            SpecReview.specification_id == spec_id,
        )
    )
    review = result.scalar_one_or_none()
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Spec review not found",
        )
    await db.delete(review)
    await db.commit()


def _generate_diff(content: str, before: str | None, after: str | None) -> str:
    """Generate a simple text diff for preview."""
    if not before and after:
        return f"+ {after}"
    if before and not after:
        return f"- {before}"
    if before and after:
        lines = []
        lines.append(f"- {before}")
        lines.append(f"+ {after}")
        return "\n".join(lines)
    return ""
