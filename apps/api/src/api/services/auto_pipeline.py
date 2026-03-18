"""Auto pipeline: Design approved → Tasks → Code → PR for each task.

Runs as an ARQ background job. Generates tasks with dependency info,
then processes them in dependency order with configurable concurrency.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from uuid import UUID

import httpx
from llm_client import ChatMessage, ChatCompletionRequest, LexoraClient
from sqlalchemy import select

from api.config import settings
from api.db.models import Conversation
from api.db.models.design import Design
from api.db.models.generated_code import GeneratedCode
from api.db.models.generated_task import GeneratedTask
from api.db.models.pull_request import PullRequest
from api.db.models.specification import Specification
from api.services.code_parser import parse_code_blocks
from api.services.github import GitHubClient, GitHubError

logger = logging.getLogger(__name__)


async def run_auto_pipeline(
    session_factory,
    lexora: LexoraClient,
    conversation_id: UUID,
    design_id: UUID,
    on_progress=None,
) -> dict:
    async def progress(step: str, detail: str = ""):
        if on_progress:
            await on_progress(step, detail)
        logger.info("Auto pipeline [%s]: %s %s", conversation_id, step, detail)

    # Load context
    async with session_factory() as s:
        design = await s.get(Design, design_id)
        if not design or not design.content:
            return {"error": "Design not found or empty"}
        spec = await s.get(Specification, design.specification_id)
        conv = await s.get(Conversation, conversation_id)

    spec_title = spec.title if spec else "Untitled"
    spec_content = spec.content if spec else ""
    design_content = design.content
    design_title = design.title
    gh_owner, gh_repo = _resolve_github(conv)

    # === Step 1: Generate Tasks ===
    await progress("tasks", "Generating tasks...")
    tasks_data = await _generate_tasks(lexora, design_content)
    if isinstance(tasks_data, dict) and "error" in tasks_data:
        return tasks_data

    # Save tasks with dependencies
    task_records = await _save_tasks(session_factory, conversation_id, design_id, tasks_data)
    await progress("tasks_done", f"{len(task_records)} tasks generated")

    # === Step 2 & 3: Process in dependency order with concurrency ===
    concurrency = settings.auto_pipeline_concurrency
    results = {"tasks": len(task_records), "codes": 0, "prs": 0, "errors": []}
    completed: set[str] = set()
    in_flight: set[str] = set()
    semaphore = asyncio.Semaphore(concurrency)

    async def process_task(rec: dict):
        """Process a single task: Code gen → PR creation."""
        tid = str(rec["id"])
        task_title = rec["title"]
        in_flight.add(tid)

        async with semaphore:
            await progress("code", f"[{len(completed)+1}/{len(task_records)}] Code: {task_title}")

            async with session_factory() as s:
                task = await s.get(GeneratedTask, rec["id"])
                task_desc = task.description if task else ""

            code_id = await _generate_and_save_code(
                session_factory, lexora, conversation_id, rec["id"],
                task_title, task_desc, spec_content, design_content, results,
            )

            if code_id:
                results["codes"] += 1
                if settings.github_token and gh_owner and gh_repo:
                    await progress("pr", f"PR: {task_title}")
                    await _create_pr(
                        session_factory, conversation_id, code_id, task_title,
                        spec_title, design_title, gh_owner, gh_repo, results,
                    )

            completed.add(tid)
            in_flight.discard(tid)

    # Dependency-aware scheduling loop
    pending_tasks = asyncio.Queue()
    running: list[asyncio.Task] = []

    while len(completed) < len(task_records):
        # Find ready tasks (deps satisfied, not in-flight, not completed)
        newly_ready = []
        for rec in task_records:
            tid = str(rec["id"])
            if tid in completed or tid in in_flight:
                continue
            blockers = [d for d in rec["dep_ids"] if d not in completed]
            if not blockers:
                newly_ready.append(rec)

        # If nothing is ready and nothing is in-flight, force one (circular dep)
        if not newly_ready and not in_flight:
            remaining = [r for r in task_records if str(r["id"]) not in completed]
            if remaining:
                await progress("warn", f"Forcing task with unresolved deps: {remaining[0]['title']}")
                newly_ready.append(remaining[0])
            else:
                break

        # Launch ready tasks
        for rec in newly_ready:
            task = asyncio.create_task(process_task(rec))
            running.append(task)

        # Wait for at least one to finish before scheduling more
        if running:
            done, _pending = await asyncio.wait(running, return_when=asyncio.FIRST_COMPLETED)
            running = [t for t in running if not t.done()]

    # Wait for all remaining
    if running:
        await asyncio.gather(*running, return_exceptions=True)

    await progress("complete",
        f"Done: {results['tasks']} tasks, {results['codes']} codes, {results['prs']} PRs"
        + (f", {len(results['errors'])} errors" if results['errors'] else ""))
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _generate_tasks(lexora: LexoraClient, design_content: str) -> list[dict] | dict:
    from api.services.llm_model_selector import select_json_model, truncate_for_json_model

    messages = [
        ChatMessage(role="system", content=settings.localized_prompt(settings.task_generation_system_prompt)),
        ChatMessage(role="user", content=(
            f"Here is the design document:\n\n{design_content}\n\n"
            "Generate implementation tasks with dependencies."
        )),
    ]

    chosen_model, use_json_mode = await select_json_model(lexora, messages)
    if use_json_mode and chosen_model:
        max_tokens = await lexora.get_model_max_tokens(chosen_model)
        if max_tokens:
            truncated = truncate_for_json_model(design_content, max_tokens)
            if len(truncated) < len(design_content):
                messages[1] = ChatMessage(
                    role="user",
                    content=f"Here is the design document:\n\n{truncated}\n\nGenerate implementation tasks with dependencies.",
                )

    raw = await lexora.complete(messages, model=chosen_model, json_mode=use_json_mode)
    try:
        parsed = json.loads(LexoraClient._strip_think_tags(raw) if not use_json_mode else raw)
    except json.JSONDecodeError:
        try:
            parsed = json.loads(LexoraClient._strip_think_tags(raw))
        except json.JSONDecodeError:
            return {"error": "Failed to parse tasks JSON"}

    tasks = parsed.get("tasks", [])
    if not tasks:
        return {"error": "No tasks generated"}

    # Deduplicate by title
    seen: set[str] = set()
    unique = []
    for t in tasks:
        title = t.get("title", "")
        if title.lower() not in seen:
            seen.add(title.lower())
            unique.append(t)
    return unique


async def _save_tasks(session_factory, conversation_id, design_id, tasks_data) -> list[dict]:
    """Save tasks to DB with dependency resolution. Returns list of task records."""
    title_to_id: dict[str, UUID] = {}
    records: list[dict] = []

    async with session_factory() as s:
        for i, td in enumerate(tasks_data):
            task = GeneratedTask(
                conversation_id=conversation_id,
                design_id=design_id,
                title=td["title"],
                description=td.get("description", ""),
                priority=td.get("priority", "medium"),
                status="pending",
                sort_order=i,
                dependencies=json.dumps([]),
            )
            s.add(task)
            await s.flush()
            title_to_id[td["title"].lower()] = task.id
            records.append({
                "id": task.id,
                "title": td["title"],
                "dep_titles": td.get("dependencies", []),
                "dep_ids": [],
            })
        await s.commit()

    # Resolve title→UUID
    async with session_factory() as s:
        for rec in records:
            dep_ids = []
            for dt in rec["dep_titles"]:
                did = title_to_id.get(dt.lower())
                if did:
                    dep_ids.append(str(did))
            rec["dep_ids"] = dep_ids
            if dep_ids:
                task = await s.get(GeneratedTask, rec["id"])
                if task:
                    task.dependencies = json.dumps(dep_ids)
        await s.commit()

    return records


async def _generate_and_save_code(
    session_factory, lexora, conversation_id, task_id, task_title, task_desc,
    spec_content, design_content, results,
) -> UUID | None:
    messages = [
        ChatMessage(role="system", content=settings.localized_prompt(settings.code_generation_system_prompt)),
        ChatMessage(role="user", content=(
            f"## Specification\n\n{spec_content}\n\n"
            f"## Design Document\n\n{design_content}\n\n"
            f"## Task\n\n**{task_title}**\n\n{task_desc}\n\n"
            "Generate the implementation code and tests for this task."
        )),
    ]

    try:
        code_model = settings.lexora_fallback_model or None
        req = ChatCompletionRequest(
            model=code_model or lexora._default_model,
            messages=messages,
            stream=False,
        )
        resp = await lexora._http.post(
            lexora.completions_url, json=req.model_dump(exclude_none=True), timeout=600.0,
        )
        resp.raise_for_status()
        raw_code = resp.json()["choices"][0]["message"]["content"]
        code_content = re.sub(r"<think>[\s\S]*?</think>\s*", "", raw_code).strip()

        if not code_content:
            results["errors"].append(f"Empty code: {task_title}")
            return None

        async with session_factory() as s:
            code = GeneratedCode(
                conversation_id=conversation_id,
                task_id=task_id,
                content=code_content,
                status="approved",
            )
            s.add(code)
            t = await s.get(GeneratedTask, task_id)
            if t:
                t.status = "done"
            await s.commit()
            await s.refresh(code)
            return code.id

    except Exception as e:
        results["errors"].append(f"Code gen failed: {task_title}: {str(e)[:100]}")
        return None


async def _create_pr(
    session_factory, conversation_id, code_id, task_title,
    spec_title, design_title, gh_owner, gh_repo, results,
):
    async with session_factory() as s:
        code = await s.get(GeneratedCode, code_id)
        if not code:
            return

    code_files = parse_code_blocks(code.content)
    if not code_files:
        results["errors"].append(f"No files parsed: {task_title}")
        return

    branch_name = f"thirdy/{_sanitize(task_title)}-{str(code_id)[:8]}"
    pr_title = f"feat: {task_title}"
    file_paths = [f.path for f in code_files]
    pr_body = (
        f"## Traceability\n\n"
        f"- **Specification**: {spec_title}\n"
        f"- **Design**: {design_title}\n"
        f"- **Task**: {task_title}\n\n"
        f"## Files\n\n" + "\n".join(f"- `{f}`" for f in file_paths) +
        f"\n\n---\n*Auto-generated by Thirdy Auto Pipeline*"
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            gh = GitHubClient(token=settings.github_token, owner=gh_owner, repo=gh_repo, http=http)
            base_sha = await gh.get_default_branch_sha(settings.github_base_branch)
            await gh.create_branch(branch_name, base_sha)
            for cf in code_files:
                await gh.create_or_update_file(
                    branch=branch_name, path=cf.path,
                    content=cf.content, message=f"feat: add {cf.path}",
                )
            pr_response = await gh.create_pull_request(
                title=pr_title, body=pr_body,
                head=branch_name, base=settings.github_base_branch,
            )

        async with session_factory() as s:
            pr = PullRequest(
                conversation_id=conversation_id,
                code_id=code_id,
                pr_number=pr_response["number"],
                pr_url=pr_response["html_url"],
                branch_name=branch_name,
                title=pr_title,
                description=pr_body,
                status="created",
            )
            s.add(pr)
            await s.commit()

        results["prs"] += 1

    except Exception as e:
        results["errors"].append(f"PR failed: {task_title}: {str(e)[:100]}")
        async with session_factory() as s:
            pr = PullRequest(
                conversation_id=conversation_id,
                code_id=code_id,
                pr_number=None, pr_url=None,
                branch_name=branch_name,
                title=pr_title,
                description=str(e)[:500],
                status="failed",
                error_message=str(e)[:500],
            )
            s.add(pr)
            await s.commit()


def _resolve_github(conv) -> tuple[str, str]:
    if conv and conv.github_repo:
        parts = conv.github_repo.split("/", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return settings.github_org or settings.github_owner, parts[0]
    return settings.github_owner, settings.github_repo


def _sanitize(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_/-]", "-", text.lower())
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:60]
