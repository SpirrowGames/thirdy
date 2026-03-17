from __future__ import annotations

import json
from collections.abc import AsyncGenerator

import httpx

from .schemas import ChatCompletionRequest, ChatCompletionResponse, ChatMessage, ResponseFormat


class LexoraClient:
    """Client for Lexora LLM proxy (OpenAI-compatible API)."""

    def __init__(self, http_client: httpx.AsyncClient, base_url: str, default_model: str = "gpt-4o") -> None:
        self._http = http_client
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model

    @property
    def completions_url(self) -> str:
        return f"{self._base_url}/v1/chat/completions"

    async def complete(self, messages: list[ChatMessage], model: str | None = None, json_mode: bool = False) -> str:
        """Non-streaming completion. Use json_mode=True for structured JSON output."""
        request = ChatCompletionRequest(
            model=model or self._default_model,
            messages=messages,
            stream=False,
            response_format=ResponseFormat(type="json_object") if json_mode else None,
        )
        payload = request.model_dump(exclude_none=True)
        response = await self._http.post(
            self.completions_url,
            json=payload,
            timeout=600.0,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return self._strip_think_tags(content)

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
            timeout=600.0,
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
