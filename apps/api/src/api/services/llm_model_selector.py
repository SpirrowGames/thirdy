"""Dynamic LLM model selection based on prompt size and model limits.

Chooses between the JSON-specialized model (e.g., Qwen3 via vLLM) and the
default model (e.g., Claude Code) based on the prompt's estimated token count
versus the model's max_model_len retrieved from /v1/models.
"""

from __future__ import annotations

import logging

from llm_client import ChatMessage, LexoraClient

from api.config import settings

logger = logging.getLogger(__name__)


async def select_json_model(
    lexora: LexoraClient,
    messages: list[ChatMessage],
    fallback_model: str | None = None,
    safety_margin: float = 0.7,
) -> tuple[str | None, bool]:
    """Select the best model for JSON output based on prompt size.

    Returns:
        (model_name, use_json_mode) tuple.
        - If JSON model can handle it: (json_model, True)
        - If too large: (fallback_model or lexora_fallback_model, False)
    """
    json_model = settings.lexora_json_model
    if not json_model:
        return fallback_model, False

    max_tokens = await lexora.get_model_max_tokens(json_model)
    if max_tokens is None:
        # Unknown limit — try JSON model anyway
        return json_model, True

    # Estimate tokens: ~2 tokens per char for mixed CJK/ASCII (conservative)
    prompt_chars = sum(len(m.content) for m in messages)
    est_tokens = prompt_chars * 2

    if est_tokens < max_tokens * safety_margin:
        return json_model, True

    # Fallback: prefer configured fallback model > caller's fallback > json model anyway
    effective_fallback = settings.lexora_fallback_model or fallback_model
    if effective_fallback:
        logger.info(
            "Prompt too large for %s (~%d tokens, limit %d), falling back to %s",
            json_model, est_tokens, max_tokens, effective_fallback,
        )
        return effective_fallback, False

    # No fallback available, try json model anyway (may timeout)
    logger.warning(
        "Prompt large for %s (~%d tokens, limit %d) but no fallback configured",
        json_model, est_tokens, max_tokens,
    )
    return json_model, True
