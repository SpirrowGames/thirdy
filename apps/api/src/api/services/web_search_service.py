"""Web search service — uses Brave Search API for real-time tech intelligence."""

import json
import logging
from dataclasses import dataclass, field

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

SEARCH_CATEGORIES = {
    "security": ["{pkg} CVE vulnerability", "{pkg} security advisory"],
    "release": ["{pkg} new release update"],
    "deprecation": ["{pkg} deprecated end of life"],
    "breaking": ["{pkg} breaking change migration"],
}


@dataclass
class SearchResult:
    title: str
    url: str
    description: str
    age: str | None = None  # e.g., "2 days ago"
    source_type: str = "ecosystem"


@dataclass
class WebSearchReport:
    query: str
    results: list[SearchResult] = field(default_factory=list)
    error: str | None = None


class WebSearchService:
    def __init__(self, http: httpx.AsyncClient, redis=None):
        self._http = http
        self._redis = redis
        self._api_key = settings.brave_api_key

    async def search(self, query: str, count: int = 5) -> list[SearchResult]:
        """Run a single Brave Search query."""
        if not self._api_key:
            logger.warning("Brave API key not configured, skipping web search")
            return []

        # Check cache
        if self._redis:
            cache_key = f"thirdy:websearch:{hash(query)}"
            cached = await self._redis.get(cache_key)
            if cached:
                try:
                    return [SearchResult(**r) for r in json.loads(cached)]
                except Exception:
                    pass

        try:
            resp = await self._http.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": count, "freshness": "pm"},
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": self._api_key,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning("Brave Search API error for '%s': %s", query, e)
            return []

        results: list[SearchResult] = []
        for item in data.get("web", {}).get("results", [])[:count]:
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                description=item.get("description", ""),
                age=item.get("age"),
            ))

        # Cache for 24 hours
        if self._redis and results:
            try:
                await self._redis.set(
                    f"thirdy:websearch:{hash(query)}",
                    json.dumps([r.__dict__ for r in results]),
                    ex=86400,
                )
            except Exception:
                pass

        return results

    async def search_for_packages(
        self,
        packages: list[str],
        categories: list[str] | None = None,
    ) -> list[WebSearchReport]:
        """Search for multiple packages across security/release/deprecation categories."""
        if not self._api_key:
            return []

        cats = categories or list(SEARCH_CATEGORIES.keys())
        reports: list[WebSearchReport] = []

        for pkg in packages:
            for cat in cats:
                templates = SEARCH_CATEGORIES.get(cat, [])
                for template in templates[:1]:  # One query per category per package
                    query = template.format(pkg=pkg)
                    results = await self.search(query, count=3)
                    # Tag results with source_type
                    for r in results:
                        if cat == "security":
                            r.source_type = "security"
                        elif cat == "release":
                            r.source_type = "dependency"
                        elif cat == "deprecation":
                            r.source_type = "ecosystem"
                        elif cat == "breaking":
                            r.source_type = "api_change"
                    if results:
                        reports.append(WebSearchReport(query=query, results=results))

        return reports
