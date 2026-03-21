"""Tech stack detector — extracts dependencies from repo manifest files."""

import json
import logging
import re
from dataclasses import dataclass, field

from api.services.github import GitHubClient, GitHubError

logger = logging.getLogger(__name__)

# Manifest files to look for
MANIFEST_FILES = [
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "go.mod",
    "Cargo.toml",
]


@dataclass
class TechStackItem:
    name: str
    version: str
    ecosystem: str  # npm / pypi / go / cargo
    source_file: str
    is_dev: bool = False


@dataclass
class TechStack:
    items: list[TechStackItem] = field(default_factory=list)
    npm_deps: dict[str, str] = field(default_factory=dict)
    pypi_deps: dict[str, str] = field(default_factory=dict)
    detected_files: list[str] = field(default_factory=list)

    @property
    def package_names(self) -> list[str]:
        """All unique package names for web search."""
        return list({item.name for item in self.items if not item.is_dev})


class TechStackDetector:
    def __init__(self, github: GitHubClient):
        self._github = github

    async def detect(self) -> TechStack:
        """Detect tech stack from repo manifest files."""
        stack = TechStack()

        # Get repo tree to find manifest files
        try:
            tree = await self._github.get_repo_tree()
        except GitHubError as e:
            logger.warning("Failed to get repo tree: %s", e)
            return stack

        paths = {item["path"] for item in tree if item["type"] == "blob"}

        # Check root and common subdirectories
        for manifest in MANIFEST_FILES:
            candidates = [manifest]
            # Also check common subdirectory patterns
            for prefix in ["apps/api/", "apps/web/", "backend/", "frontend/", "server/", "client/"]:
                candidates.append(prefix + manifest)

            for path in candidates:
                if path in paths:
                    try:
                        content = await self._github.get_file_content(path)
                        self._parse_manifest(stack, path, content)
                    except GitHubError:
                        continue

        return stack

    def _parse_manifest(self, stack: TechStack, path: str, content: str) -> None:
        """Parse a manifest file and add items to the stack."""
        stack.detected_files.append(path)
        filename = path.split("/")[-1]

        if filename == "package.json":
            self._parse_package_json(stack, path, content)
        elif filename == "pyproject.toml":
            self._parse_pyproject_toml(stack, path, content)
        elif filename == "requirements.txt":
            self._parse_requirements_txt(stack, path, content)

    def _parse_package_json(self, stack: TechStack, path: str, content: str) -> None:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return

        for name, version in data.get("dependencies", {}).items():
            stack.items.append(TechStackItem(
                name=name, version=version, ecosystem="npm",
                source_file=path, is_dev=False,
            ))
            stack.npm_deps[name] = version

        for name, version in data.get("devDependencies", {}).items():
            stack.items.append(TechStackItem(
                name=name, version=version, ecosystem="npm",
                source_file=path, is_dev=True,
            ))

    def _parse_pyproject_toml(self, stack: TechStack, path: str, content: str) -> None:
        # Simple TOML parsing for dependencies (avoid tomllib dependency)
        in_deps = False
        in_optional = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped == "[project]":
                continue
            if stripped.startswith("["):
                in_deps = "dependencies" in stripped.lower()
                in_optional = "optional" in stripped.lower() or "dev" in stripped.lower()
                continue
            if in_deps and stripped and not stripped.startswith("#"):
                # Parse "package>=1.0" or '"package>=1.0"' patterns
                cleaned = stripped.strip('", ')
                if not cleaned:
                    continue
                m = re.match(r'^([a-zA-Z0-9_-]+)\s*([><=!~]+.+)?$', cleaned)
                if m:
                    name = m.group(1)
                    version = m.group(2) or "*"
                    stack.items.append(TechStackItem(
                        name=name, version=version.strip(),
                        ecosystem="pypi", source_file=path,
                        is_dev=in_optional,
                    ))
                    if not in_optional:
                        stack.pypi_deps[name] = version.strip()

    def _parse_requirements_txt(self, stack: TechStack, path: str, content: str) -> None:
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("-"):
                continue
            m = re.match(r'^([a-zA-Z0-9_.-]+)\s*([><=!~]+.+)?$', stripped)
            if m:
                name = m.group(1)
                version = m.group(2) or "*"
                stack.items.append(TechStackItem(
                    name=name, version=version.strip(),
                    ecosystem="pypi", source_file=path,
                ))
                stack.pypi_deps[name] = version.strip()
