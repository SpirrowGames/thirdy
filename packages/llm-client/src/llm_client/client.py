from __future__ import annotations

import json
from collections.abc import AsyncGenerator

import httpx

from .schemas import ChatCompletionRequest, ChatCompletionResponse, ChatMessage


class LexoraClient:
    """Client for Lexora LLM proxy (OpenAI-compatible API)."""

    def __init__(self, http_client: httpx.AsyncClient, base_url: str, default_model: str = "gpt-4o") -> None:
        self._http = http_client
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model

    @property
    def completions_url(self) -> str:
        return f"{self._base_url}/v1/chat/completions"

    async def complete(self, messages: list[ChatMessage], model: str | None = None) -> str:
        """Non-streaming completion built on streaming to avoid timeout on slow models."""
        full = ""
        async for token in self.stream(messages, model=model):
            full += token
        return self._strip_think_tags(full)

    @staticmethod
    def _strip_think_tags(text: str) -> str:
        """Remove <think>...</think> blocks and markdown code fences from model output."""
        import re
        # Remove think blocks
        text = re.sub(r"<think>[\s\S]*?</think>\s*", "", text)
        # Remove markdown code fences (```json ... ```)
        text = re.sub(r"```(?:json)?\s*\n?", "", text)
        return text.strip()

    async def stream(self, messages: list[ChatMessage], model: str | None = None) -> AsyncGenerator[str]:
        """Streaming completion. Yields content tokens as strings."""
        request = ChatCompletionRequest(
            model=model or self._default_model,
            messages=messages,
            stream=True,
        )
        async with self._http.stream(
            "POST",
            self.completions_url,
            json=request.model_dump(),
            timeout=300.0,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]  # strip "data: " prefix
                if data == "[DONE]":
                    return
                try:
                    chunk = json.loads(data)
                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield content
                except json.JSONDecodeError:
                    continue
