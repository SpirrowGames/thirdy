"""External Watch service — multi-source tech intelligence with diff reporting.

Integrates three information sources:
1. Web search (Brave Search API) — real-time security/release/deprecation news
2. Package registries (npm/PyPI/GitHub Advisory) — version diffs & CVEs
3. LLM analysis — ecosystem trends & competitive intelligence
"""

import json
import logging

import httpx
from llm_client import LexoraClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.db.models.design import Design
from api.db.models.generated_code import GeneratedCode
from api.db.models.specification import Specification
from api.db.models.watch_report import WatchReport

logger = logging.getLogger(__name__)

_IMPACT_ORDER = ["none", "low", "medium", "high", "critical"]


class WatchService:
    def __init__(self, session: AsyncSession, lexora: LexoraClient, http: httpx.AsyncClient | None = None, redis=None):
        self.session = session
        self.lexora = lexora
        self._http = http
        self._redis = redis

    async def run_watch(
        self,
        conversation_id,
        *,
        job_id: str | None = None,
        model: str | None = None,
        targets: list[str] | None = None,
        trigger_type: str = "manual",
        github_repo: str | None = None,
    ) -> WatchReport:
        all_findings: list[dict] = []

        # --- Source 1: Package registry checks ---
        tech_stack = None
        if settings.watch_registry_check_enabled and github_repo and self._http:
            try:
                tech_stack = await self._gather_registry_findings(github_repo, all_findings)
            except Exception as e:
                logger.warning("Registry check failed: %s", e)

        # --- Source 2: Web search ---
        if settings.watch_web_search_enabled and self._http:
            try:
                search_packages = targets or (tech_stack.package_names[:10] if tech_stack else [])
                if search_packages:
                    await self._gather_web_search_findings(search_packages, all_findings)
            except Exception as e:
                logger.warning("Web search failed: %s", e)

        # --- Source 3: LLM analysis (existing) ---
        try:
            specs = await self._load_specifications(conversation_id)
            designs = await self._load_designs(conversation_id)
            codes = await self._load_codes(conversation_id)
            await self._gather_llm_findings(specs, designs, codes, targets, model, all_findings)
        except Exception as e:
            logger.warning("LLM analysis failed: %s", e)

        # --- Dedup ---
        all_findings = self._dedup_findings(all_findings)

        # --- Diff with previous report ---
        prev_report = await self._get_previous_report(conversation_id)
        if prev_report and prev_report.findings:
            prev_titles = {f.get("title", "").lower() for f in prev_report.findings}
            for f in all_findings:
                f["is_new"] = f.get("title", "").lower() not in prev_titles
        else:
            for f in all_findings:
                f["is_new"] = True

        # --- Summary ---
        summary = self._compute_summary(all_findings)

        # --- Save ---
        report = WatchReport(
            conversation_id=conversation_id,
            job_id=job_id,
            summary=summary,
            findings=all_findings,
            watch_targets=targets or [],
            status="completed",
            trigger_type=trigger_type,
        )
        self.session.add(report)

        # Notifications for high/critical
        new_high = [f for f in all_findings if f.get("impact_level") in ("high", "critical") and f.get("is_new")]
        if new_high:
            from api.db.models import Notification, Conversation
            conv_result = await self.session.execute(
                select(Conversation.user_id).where(Conversation.id == conversation_id)
            )
            owner_id = conv_result.scalar_one_or_none()
            if owner_id:
                notification = Notification(
                    user_id=owner_id,
                    type="watch_alert",
                    title=f"Watch: {len(new_high)}件の新しい重要な発見",
                    body="; ".join(f["title"] for f in new_high[:3]),
                    link=f"/chat/{conversation_id}",
                )
                self.session.add(notification)

        await self.session.commit()
        await self.session.refresh(report)
        return report

    async def _gather_registry_findings(self, github_repo: str, findings: list[dict]):
        """Check package registries for outdated deps and advisories."""
        from api.services.tech_stack_detector import TechStackDetector
        from api.services.package_registry_service import PackageRegistryService

        parts = github_repo.split("/")
        if len(parts) != 2:
            return None

        github = self._create_github_client(parts[0], parts[1])
        detector = TechStackDetector(github)
        tech_stack = await detector.detect()

        if not tech_stack.items:
            return tech_stack

        registry = PackageRegistryService(self._http)
        report = await registry.check_packages(
            npm_deps=tech_stack.npm_deps or None,
            pypi_deps=tech_stack.pypi_deps or None,
        )

        for pkg in report.outdated:
            impact = "high" if pkg.update_type == "major" else "medium" if pkg.update_type == "minor" else "low"
            findings.append({
                "source_type": "dependency",
                "impact_level": impact,
                "title": f"{pkg.name}: {pkg.current_version} → {pkg.latest_version} ({pkg.update_type})",
                "description": f"{pkg.ecosystem} package {pkg.name} has a {pkg.update_type} update available.",
                "source_url": pkg.registry_url,
                "affected_area": "backend" if pkg.ecosystem == "pypi" else "frontend",
                "recommendation": f"Update {pkg.name} to {pkg.latest_version}",
            })

        for adv in report.advisories:
            findings.append({
                "source_type": "security",
                "impact_level": adv.severity if adv.severity in _IMPACT_ORDER else "high",
                "title": f"Security: {adv.package} ({adv.ghsa_id})",
                "description": adv.summary,
                "source_url": adv.url,
                "affected_area": "backend" if adv.ecosystem == "pypi" else "frontend",
                "recommendation": f"Review advisory {adv.ghsa_id} and update {adv.package}",
            })

        return tech_stack

    async def _gather_web_search_findings(self, packages: list[str], findings: list[dict]):
        """Search the web for security/release/deprecation news."""
        from api.services.web_search_service import WebSearchService

        search_svc = WebSearchService(self._http, redis=self._redis)
        reports = await search_svc.search_for_packages(
            packages,
            categories=["security", "breaking"],
        )

        for report in reports:
            for result in report.results:
                findings.append({
                    "source_type": result.source_type,
                    "impact_level": "medium",
                    "title": result.title[:120],
                    "description": result.description[:300],
                    "source_url": result.url,
                    "affected_area": None,
                    "recommendation": None,
                })

    async def _gather_llm_findings(self, specs, designs, codes, targets, model, findings: list[dict]):
        """Existing LLM-based analysis."""
        messages = self._build_watch_prompt(specs, designs, codes, targets)
        raw_response = await self.lexora.complete(messages, model=model)

        from llm_client import LexoraClient as LC
        raw_response = LC._strip_think_tags(raw_response)

        parsed = self._parse_watch_response(raw_response)
        for f in parsed.get("findings", []):
            f.setdefault("is_new", True)
            findings.append(f)

    def _dedup_findings(self, findings: list[dict]) -> list[dict]:
        """Remove duplicate findings by title similarity."""
        seen: set[str] = set()
        result: list[dict] = []
        for f in findings:
            key = f.get("title", "").lower().strip()[:80]
            if key not in seen:
                seen.add(key)
                result.append(f)
        return result

    async def _get_previous_report(self, conversation_id) -> WatchReport | None:
        result = await self.session.execute(
            select(WatchReport)
            .where(WatchReport.conversation_id == conversation_id)
            .order_by(WatchReport.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _create_github_client(self, owner: str, repo: str):
        from api.services.github import GitHubClient
        return GitHubClient(
            token=settings.github_token,
            owner=owner,
            repo=repo,
            http=self._http,
        )

    async def _load_specifications(self, conversation_id):
        result = await self.session.execute(
            select(Specification).where(Specification.conversation_id == conversation_id)
        )
        return list(result.scalars().all())

    async def _load_designs(self, conversation_id):
        result = await self.session.execute(
            select(Design).where(Design.conversation_id == conversation_id)
        )
        return list(result.scalars().all())

    async def _load_codes(self, conversation_id):
        result = await self.session.execute(
            select(GeneratedCode).where(GeneratedCode.conversation_id == conversation_id)
        )
        return list(result.scalars().all())

    def _build_watch_prompt(self, specs, designs, codes, targets):
        parts = ["# Project Context for External Watch\n"]
        if specs:
            parts.append("## Specifications\n")
            for s in specs:
                parts.append(f"### {s.title}\n{s.content}\n")
        if designs:
            parts.append("## Designs\n")
            for d in designs:
                parts.append(f"### {d.title}\n{d.content}\n")
        if codes:
            parts.append("## Generated Code (technology references)\n")
            for c in codes:
                snippet = c.content[:500] if len(c.content) > 500 else c.content
                parts.append(f"### Code [{c.id}]\n{snippet}\n")
        if targets:
            parts.append(f"\n## Watch Targets\nFocus on: {', '.join(targets)}\n")
        user_content = "\n".join(parts)
        return [
            {"role": "system", "content": settings.localized_prompt(settings.watch_system_prompt)},
            {"role": "user", "content": user_content},
        ]

    def _parse_watch_response(self, raw: str) -> dict:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            if "```" in raw:
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start != -1 and end > start:
                    try:
                        return json.loads(raw[start:end])
                    except json.JSONDecodeError:
                        pass
            logger.warning("Failed to parse watch LLM response as JSON")
            return {"findings": []}

    def _compute_summary(self, findings) -> dict:
        by_impact: dict[str, int] = {}
        by_source: dict[str, int] = {}
        highest_idx = 0
        new_count = 0
        for f in findings:
            impact = f.get("impact_level", "none")
            source = f.get("source_type", "ecosystem")
            by_impact[impact] = by_impact.get(impact, 0) + 1
            by_source[source] = by_source.get(source, 0) + 1
            idx = _IMPACT_ORDER.index(impact) if impact in _IMPACT_ORDER else 0
            if idx > highest_idx:
                highest_idx = idx
            if f.get("is_new"):
                new_count += 1
        highest_impact = _IMPACT_ORDER[highest_idx]
        requires_action = highest_idx >= 3
        return {
            "total_findings": len(findings),
            "new_findings": new_count,
            "findings_by_impact": by_impact,
            "findings_by_source": by_source,
            "highest_impact": highest_impact,
            "requires_action": requires_action,
        }
