"""Auto pipeline: Design approved → Tasks → Code → PR for each task.

Runs as an ARQ background job. Orchestrates the full pipeline by
calling LLM services directly (not via HTTP endpoints).
"""

from __future__ import annotations

import json
import logging
import re
import base64
from uuid import UUID

import httpx
from llm_client import ChatMessage, LexoraClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    """Run the full auto pipeline: Tasks → Code → PR for each task.

    Args:
        session_factory: async session factory
        lexora: LexoraClient instance
        conversation_id: conversation UUID
        design_id: approved design UUID
        on_progress: optional async callback(step, detail) for progress updates

    Returns:
        Summary dict with counts.
    """
    async def progress(step: str, detail: str = ""):
        if on_progress:
            await on_progress(step, detail)
        logger.info("Auto pipeline [%s]: %s %s", conversation_id, step, detail)

    # Load design + spec
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

    # Resolve GitHub repo
    gh_owner, gh_repo = "", ""
    if conv and conv.github_repo:
        parts = conv.github_repo.split("/", 1)
        if len(parts) == 2:
            gh_owner, gh_repo = parts
        else:
            gh_owner = settings.github_org or settings.github_owner
            gh_repo = parts[0]
    else:
        gh_owner = settings.github_owner
        gh_repo = settings.github_repo

    # === Step 1: Generate Tasks ===
    await progress("tasks", "Generating tasks from design...")

    task_messages = [
        ChatMessage(role="system", content=settings.localized_prompt(settings.task_generation_system_prompt)),
        ChatMessage(role="user", content=f"Here is the design document:\n\n{design_content}\n\nGenerate implementation tasks with dependencies."),
    ]

    from api.services.llm_model_selector import select_json_model, truncate_for_json_model
    chosen_model, use_json_mode = await select_json_model(lexora, task_messages)

    # Truncate if needed
    if use_json_mode and chosen_model:
        max_tokens = await lexora.get_model_max_tokens(chosen_model)
        if max_tokens:
            truncated = truncate_for_json_model(design_content, max_tokens)
            if len(truncated) < len(design_content):
                task_messages[1] = ChatMessage(
                    role="user",
                    content=f"Here is the design document:\n\n{truncated}\n\nGenerate implementation tasks with dependencies.",
                )

    raw_tasks = await lexora.complete(task_messages, model=chosen_model, json_mode=use_json_mode)
    try:
        parsed_tasks = json.loads(LexoraClient._strip_think_tags(raw_tasks) if not use_json_mode else raw_tasks)
    except json.JSONDecodeError:
        # Try stripping think tags
        try:
            parsed_tasks = json.loads(LexoraClient._strip_think_tags(raw_tasks))
        except json.JSONDecodeError:
            return {"error": "Failed to parse tasks JSON", "raw": raw_tasks[:500]}

    tasks_data = parsed_tasks.get("tasks", [])
    if not tasks_data:
        return {"error": "No tasks generated"}

    # Save tasks
    task_ids = []
    async with session_factory() as s:
        for i, td in enumerate(tasks_data):
            task = GeneratedTask(
                conversation_id=conversation_id,
                design_id=design_id,
                title=td.get("title", f"Task {i+1}"),
                description=td.get("description", ""),
                priority=td.get("priority", "medium"),
                status="pending",
                sort_order=i,
            )
            s.add(task)
            await s.flush()
            task_ids.append({"id": task.id, "title": task.title})
        await s.commit()

    await progress("tasks_done", f"{len(task_ids)} tasks generated")

    # === Step 2 & 3: For each task, generate code then create PR ===
    results = {"tasks": len(task_ids), "codes": 0, "prs": 0, "errors": []}

    for task_info in task_ids:
        task_id = task_info["id"]
        task_title = task_info["title"]

        # Load task description
        async with session_factory() as s:
            task = await s.get(GeneratedTask, task_id)
            task_desc = task.description if task else ""

        # --- Generate Code ---
        await progress("code", f"Generating code for: {task_title}")

        code_messages = [
            ChatMessage(role="system", content=settings.localized_prompt(settings.code_generation_system_prompt)),
            ChatMessage(role="user", content=(
                f"## Specification\n\n{spec_content}\n\n"
                f"## Design Document\n\n{design_content}\n\n"
                f"## Task\n\n**{task_title}**\n\n{task_desc}\n\n"
                "Generate the implementation code and tests for this task."
            )),
        ]

        try:
            code_content = ""
            async for token in lexora.stream(code_messages):
                code_content += token
            code_content = LexoraClient._strip_think_tags(code_content)

            if not code_content.strip():
                results["errors"].append(f"Empty code for task: {task_title}")
                continue

            # Save code
            async with session_factory() as s:
                code = GeneratedCode(
                    conversation_id=conversation_id,
                    task_id=task_id,
                    content=code_content,
                    status="approved",  # Auto-approve in auto mode
                )
                s.add(code)
                # Mark task as done
                t = await s.get(GeneratedTask, task_id)
                if t:
                    t.status = "done"
                await s.commit()
                await s.refresh(code)
                code_id = code.id

            results["codes"] += 1
            await progress("code_done", f"Code generated for: {task_title}")

        except Exception as e:
            results["errors"].append(f"Code gen failed for {task_title}: {str(e)[:100]}")
            continue

        # --- Create PR ---
        if not settings.github_token or not gh_owner or not gh_repo:
            results["errors"].append(f"GitHub not configured, skipping PR for {task_title}")
            continue

        await progress("pr", f"Creating PR for: {task_title}")

        try:
            code_files = parse_code_blocks(code_content)
            if not code_files:
                results["errors"].append(f"No code files parsed for {task_title}")
                continue

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

            async with httpx.AsyncClient(timeout=30.0) as http:
                gh = GitHubClient(token=settings.github_token, owner=gh_owner, repo=gh_repo, http=http)
                base_sha = await gh.get_default_branch_sha(settings.github_base_branch)
                await gh.create_branch(branch_name, base_sha)
                for cf in code_files:
                    await gh.create_or_update_file(branch=branch_name, path=cf.path, content=cf.content, message=f"feat: add {cf.path}")
                pr_response = await gh.create_pull_request(title=pr_title, body=pr_body, head=branch_name, base=settings.github_base_branch)

            pr_number = pr_response["number"]
            pr_url = pr_response["html_url"]

            async with session_factory() as s:
                pr = PullRequest(
                    conversation_id=conversation_id,
                    code_id=code_id,
                    pr_number=pr_number,
                    pr_url=pr_url,
                    branch_name=branch_name,
                    title=pr_title,
                    description=pr_body,
                    status="created",
                )
                s.add(pr)
                await s.commit()

            results["prs"] += 1
            await progress("pr_done", f"PR #{pr_number} created for: {task_title}")

        except (GitHubError, Exception) as e:
            results["errors"].append(f"PR failed for {task_title}: {str(e)[:100]}")
            # Save failed PR record
            async with session_factory() as s:
                pr = PullRequest(
                    conversation_id=conversation_id,
                    code_id=code_id,
                    pr_number=None,
                    pr_url=None,
                    branch_name=branch_name if "branch_name" in dir() else "unknown",
                    title=f"feat: {task_title}",
                    description=str(e),
                    status="failed",
                    error_message=str(e)[:500],
                )
                s.add(pr)
                await s.commit()

    await progress("complete", f"Done: {results['tasks']} tasks, {results['codes']} codes, {results['prs']} PRs")
    return results


def _sanitize(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_/-]", "-", text.lower())
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:60]
