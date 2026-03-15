from __future__ import annotations

import base64
import logging

import httpx

logger = logging.getLogger(__name__)


class GitHubError(Exception):
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class GitHubClient:
    def __init__(self, token: str, owner: str, repo: str, http: httpx.AsyncClient):
        self._token = token
        self._owner = owner
        self._repo = repo
        self._http = http
        self._base = f"https://api.github.com/repos/{owner}/{repo}"

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _request(self, method: str, url: str, **kwargs) -> dict:
        resp = await self._http.request(method, url, headers=self._headers, **kwargs)
        if resp.status_code >= 400:
            detail = resp.text
            logger.error("GitHub API error %s %s: %s", method, url, detail)
            raise GitHubError(f"GitHub API {resp.status_code}: {detail}", resp.status_code)
        if resp.status_code == 204:
            return {}
        return resp.json()

    async def get_default_branch_sha(self, base_branch: str) -> str:
        data = await self._request("GET", f"{self._base}/git/ref/heads/{base_branch}")
        return data["object"]["sha"]

    async def create_branch(self, branch_name: str, sha: str) -> None:
        await self._request(
            "POST",
            f"{self._base}/git/refs",
            json={"ref": f"refs/heads/{branch_name}", "sha": sha},
        )

    async def create_or_update_file(
        self, branch: str, path: str, content: str, message: str
    ) -> None:
        encoded = base64.b64encode(content.encode()).decode()
        # Check if file exists to get its sha
        sha = None
        try:
            existing = await self._request(
                "GET", f"{self._base}/contents/{path}", params={"ref": branch}
            )
            sha = existing.get("sha")
        except GitHubError:
            pass

        payload: dict = {
            "message": message,
            "content": encoded,
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha

        await self._request("PUT", f"{self._base}/contents/{path}", json=payload)

    async def create_pull_request(
        self, title: str, body: str, head: str, base: str
    ) -> dict:
        return await self._request(
            "POST",
            f"{self._base}/pulls",
            json={"title": title, "body": body, "head": head, "base": base},
        )

    async def create_issue(
        self, title: str, body: str, labels: list[str] | None = None
    ) -> dict:
        payload: dict = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        return await self._request(
            "POST",
            f"{self._base}/issues",
            json=payload,
        )
