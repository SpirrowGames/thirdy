# === Build stage ===
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/ packages/
COPY apps/api/ apps/api/

RUN uv sync --project apps/api --frozen --no-dev

# === Runtime stage ===
FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/apps/api /app/apps/api
COPY --from=builder /app/packages /app/packages

ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app/apps/api

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
