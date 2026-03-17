"""Lightweight decision-point classifier.

Called after each AI response to determine whether the latest exchange
contains a decision point (trade-offs, ambiguities, technical choices, etc.).
Uses the JSON-capable model (Qwen3) via lexora.complete().
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from llm_client import ChatMessage, LexoraClient

from api.config import settings

logger = logging.getLogger(__name__)

DECISION_CLASSIFY_SYSTEM_PROMPT = (
    "You are a decision point classifier. "
    "Given a user message and an AI response from a conversation, "
    "determine whether the exchange contains a decision point that needs to be resolved.\n\n"
    "A decision point includes:\n"
    "- Trade-offs between two or more approaches\n"
    "- Technology or library selection choices\n"
    "- Architecture decisions (monolith vs microservices, REST vs GraphQL, etc.)\n"
    "- Ambiguous requirements that need clarification\n"
    "- Scope decisions (include feature X or not)\n"
    "- Design pattern choices\n\n"
    "NOT a decision point:\n"
    "- Already resolved decisions (user clearly chose one option)\n"
    "- Factual questions with a single correct answer\n"
    "- Greetings, small talk, or meta-conversation\n"
    "- Implementation details that don't involve trade-offs\n\n"
    "Respond ONLY with a JSON object:\n"
    "{\n"
    '  "has_decision_point": true/false,\n'
    '  "question": "The decision question in a clear, concise sentence (empty string if none)",\n'
    '  "options_hint": ["Option A short label", "Option B short label"],\n'
    '  "context": "One-sentence context from the conversation (empty string if none)"\n'
    "}\n\n"
    "If no decision point, return has_decision_point=false with empty strings and empty array.\n\n"
    "IMPORTANT: Output ONLY the JSON object. Do NOT include any thinking, reasoning, or explanation. /no_think"
)


@dataclass
class DecisionClassificationResult:
    has_decision_point: bool
    question: str
    options_hint: list[str]
    context: str


async def classify_decision(
    lexora: LexoraClient,
    user_message: str,
    ai_response: str,
) -> DecisionClassificationResult:
    """Classify whether the latest exchange contains a decision point.

    On any failure returns has_decision_point=False so the pipeline skips.
    """
    prompt = f"## User message\n{user_message}\n\n## AI response\n{ai_response}"

    messages = [
        ChatMessage(role="system", content=DECISION_CLASSIFY_SYSTEM_PROMPT),
        ChatMessage(role="user", content=prompt),
    ]

    try:
        json_model = settings.lexora_json_model or None
        raw = await lexora.complete(messages, model=json_model, json_mode=True)
        parsed = json.loads(raw)
        return DecisionClassificationResult(
            has_decision_point=bool(parsed.get("has_decision_point", False)),
            question=parsed.get("question", ""),
            options_hint=parsed.get("options_hint", []),
            context=parsed.get("context", ""),
        )
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Decision classification failed, skipping: %s", exc)
        return DecisionClassificationResult(
            has_decision_point=False,
            question="",
            options_hint=[],
            context="",
        )
