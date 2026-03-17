"""Incremental spec extractor.

When the spec classifier flags a message exchange as spec-relevant,
this service merges the new information into the living specification.
If no draft spec exists yet, it creates one.

Runs inside an ARQ worker (non-streaming, complete()).
"""

from __future__ import annotations

import logging
import re
from uuid import UUID

from llm_client import ChatMessage, LexoraClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.db.models.specification import Specification

logger = logging.getLogger(__name__)

INCREMENTAL_SPEC_SYSTEM_PROMPT = (
    "You are a living specification maintainer. "
    "You will receive either an existing specification document or nothing (if this is the first extraction), "
    "plus a summary of new spec-relevant content from a conversation.\n\n"
    "Your job:\n"
    "- If an existing spec is provided, MERGE the new information into it. "
    "Do not remove existing content unless it is contradicted by the new information. "
    "Add new sections or bullet points as needed.\n"
    "- If no existing spec is provided, CREATE a new specification document.\n\n"
    "Output format: A complete Markdown specification document with these sections as appropriate:\n"
    "# Title\n"
    "## Overview\n"
    "## Requirements\n"
    "## Technical Details\n"
    "## Constraints\n"
    "## Open Questions\n\n"
    "Output ONLY the Markdown document, no preamble or explanation."
)


def _extract_title(markdown: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
    return match.group(1).strip() if match else fallback


async def incremental_extract(
    session: AsyncSession,
    lexora: LexoraClient,
    conversation_id: UUID,
    user_message: str,
    ai_response: str,
    classification_summary: str,
    categories: list[str],
) -> Specification | None:
    """Merge new spec-relevant content into the living spec.

    Returns the updated/created Specification, or None on failure.
    """
    # Find existing draft spec
    result = await session.execute(
        select(Specification)
        .where(
            Specification.conversation_id == conversation_id,
            Specification.status == "draft",
        )
        .order_by(Specification.updated_at.desc())
        .limit(1)
    )
    existing_spec = result.scalar_one_or_none()

    # Build prompt
    new_content_block = (
        f"## New content from conversation\n\n"
        f"**Categories**: {', '.join(categories)}\n"
        f"**Summary**: {classification_summary}\n\n"
        f"### User message\n{user_message}\n\n"
        f"### AI response\n{ai_response}"
    )

    if existing_spec:
        user_prompt = (
            f"Here is the existing specification:\n\n{existing_spec.content}\n\n"
            f"---\n\n{new_content_block}\n\n"
            "Merge the new content into the existing specification. "
            "Preserve all existing content and add the new information in the appropriate sections."
        )
    else:
        user_prompt = (
            f"{new_content_block}\n\n"
            "Create a new specification document from this content."
        )

    messages = [
        ChatMessage(role="system", content=settings.localized_prompt(INCREMENTAL_SPEC_SYSTEM_PROMPT)),
        ChatMessage(role="user", content=user_prompt),
    ]

    try:
        full_content = await lexora.complete(messages)

        # Strip think tags
        from llm_client import LexoraClient as LC
        full_content = LC._strip_think_tags(full_content)

        if not full_content.strip():
            logger.warning("Incremental extraction returned empty content")
            return None

        title = _extract_title(full_content, "Living Specification")

        if existing_spec:
            existing_spec.content = full_content
            existing_spec.title = title
            await session.commit()
            await session.refresh(existing_spec)
            logger.info("Updated spec %s for conversation %s", existing_spec.id, conversation_id)
            return existing_spec
        else:
            spec = Specification(
                conversation_id=conversation_id,
                title=title,
                content=full_content,
                status="draft",
            )
            session.add(spec)
            await session.commit()
            await session.refresh(spec)
            logger.info("Created spec %s for conversation %s", spec.id, conversation_id)
            return spec

    except Exception as exc:
        logger.exception("Incremental spec extraction failed: %s", exc)
        return None
