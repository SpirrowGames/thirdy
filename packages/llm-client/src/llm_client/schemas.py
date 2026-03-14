from __future__ import annotations

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # "system" | "user" | "assistant"
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float = 0.7
    max_tokens: int | None = None


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatMessage | None = None
    delta: dict | None = None
    finish_reason: str | None = None


class ChatCompletionResponse(BaseModel):
    id: str
    choices: list[ChatCompletionChoice]


class ChatCompletionChunk(BaseModel):
    id: str
    choices: list[ChatCompletionChoice]
