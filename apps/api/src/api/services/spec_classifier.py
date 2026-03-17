"""Lightweight spec-relevance classifier.

Called after each AI response to determine whether the latest exchange
contains content relevant to a specification (requirements, constraints,
decisions, architecture, etc.).  Uses the JSON-capable model (Qwen3)
via lexora.complete() for minimal latency.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from llm_client import ChatMessage, LexoraClient

from api.config import settings

logger = logging.getLogger(__name__)

SPEC_CLASSIFY_SYSTEM_PROMPT = (
    "You are a specification relevance classifier. "
    "Given a user message and an AI response from a conversation, "
    "determine whether the exchange contains content relevant to a software specification.\n\n"
    "Relevant content includes:\n"
    "- Functional or non-functional requirements\n"
    "- Technical constraints or limitations\n"
    "- Architecture or design decisions\n"
    "- API contracts or data models\n"
    "- Performance, security, or compliance requirements\n"
    "- Scope definitions or feature descriptions\n\n"
    "NOT relevant:\n"
    "- Greetings, small talk, or meta-conversation\n"
    "- Questions asking for clarification without providing requirements\n"
    "- Debugging or troubleshooting specific code issues\n"
    "- General knowledge questions unrelated to a project spec\n\n"
    "Respond ONLY with a JSON object:\n"
    "{\n"
    '  "is_spec_relevant": true/false,\n'
    '  "categories": ["requirement", "constraint", "decision", "architecture", "api", "data_model", "security", "performance", "scope"],\n'
    '  "summary": "One-sentence summary of the spec-relevant content (empty string if not relevant)"\n'
    "}\n\n"
    "Only include categories that actually apply. If not relevant, return empty categories and empty summary.\n\n"
    "IMPORTANT: Output ONLY the JSON object. Do NOT include any thinking, reasoning, or explanation. /no_think"
)


@dataclass
class ClassificationResult:
    is_spec_relevant: bool
    categories: list[str]
    summary: str


async def classify_message(
    lexora: LexoraClient,
    user_message: str,
    ai_response: str,
) -> ClassificationResult:
    """Classify whether the latest exchange is spec-relevant.

    Returns a ClassificationResult.  On any failure (parse error, timeout, etc.)
    returns is_spec_relevant=False so the pipeline silently skips extraction.
    """
    prompt = f"## User message\n{user_message}\n\n## AI response\n{ai_response}"

    messages = [
        ChatMessage(role="system", content=SPEC_CLASSIFY_SYSTEM_PROMPT),
        ChatMessage(role="user", content=prompt),
    ]

    try:
        json_model = settings.lexora_json_model or None
        raw = await lexora.complete(messages, model=json_model, json_mode=True)
        parsed = json.loads(raw)
        return ClassificationResult(
            is_spec_relevant=bool(parsed.get("is_spec_relevant", False)),
            categories=parsed.get("categories", []),
            summary=parsed.get("summary", ""),
        )
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Spec classification failed, skipping: %s", exc)
        return ClassificationResult(
            is_spec_relevant=False,
            categories=[],
            summary="",
        )
