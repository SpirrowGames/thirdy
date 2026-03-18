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
        self._model_limits: dict[str, int] = {}  # model -> max_model_len cache

    @property
    def completions_url(self) -> str:
        return f"{self._base_url}/v1/chat/completions"

    async def get_model_max_tokens(self, model: str) -> int | None:
        """Get max_model_len for a model from /v1/models. Cached after first call."""
        if model in self._model_limits:
            return self._model_limits[model]
        try:
            resp = await self._http.get(f"{self._base_url}/v1/models", timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("data", []):
                    mid = m.get("id", "")
                    limit = m.get("max_model_len")
                    if limit:
                        self._model_limits[mid] = int(limit)
            return self._model_limits.get(model)
        except Exception:
            return None

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
