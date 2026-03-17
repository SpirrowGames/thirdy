"""Incremental decision point extractor.

When the decision classifier flags a message exchange as containing a decision
point, this service creates a DecisionPoint + DecisionOptions in the DB.
Skips if a similar question already exists for the conversation.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from llm_client import ChatMessage, LexoraClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.db.models.decision_point import DecisionOption, DecisionPoint

logger = logging.getLogger(__name__)

DECISION_EXTRACT_SYSTEM_PROMPT = (
    "You are a decision analysis assistant. Given a conversation excerpt that "
    "contains a decision point, extract the decision with its options.\n\n"
    "Respond ONLY with a JSON object:\n"
    "{\n"
    '  "question": "The decision that needs to be made",\n'
    '  "context": "Relevant context from the conversation",\n'
    '  "recommendation": "Your recommended option (or null)",\n'
    '  "options": [\n'
    '    {"label": "Option name", "description": "Explanation", "pros": ["..."], "cons": ["..."]},\n'
    '    {"label": "Option name", "description": "Explanation", "pros": ["..."], "cons": ["..."]}\n'
    "  ]\n"
    "}\n\n"
    "Provide at least 2 options. Each option must have a label and at least one pro and con.\n\n"
    "IMPORTANT: Output ONLY the JSON object. Do NOT include any thinking, reasoning, or explanation. /no_think"
)


async def _is_duplicate(
    session: AsyncSession,
    conversation_id: UUID,
    question: str,
) -> bool:
    """Check if a similar decision point already exists (simple substring match)."""
    result = await session.execute(
        select(DecisionPoint).where(
            DecisionPoint.conversation_id == conversation_id,
            DecisionPoint.status == "pending",
        )
    )
    existing = result.scalars().all()
    q_lower = question.lower()
    for dp in existing:
        # Simple overlap check: if >50% of words overlap, consider duplicate
        existing_words = set(dp.question.lower().split())
        new_words = set(q_lower.split())
        if not existing_words or not new_words:
            continue
        overlap = len(existing_words & new_words) / max(len(existing_words), len(new_words))
        if overlap > 0.5:
            return True
    return False


async def incremental_extract_decision(
    session: AsyncSession,
    lexora: LexoraClient,
    conversation_id: UUID,
    user_message: str,
    ai_response: str,
    question_hint: str,
    options_hint: list[str],
    context_hint: str,
) -> DecisionPoint | None:
    """Extract a decision point and create it in the DB.

    Returns the created DecisionPoint, or None on failure/duplicate.
    """
    # Check for duplicates
    if await _is_duplicate(session, conversation_id, question_hint):
        logger.info("Skipping duplicate decision point: %s", question_hint[:80])
        return None

    # Build prompt
    prompt = (
        f"## Conversation excerpt\n\n"
        f"**User**: {user_message}\n\n"
        f"**AI**: {ai_response}\n\n"
        f"## Hint\n"
        f"The decision question is roughly: {question_hint}\n"
        f"Possible options: {', '.join(options_hint) if options_hint else 'not specified'}\n"
        f"Context: {context_hint}"
    )

    messages = [
        ChatMessage(role="system", content=settings.localized_prompt(DECISION_EXTRACT_SYSTEM_PROMPT)),
        ChatMessage(role="user", content=prompt),
    ]

    try:
        json_model = settings.lexora_json_model or None
        raw = await lexora.complete(messages, model=json_model, json_mode=True)
        parsed = json.loads(raw)

        question = parsed.get("question", question_hint)
        context = parsed.get("context", context_hint)
        recommendation = parsed.get("recommendation")
        options_data = parsed.get("options", [])

        if not question or not options_data:
            logger.warning("Decision extraction returned empty question or options")
            return None

        # Re-check duplicate with the refined question
        if await _is_duplicate(session, conversation_id, question):
            logger.info("Skipping duplicate decision (refined): %s", question[:80])
            return None

        # Create DecisionPoint
        dp = DecisionPoint(
            conversation_id=conversation_id,
            question=question,
            context=context,
            recommendation=recommendation,
            status="pending",
        )
        session.add(dp)
        await session.flush()  # Get dp.id

        # Create DecisionOptions
        for i, opt in enumerate(options_data):
            pros = opt.get("pros", [])
            cons = opt.get("cons", [])
            option = DecisionOption(
                decision_point_id=dp.id,
                label=opt.get("label", f"Option {i+1}"),
                description=opt.get("description"),
                pros=json.dumps(pros) if isinstance(pros, list) else str(pros),
                cons=json.dumps(cons) if isinstance(cons, list) else str(cons),
                sort_order=i,
            )
            session.add(option)

        await session.commit()
        await session.refresh(dp)
        logger.info("Created decision point %s for conversation %s", dp.id, conversation_id)
        return dp

    except (json.JSONDecodeError, Exception) as exc:
        logger.exception("Decision extraction failed: %s", exc)
        return None
