"""Repository context service.

Fetches repo structure and key files from GitHub, caches in Redis,
and provides a compact context string for LLM prompts.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from llm_client import ChatMessage, LexoraClient

from api.config import settings
from api.services.github import GitHubClient, GitHubError

logger = logging.getLogger(__name__)

# Files to always try to fetch content for
PRIORITY_FILES = {
    "README.md", "readme.md", "README.rst",
    "package.json", "pyproject.toml", "Cargo.toml", "go.mod",
    "docker-compose.yml", "docker-compose.yaml", "Dockerfile",
    "tsconfig.json", ".env.example",
}

# Extensions worth including in tree display
CODE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java",
    ".vue", ".svelte", ".rb", ".php", ".cs", ".swift", ".kt",
}

# Max file size to fetch (bytes in base64, ~75KB decoded)
MAX_FILE_SIZE = 100_000

# Max files to fetch content for beyond priority files
MAX_EXTRA_FILES = 5

REDIS_CACHE_TTL = 300  # 5 minutes


REPO_SUMMARIZE_SYSTEM_PROMPT = (
    "You are a codebase analyst. Given a repository's directory structure and key file contents, "
    "produce a concise summary that would help an AI code generator understand the project.\n\n"
    "Include:\n"
    "- Tech stack (languages, frameworks, databases)\n"
    "- Architecture overview (monorepo structure, backend/frontend split, etc.)\n"
    "- Key patterns (naming conventions, file organization, testing approach)\n"
    "- Important configuration (build system, deployment setup)\n\n"
    "Keep the summary under 1500 characters. Output ONLY the summary in Markdown, no preamble."
)


@dataclass
class RepoContext:
    owner: str
    repo: str
    default_branch: str
    description: str | None
    tree_summary: str  # compact directory listing
    file_contents: dict[str, str] = field(default_factory=dict)  # path -> content
    summary: str = ""  # LLM-generated compact summary

    def to_prompt_context(self) -> str:
        """Format as a compact context block for LLM prompts.

        Uses the LLM summary if available, otherwise falls back to raw tree + files.
        """
        parts = [
            f"## Repository Context: {self.owner}/{self.repo}",
            "",
        ]

        if self.summary:
            parts.append(self.summary)
            parts.append("")
            parts.append("### Directory Structure")
            parts.append("```")
            parts.append(self.tree_summary)
            parts.append("```")
        else:
            if self.description:
                parts.append(f"**Description**: {self.description}")
                parts.append("")
            parts.append(f"**Branch**: {self.default_branch}")
            parts.append("")
            parts.append("### Directory Structure")
            parts.append("```")
            parts.append(self.tree_summary)
            parts.append("```")
            parts.append("")
            for path, content in self.file_contents.items():
                display = content[:3000]
                if len(content) > 3000:
                    display += f"\n... (truncated, {len(content)} chars total)"
                parts.append(f"### {path}")
                parts.append("```")
                parts.append(display)
                parts.append("```")
                parts.append("")

        return "\n".join(parts)


def _build_tree_summary(tree_items: list[dict], max_lines: int = 80) -> str:
    """Build a compact directory tree from GitHub API tree response."""
    # Filter to meaningful paths
    paths = []
    for item in tree_items:
        path = item.get("path", "")
        item_type = item.get("type", "")
        # Skip hidden dirs, node_modules, __pycache__, etc.
        skip_prefixes = (".", "node_modules/", "__pycache__/", ".git/", "venv/", ".venv/")
        if any(path.startswith(p) or f"/{p}" in path for p in skip_prefixes):
            continue
        if item_type == "blob":
            paths.append(path)
        elif item_type == "tree":
            paths.append(path + "/")

    # If too many, show only top-level and important subdirs
    if len(paths) > max_lines:
        # Show directories and key files
        dirs = sorted(set(p for p in paths if p.endswith("/")))
        files = sorted(p for p in paths if not p.endswith("/") and "/" not in p)
        result = files + dirs[:max_lines - len(files)]
        return "\n".join(result[:max_lines])

    return "\n".join(sorted(paths)[:max_lines])


def _select_extra_files(tree_items: list[dict]) -> list[str]:
    """Select a few entry-point files to fetch beyond priority files."""
    candidates = []
    for item in tree_items:
        if item.get("type") != "blob":
            continue
        path = item["path"]
        size = item.get("size", 0)
        if size > MAX_FILE_SIZE or size == 0:
            continue
        # Look for entry points and config files in src/app root
        parts = path.split("/")
        ext = "." + parts[-1].rsplit(".", 1)[-1] if "." in parts[-1] else ""
        if ext in CODE_EXTENSIONS and len(parts) <= 3:
            # Prefer files like main.py, app.py, index.ts, etc.
            name = parts[-1].lower()
            if any(kw in name for kw in ("main", "app", "index", "server", "routes", "config")):
                candidates.append((path, size))
    # Sort by size (smaller first) and take top N
    candidates.sort(key=lambda x: x[1])
    return [c[0] for c in candidates[:MAX_EXTRA_FILES]]


async def summarize_repo_context(
    lexora: LexoraClient,
    ctx: RepoContext,
) -> str:
    """Generate a compact LLM summary of the repository."""
    # Build input from raw context
    raw_parts = [f"Repository: {ctx.owner}/{ctx.repo}"]
    if ctx.description:
        raw_parts.append(f"Description: {ctx.description}")
    raw_parts.append(f"\nDirectory structure:\n{ctx.tree_summary}")
    for path, content in ctx.file_contents.items():
        raw_parts.append(f"\n--- {path} ---\n{content[:2000]}")

    raw_input = "\n".join(raw_parts)
    # Truncate to ~8000 chars to stay within model limits
    if len(raw_input) > 8000:
        raw_input = raw_input[:8000] + "\n... (truncated)"

    messages = [
        ChatMessage(role="system", content=REPO_SUMMARIZE_SYSTEM_PROMPT),
        ChatMessage(role="user", content=raw_input),
    ]

    try:
        summary = await lexora.complete(messages)
        from llm_client import LexoraClient as LC
        summary = LC._strip_think_tags(summary)
        return summary.strip()
    except Exception as exc:
        logger.warning("Failed to summarize repo context: %s", exc)
        return ""


async def fetch_repo_context(
    gh: GitHubClient,
    owner: str,
    repo: str,
    redis=None,
    lexora: LexoraClient | None = None,
) -> RepoContext:
    """Fetch repository context. Uses Redis cache if available."""
    cache_key = f"repo_context:{owner}/{repo}"

    # Check cache
    if redis is not None:
        try:
            cached = await redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                return RepoContext(**data)
        except Exception:
            pass

    # Fetch repo info
    try:
        repo_info = await gh.get_repo_info()
    except GitHubError:
        repo_info = {}

    default_branch = repo_info.get("default_branch", "main")
    description = repo_info.get("description")

    # Fetch tree
    try:
        tree_items = await gh.get_repo_tree(default_branch)
    except GitHubError:
        tree_items = []

    tree_summary = _build_tree_summary(tree_items)

    # Fetch priority files
    file_contents: dict[str, str] = {}
    all_paths = {item["path"] for item in tree_items if item.get("type") == "blob"}

    for pf in PRIORITY_FILES:
        if pf in all_paths:
            content = await gh.get_file_content(pf, ref=default_branch)
            if content:
                file_contents[pf] = content

    # Fetch extra entry-point files
    extra_files = _select_extra_files(tree_items)
    for ef in extra_files:
        if ef not in file_contents:
            content = await gh.get_file_content(ef, ref=default_branch)
            if content:
                file_contents[ef] = content

    ctx = RepoContext(
        owner=owner,
        repo=repo,
        default_branch=default_branch,
        description=description,
        tree_summary=tree_summary,
        file_contents=file_contents,
    )

    # Generate LLM summary if lexora client is available
    if lexora is not None:
        ctx.summary = await summarize_repo_context(lexora, ctx)

    # Cache
    if redis is not None:
        try:
            cache_data = {
                "owner": ctx.owner,
                "repo": ctx.repo,
                "default_branch": ctx.default_branch,
                "description": ctx.description,
                "tree_summary": ctx.tree_summary,
                "file_contents": ctx.file_contents,
                "summary": ctx.summary,
            }
            await redis.set(cache_key, json.dumps(cache_data), ex=REDIS_CACHE_TTL)
        except Exception as exc:
            logger.warning("Failed to cache repo context: %s", exc)

    return ctx
