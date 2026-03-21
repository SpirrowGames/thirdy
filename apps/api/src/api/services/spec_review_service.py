"""Spec Review service — deep analysis of a specification document.

Identifies contradictions, gaps, ambiguities, and inconsistencies.
Generates concrete improvement suggestions and clarifying questions.
"""

import json
import logging

from llm_client import LexoraClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.db.models.spec_review import SpecReview
from api.db.models.specification import Specification

logger = logging.getLogger(__name__)

SPEC_REVIEW_SYSTEM_PROMPT = (
    "You are a specification review expert. Deeply analyze the given specification document "
    "and identify problems, suggest improvements, and generate clarifying questions.\n\n"
    "Analyze for:\n"
    "1. **Contradictions**: Conflicting statements within the spec (e.g., one section says sync, another says async)\n"
    "2. **Gaps**: Missing requirements, undefined error handling, missing non-functional requirements, "
    "missing edge cases, undefined API responses\n"
    "3. **Ambiguities**: Vague descriptions like 'handle appropriately', 'as needed', 'etc.', "
    "undefined terms, unclear scope boundaries\n"
    "4. **Inconsistencies**: Inconsistent terminology, naming conventions, or formatting\n\n"
    "For each issue found, provide:\n"
    "- severity: One of: critical, warning, info\n"
    "- category: One of: contradiction, gap, ambiguity, inconsistency\n"
    "- title: Concise title\n"
    "- description: Detailed explanation\n"
    "- location: Which section or part of the spec is affected (or null)\n\n"
    "For each improvement suggestion, provide:\n"
    "- severity: One of: critical, warning, info\n"
    "- title: What to improve\n"
    "- description: Why this improvement matters\n"
    "- before: The original text to replace (exact quote from the spec, or null for additions)\n"
    "- after: The proposed replacement or addition text\n"
    "- section: Which section this applies to (or null)\n"
    "- related_issue_index: Index (0-based) of the related issue, or null\n\n"
    "For clarifying questions that should be asked to stakeholders:\n"
    "- question: The question to ask\n"
    "- context: Why this question matters for the spec quality\n"
    "- priority: One of: high, medium, low\n\n"
    "Respond ONLY with a JSON object in this exact format:\n"
    "{\n"
    '  "issues": [...],\n'
    '  "suggestions": [...],\n'
    '  "questions": [...]\n'
    "}\n\n"
    "If a category has no items, use an empty array.\n\n"
    "IMPORTANT: Output ONLY the JSON object. Do NOT include any thinking, reasoning, or explanation. /no_think"
)

SPEC_REVIEW_QUICK_SYSTEM_PROMPT = (
    "You are a specification review expert. Quickly scan the given specification document "
    "and identify only the most critical problems.\n\n"
    "Focus on:\n"
    "1. **Contradictions**: Conflicting statements within the spec\n"
    "2. **Critical Gaps**: Major missing requirements\n\n"
    "For each issue found, provide:\n"
    "- severity: One of: critical, warning\n"
    "- category: One of: contradiction, gap\n"
    "- title: Concise title\n"
    "- description: Brief explanation\n"
    "- location: Which section (or null)\n\n"
    "Respond ONLY with a JSON object:\n"
    '{"issues": [...], "suggestions": [], "questions": []}\n\n'
    "IMPORTANT: Output ONLY the JSON object. /no_think"
)

# Severity penalty weights for score computation
_SEVERITY_PENALTY = {
    "critical": 15,
    "warning": 5,
    "info": 1,
}


class SpecReviewService:
    def __init__(self, session: AsyncSession, lexora: LexoraClient):
        self.session = session
        self.lexora = lexora

    async def run_review(
        self,
        specification_id,
        conversation_id,
        *,
        job_id: str | None = None,
        scope: str = "full",
    ) -> SpecReview:
        # 1. Load specification
        spec = await self._load_specification(specification_id)
        if spec is None:
            raise ValueError(f"Specification {specification_id} not found")

        # 2. Build prompt and call LLM
        messages = self._build_review_prompt(spec, scope)
        json_model = settings.lexora_json_model or None
        raw_response = await self.lexora.complete(messages, model=json_model, json_mode=True)

        # 3. Parse response
        parsed = self._parse_review_response(raw_response)
        issues = parsed.get("issues", [])
        suggestions = parsed.get("suggestions", [])
        questions = parsed.get("questions", [])

        # Add default status to suggestions
        for s in suggestions:
            if "status" not in s:
                s["status"] = "pending"

        # 4. Compute summary
        summary = self._compute_summary(issues, suggestions, questions)

        # 5. Save review
        review = SpecReview(
            specification_id=specification_id,
            conversation_id=conversation_id,
            job_id=job_id,
            status="completed",
            scope=scope,
            summary=summary,
            issues=issues,
            suggestions=suggestions,
            questions=questions,
            spec_snapshot=spec.content,
        )
        self.session.add(review)
        await self.session.commit()
        await self.session.refresh(review)
        return review

    async def _load_specification(self, specification_id):
        result = await self.session.execute(
            select(Specification).where(Specification.id == specification_id)
        )
        return result.scalar_one_or_none()

    def _build_review_prompt(self, spec: Specification, scope: str) -> list[dict]:
        system_prompt = (
            SPEC_REVIEW_QUICK_SYSTEM_PROMPT if scope == "quick"
            else SPEC_REVIEW_SYSTEM_PROMPT
        )

        user_content = (
            f"# Specification to Review\n\n"
            f"## Title: {spec.title}\n"
            f"## Status: {spec.status}\n\n"
            f"{spec.content}"
        )

        return [
            {"role": "system", "content": settings.localized_prompt(system_prompt)},
            {"role": "user", "content": user_content},
        ]

    def _parse_review_response(self, raw: str) -> dict:
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
            logger.warning("Failed to parse spec review LLM response as JSON")
            return {"issues": [], "suggestions": [], "questions": []}

    def _compute_summary(self, issues: list, suggestions: list, questions: list) -> dict:
        by_category: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for issue in issues:
            cat = issue.get("category", "ambiguity")
            sev = issue.get("severity", "info")
            by_category[cat] = by_category.get(cat, 0) + 1
            by_severity[sev] = by_severity.get(sev, 0) + 1

        # Compute score: start at 100, subtract penalties
        score = 100
        for issue in issues:
            sev = issue.get("severity", "info")
            score -= _SEVERITY_PENALTY.get(sev, 1)
        score = max(score, 0)

        if score >= 90:
            badge = "excellent"
        elif score >= 70:
            badge = "good"
        elif score >= 50:
            badge = "needs_improvement"
        else:
            badge = "poor"

        return {
            "quality_score": score,
            "quality_badge": badge,
            "total_issues": len(issues),
            "total_suggestions": len(suggestions),
            "total_questions": len(questions),
            "issues_by_category": by_category,
            "issues_by_severity": by_severity,
        }
