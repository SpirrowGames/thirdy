"""External Watch service — analyzes project context for external risks via LLM."""

import json
import logging

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
    def __init__(self, session: AsyncSession, lexora: LexoraClient):
        self.session = session
        self.lexora = lexora

    async def run_watch(
        self,
        conversation_id,
        *,
        job_id: str | None = None,
        model: str | None = None,
        targets: list[str] | None = None,
    ) -> WatchReport:
        # 1. Load project context
        specs = await self._load_specifications(conversation_id)
        designs = await self._load_designs(conversation_id)
        codes = await self._load_codes(conversation_id)

        # 2-3. Build prompt and call LLM
        messages = self._build_watch_prompt(specs, designs, codes, targets)
        raw_response = await self.lexora.complete(messages, model=model)

        # 4. Parse response
        parsed = self._parse_watch_response(raw_response)
        findings = parsed.get("findings", [])

        # 5. Compute summary
        summary = self._compute_summary(findings)

        # 6. Save report
        report = WatchReport(
            conversation_id=conversation_id,
            job_id=job_id,
            summary=summary,
            findings=findings,
            watch_targets=targets or [],
            status="completed",
        )
        self.session.add(report)
        await self.session.commit()
        await self.session.refresh(report)
        return report

    async def _load_specifications(self, conversation_id):
        result = await self.session.execute(
            select(Specification).where(
                Specification.conversation_id == conversation_id
            )
        )
        return list(result.scalars().all())

    async def _load_designs(self, conversation_id):
        result = await self.session.execute(
            select(Design).where(Design.conversation_id == conversation_id)
        )
        return list(result.scalars().all())

    async def _load_codes(self, conversation_id):
        result = await self.session.execute(
            select(GeneratedCode).where(
                GeneratedCode.conversation_id == conversation_id
            )
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
                # Include only first 500 chars to focus on imports/tech stack
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

        for f in findings:
            impact = f.get("impact_level", "none")
            source = f.get("source_type", "ecosystem")
            by_impact[impact] = by_impact.get(impact, 0) + 1
            by_source[source] = by_source.get(source, 0) + 1

            idx = _IMPACT_ORDER.index(impact) if impact in _IMPACT_ORDER else 0
            if idx > highest_idx:
                highest_idx = idx

        highest_impact = _IMPACT_ORDER[highest_idx]
        requires_action = highest_idx >= 3  # high or critical

        return {
            "total_findings": len(findings),
            "findings_by_impact": by_impact,
            "findings_by_source": by_source,
            "highest_impact": highest_impact,
            "requires_action": requires_action,
        }
