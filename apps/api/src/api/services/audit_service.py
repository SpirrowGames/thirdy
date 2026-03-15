"""Internal Audit service — loads conversation artifacts, calls LLM, parses findings, saves report."""

import json
import logging

from llm_client import LexoraClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.db.models.audit_report import AuditReport
from api.db.models.design import Design
from api.db.models.generated_code import GeneratedCode
from api.db.models.generated_task import GeneratedTask
from api.db.models.specification import Specification

logger = logging.getLogger(__name__)

# Severity penalty weights for score computation
_SEVERITY_PENALTY = {
    "critical": 20,
    "error": 10,
    "warning": 3,
    "info": 1,
}


class AuditService:
    def __init__(self, session: AsyncSession, lexora: LexoraClient):
        self.session = session
        self.lexora = lexora

    async def run_audit(
        self,
        conversation_id,
        *,
        job_id: str | None = None,
        model: str | None = None,
        scope: str = "full",
    ) -> AuditReport:
        # 1. Load artifacts
        specs = await self._load_specifications(conversation_id)
        designs = await self._load_designs(conversation_id)
        tasks = await self._load_tasks(conversation_id)
        codes = await self._load_codes(conversation_id)

        # 2-3. Build prompt and call LLM
        messages = self._build_audit_prompt(specs, designs, tasks, codes, scope)
        raw_response = await self.lexora.complete(messages, model=model)

        # 4. Parse response
        parsed = self._parse_audit_response(raw_response)
        findings = parsed.get("findings", [])

        # 5-6. Compute summary
        summary = self._compute_summary(findings, specs, designs, tasks, codes)

        # 7. Save report
        report = AuditReport(
            conversation_id=conversation_id,
            job_id=job_id,
            summary=summary,
            findings=findings,
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

    async def _load_tasks(self, conversation_id):
        result = await self.session.execute(
            select(GeneratedTask).where(
                GeneratedTask.conversation_id == conversation_id
            )
        )
        return list(result.scalars().all())

    async def _load_codes(self, conversation_id):
        result = await self.session.execute(
            select(GeneratedCode).where(
                GeneratedCode.conversation_id == conversation_id
            )
        )
        return list(result.scalars().all())

    def _build_audit_prompt(self, specs, designs, tasks, codes, scope):
        parts = ["# Artifacts to Audit\n"]

        if specs:
            parts.append("## Specifications\n")
            for s in specs:
                parts.append(f"### [{s.id}] {s.title}\nStatus: {s.status}\n{s.content}\n")

        if designs:
            parts.append("## Designs\n")
            for d in designs:
                parts.append(f"### [{d.id}] {d.title}\nStatus: {d.status}\n{d.content}\n")

        if tasks:
            parts.append("## Tasks\n")
            for t in tasks:
                parts.append(
                    f"### [{t.id}] {t.title}\n"
                    f"Priority: {t.priority} | Status: {t.status}\n{t.description}\n"
                )

        if codes:
            parts.append("## Generated Code\n")
            for c in codes:
                parts.append(f"### [{c.id}]\nStatus: {c.status}\n{c.content}\n")

        user_content = "\n".join(parts)

        return [
            {"role": "system", "content": settings.audit_system_prompt},
            {"role": "user", "content": user_content},
        ]

    def _parse_audit_response(self, raw: str) -> dict:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            if "```" in raw:
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start != -1 and end > start:
                    try:
                        return json.loads(raw[start:end])
                    except json.JSONDecodeError:
                        pass
            logger.warning("Failed to parse audit LLM response as JSON")
            return {"findings": []}

    def _compute_summary(self, findings, specs, designs, tasks, codes) -> dict:
        # Count findings by severity
        by_severity: dict[str, int] = {}
        for f in findings:
            sev = f.get("severity", "info")
            by_severity[sev] = by_severity.get(sev, 0) + 1

        # Compute score: start at 100, subtract penalties
        score = 100
        for f in findings:
            sev = f.get("severity", "info")
            score -= _SEVERITY_PENALTY.get(sev, 1)
        score = max(score, 0)

        # Badge
        if score >= 90:
            badge = "excellent"
        elif score >= 70:
            badge = "good"
        elif score >= 50:
            badge = "needs_improvement"
        else:
            badge = "poor"

        return {
            "overall_score": score,
            "quality_badge": badge,
            "total_findings": len(findings),
            "findings_by_severity": by_severity,
            "analyzed_entities": {
                "specifications": len(specs),
                "designs": len(designs),
                "tasks": len(tasks),
                "codes": len(codes),
            },
        }
