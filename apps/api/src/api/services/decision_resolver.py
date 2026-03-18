"""Auto-resolve decision points from conversation context.

After each chat response, checks if any pending decisions have been
resolved by the latest exchange. Uses lightweight LLM classification.
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

DECISION_RESOLVE_SYSTEM_PROMPT = (
    "You are a decision resolution detector. Given a list of pending decisions "
    "and a new conversation exchange, determine if any decision has been resolved.\n\n"
    "A decision is resolved when:\n"
    "- The user explicitly chooses an option (e.g., 'Let's go with JWT', 'Option A sounds good')\n"
    "- The user and AI reach a clear consensus on an approach\n"
    "- The user dismisses the decision as no longer relevant\n\n"
    "A decision is NOT resolved when:\n"
    "- Still discussing trade-offs without a clear choice\n"
    "- Asking follow-up questions about options\n"
    "- The topic is unrelated to any pending decision\n\n"
    "Respond ONLY with a JSON object:\n"
    "{\n"
    '  "resolved_decisions": [\n'
    '    {"decision_id": "uuid", "chosen_option_label": "the option label chosen (or null if dismissed)", "resolution_note": "brief explanation"}\n'
    "  ]\n"
    "}\n\n"
    "If no decisions are resolved, return: {\"resolved_decisions\": []}\n\n"
    "IMPORTANT: Output ONLY the JSON object. Do NOT include any thinking, reasoning, or explanation. /no_think"
)


async def check_and_resolve_decisions(
    session: AsyncSession,
    lexora: LexoraClient,
    conversation_id: UUID,
    user_message: str,
    ai_response: str,
) -> list[str]:
    """Check if any pending decisions are resolved by the latest exchange.

    Returns list of resolved decision point IDs.
    """
    # Load pending decisions with options
    result = await session.execute(
        select(DecisionPoint)
        .where(
            DecisionPoint.conversation_id == conversation_id,
            DecisionPoint.status == "pending",
        )
    )
    pending = result.scalars().all()

    if not pending:
        return []

    # Build decision list for prompt
    decision_list = []
    decision_map: dict[str, DecisionPoint] = {}
    options_map: dict[str, dict[str, DecisionOption]] = {}  # decision_id -> {label -> option}

    for dp in pending:
        opts_result = await session.execute(
            select(DecisionOption).where(DecisionOption.decision_point_id == dp.id)
        )
        opts = opts_result.scalars().all()

        dp_id = str(dp.id)
        decision_map[dp_id] = dp
        options_map[dp_id] = {o.label.lower(): o for o in opts}

        opt_labels = [o.label for o in opts]
        decision_list.append(
            f"- Decision ID: {dp_id}\n"
            f"  Question: {dp.question}\n"
            f"  Options: {', '.join(opt_labels)}"
        )

    prompt = (
        f"## Pending Decisions\n\n"
        f"{''.join(decision_list)}\n\n"
        f"## Latest Exchange\n\n"
        f"**User**: {user_message}\n\n"
        f"**AI**: {ai_response}"
    )

    messages = [
        ChatMessage(role="system", content=DECISION_RESOLVE_SYSTEM_PROMPT),
        ChatMessage(role="user", content=prompt),
    ]

    try:
        json_model = settings.lexora_json_model or None
        raw = await lexora.complete(messages, model=json_model, json_mode=True)
        parsed = json.loads(raw)
        resolved_list = parsed.get("resolved_decisions", [])
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Decision resolution check failed: %s", exc)
        return []

    resolved_ids = []
    for item in resolved_list:
        dp_id = item.get("decision_id", "")
        chosen_label = item.get("chosen_option_label")
        note = item.get("resolution_note", "")

        if dp_id not in decision_map:
            continue

        dp = decision_map[dp_id]

        # Find matching option
        resolved_option_id = None
        if chosen_label:
            label_lower = chosen_label.lower()
            opts = options_map.get(dp_id, {})
            # Exact match first, then substring
            matched = opts.get(label_lower)
            if not matched:
                for key, opt in opts.items():
                    if label_lower in key or key in label_lower:
                        matched = opt
                        break
            if matched:
                resolved_option_id = matched.id

        dp.status = "resolved"
        dp.resolved_option_id = resolved_option_id
        dp.resolution_note = f"自動検出: {note}" if note else "会話から自動検出"
        resolved_ids.append(dp_id)
        logger.info("Auto-resolved decision %s: %s", dp_id, chosen_label or "dismissed")

    if resolved_ids:
        await session.commit()

    return resolved_ids
