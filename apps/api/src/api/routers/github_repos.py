from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from api.config import settings
from api.db.models import User
from api.dependencies import get_current_user
from api.dependencies import get_lexora_client
from api.services.github import GitHubClient, GitHubError
from api.services.repo_context_service import fetch_repo_context
from llm_client import LexoraClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/github", tags=["github"])


class RepoInfo(BaseModel):
    full_name: str
    name: str
    description: str | None = None
    private: bool = False
    default_branch: str = "main"
    html_url: str = ""


class CreateRepoRequest(BaseModel):
    name: str
    description: str = ""
    private: bool = True


class GitHubConfigStatus(BaseModel):
    configured: bool
    org: str | None = None


@router.get("/config", response_model=GitHubConfigStatus)
async def get_github_config(
    user: User = Depends(get_current_user),
):
    org = settings.github_org or settings.github_owner
    has_token = bool(settings.github_token)
    return GitHubConfigStatus(
        configured=bool(org and has_token),
        org=org if org else None,
    )


def _get_org() -> str:
    org = settings.github_org or settings.github_owner
    if not org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub organization not configured. Set GITHUB_ORG.",
        )
    return org


@router.get("/repos", response_model=list[RepoInfo])
async def list_repos(
    user: User = Depends(get_current_user),
):
    if not settings.github_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub token not configured",
        )
    org = _get_org()
    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            gh = GitHubClient(token=settings.github_token, owner=org, repo="", http=http)
            repos = await gh.list_org_repos(org)
        return [
            RepoInfo(
                full_name=r["full_name"],
                name=r["name"],
                description=r.get("description"),
                private=r.get("private", False),
                default_branch=r.get("default_branch", "main"),
                html_url=r.get("html_url", ""),
            )
            for r in repos
        ]
    except GitHubError as e:
        logger.exception("Failed to list repos")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/repos", response_model=RepoInfo, status_code=status.HTTP_201_CREATED)
async def create_repo(
    body: CreateRepoRequest,
    user: User = Depends(get_current_user),
):
    if not settings.github_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub token not configured",
        )
    org = _get_org()
    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            gh = GitHubClient(token=settings.github_token, owner=org, repo="", http=http)
            r = await gh.create_repo(org, body.name, body.description, body.private)
        return RepoInfo(
            full_name=r["full_name"],
            name=r["name"],
            description=r.get("description"),
            private=r.get("private", False),
            default_branch=r.get("default_branch", "main"),
            html_url=r.get("html_url", ""),
        )
    except GitHubError as e:
        logger.exception("Failed to create repo")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


class RepoContextResponse(BaseModel):
    owner: str
    repo: str
    default_branch: str
    description: str | None = None
    tree_summary: str
    file_count: int
    prompt_context: str


@router.get("/repos/{owner}/{repo}/context", response_model=RepoContextResponse)
async def get_repo_context(
    owner: str,
    repo: str,
    request: Request,
    user: User = Depends(get_current_user),
    lexora: LexoraClient = Depends(get_lexora_client),
):
    """Fetch repository context (structure + key files + LLM summary). Cached in Redis for 5 min."""
    if not settings.github_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub token not configured",
        )
    redis = getattr(request.app.state, "redis_pool", None)
    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            gh = GitHubClient(token=settings.github_token, owner=owner, repo=repo, http=http)
            ctx = await fetch_repo_context(gh, owner, repo, redis=redis, lexora=lexora)
        return RepoContextResponse(
            owner=ctx.owner,
            repo=ctx.repo,
            default_branch=ctx.default_branch,
            description=ctx.description,
            tree_summary=ctx.tree_summary,
            file_count=len(ctx.file_contents),
            prompt_context=ctx.to_prompt_context(),
        )
    except GitHubError as e:
        logger.exception("Failed to fetch repo context")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
