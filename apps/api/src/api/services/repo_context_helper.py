"""Helper to resolve and inject repo context into LLM prompts.

Used by pipeline endpoints (designs, codes, pull_requests) to enrich
LLM prompts with repository structure and patterns.
"""

from __future__ import annotations

import logging

import httpx
from llm_client import LexoraClient

from api.config import settings
from api.services.github import GitHubClient
from api.services.repo_context_service import fetch_repo_context

logger = logging.getLogger(__name__)


async def get_repo_context_for_conversation(
    github_repo: str | None,
    lexora: LexoraClient,
    redis=None,
) -> str:
    """Get repo context prompt section for a conversation.

    Returns a formatted context string, or empty string if no repo is configured.
    """
    if not github_repo or not settings.github_token:
        return ""

    parts = github_repo.split("/", 1)
    if len(parts) == 2:
        owner, repo = parts
    else:
        owner = settings.github_org or settings.github_owner
        repo = parts[0]

    if not owner or not repo:
        return ""

    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            gh = GitHubClient(
                token=settings.github_token,
                owner=owner,
                repo=repo,
                http=http,
            )
            ctx = await fetch_repo_context(gh, owner, repo, redis=redis, lexora=lexora)
        return ctx.to_prompt_context()
    except Exception as exc:
        logger.warning("Failed to get repo context for %s: %s", github_repo, exc)
        return ""
