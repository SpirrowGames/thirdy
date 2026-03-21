from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://thirdy:thirdy@localhost:5432/thirdy"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""

    # Frontend
    frontend_url: str = "http://localhost:3000"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Lexora (LLM Proxy)
    lexora_base_url: str = "http://sg-ai-server-01:8110"
    lexora_default_model: str = "gpt-4o"
    lexora_json_model: str = ""  # Model for structured JSON output (falls back to default)
    chat_history_limit: int = 50
    output_language: str = ""
    chat_system_prompt: str = "You are a helpful AI assistant."

    # Specification extraction
    spec_extraction_system_prompt: str = (
        "You are a specification writer. Analyze the conversation and generate a comprehensive "
        "specification document in Markdown format. Include the following sections as appropriate:\n\n"
        "# Title\n\n"
        "## Overview\nBrief summary of what is being specified.\n\n"
        "## Requirements\nFunctional and non-functional requirements.\n\n"
        "## Technical Details\nArchitecture, data models, APIs, etc.\n\n"
        "## Constraints\nLimitations, dependencies, performance requirements.\n\n"
        "## Open Questions\nUnresolved items that need further discussion.\n\n"
        "Output ONLY the Markdown document, no preamble or explanation."
    )

    # Decision detection
    decision_detection_system_prompt: str = (
        "You are a decision analysis assistant. Analyze the conversation and identify "
        "ambiguities, decision points, or questions that need to be resolved.\n\n"
        "For each decision point found, provide:\n"
        "- question: The ambiguity or decision that needs to be made\n"
        "- context: Relevant excerpt from the conversation\n"
        "- recommendation: Your recommended course of action (or null)\n"
        "- options: A list of possible choices, each with:\n"
        "  - label: Short name for the option\n"
        "  - description: Explanation of the option (or null)\n"
        "  - pros: List of advantages\n"
        "  - cons: List of disadvantages\n\n"
        "Respond ONLY with a JSON object in this exact format:\n"
        '{"decision_points": [\n'
        '  {"question": "...", "context": "...", "recommendation": "...", "options": [\n'
        '    {"label": "...", "description": "...", "pros": ["..."], "cons": ["..."]}\n'
        "  ]}\n"
        "]}\n\n"
        "If there are no decision points, return: {\"decision_points\": []}\n\n"
        "IMPORTANT: Output ONLY the JSON object. Do NOT include any thinking, reasoning, or explanation. /no_think"
    )

    # Design decomposition
    design_decomposition_system_prompt: str = (
        "You are a software design architect. Given a specification document, generate a detailed "
        "design document in Markdown format that decomposes the specification into implementable components.\n\n"
        "Include the following sections as appropriate:\n\n"
        "# Title\n\n"
        "## Overview\nHigh-level architecture and design approach.\n\n"
        "## Components\nBreakdown of system components, their responsibilities, and interfaces.\n\n"
        "## Data Models\nDatabase schemas, entity relationships, and data flow.\n\n"
        "## API Design\nEndpoint definitions, request/response formats.\n\n"
        "## Dependencies\nExternal services, libraries, and inter-component dependencies.\n\n"
        "## Implementation Notes\nKey implementation decisions, patterns to use, and edge cases.\n\n"
        "Output ONLY the Markdown document, no preamble or explanation."
    )

    # Design decision detection
    design_decision_detection_system_prompt: str = (
        "You are a design review assistant. Analyze the design document and identify "
        "architectural decisions, trade-offs, and design choices that need review or approval.\n\n"
        "For each decision point found, provide:\n"
        "- question: The design decision or trade-off that needs to be made\n"
        "- context: Relevant excerpt from the design document\n"
        "- recommendation: Your recommended approach (or null)\n"
        "- options: A list of possible approaches, each with:\n"
        "  - label: Short name for the option\n"
        "  - description: Explanation of the approach (or null)\n"
        "  - pros: List of advantages\n"
        "  - cons: List of disadvantages\n\n"
        "Respond ONLY with a JSON object in this exact format:\n"
        '{"decision_points": [\n'
        '  {"question": "...", "context": "...", "recommendation": "...", "options": [\n'
        '    {"label": "...", "description": "...", "pros": ["..."], "cons": ["..."]}\n'
        "  ]}\n"
        "]}\n\n"
        "If there are no decision points, return: {\"decision_points\": []}\n\n"
        "IMPORTANT: Output ONLY the JSON object. Do NOT include any thinking, reasoning, or explanation. /no_think"
    )

    # Task generation
    task_generation_system_prompt: str = (
        "You are a task planning assistant. Given a design document, generate a list of "
        "implementation tasks with dependencies.\n\n"
        "For each task, provide:\n"
        "- title: A concise task title\n"
        "- description: Detailed description of what needs to be done\n"
        "- priority: One of: low, medium, high, critical\n"
        "- dependencies: List of task titles that must be completed first (use exact titles)\n\n"
        "Order tasks so that dependencies come before dependents.\n\n"
        "Respond ONLY with a JSON object in this exact format:\n"
        '{"tasks": [\n'
        '  {"title": "...", "description": "...", "priority": "medium", "dependencies": []},\n'
        '  {"title": "...", "description": "...", "priority": "high", "dependencies": ["first task title"]}\n'
        "]}\n\n"
        "If there are no tasks to generate, return: {\"tasks\": []}\n\n"
        "IMPORTANT: Output ONLY the JSON object. Do NOT include any thinking, reasoning, or explanation. /no_think"
    )

    # Code generation
    code_generation_system_prompt: str = (
        "You are a senior software engineer. Given a task description along with its parent design "
        "document and specification, generate production-ready implementation code and tests.\n\n"
        "Format your output as Markdown with fenced code blocks. Each code block should have the "
        "file path as a comment on the first line inside the block, for example:\n\n"
        "```typescript\n"
        "// src/components/MyComponent.tsx\n"
        "...\n"
        "```\n\n"
        "```python\n"
        "# app/services/my_service.py\n"
        "...\n"
        "```\n\n"
        "Requirements:\n"
        "- Write clean, production-ready code\n"
        "- Include proper error handling\n"
        "- Include unit tests in separate code blocks\n"
        "- Follow the conventions and patterns visible in the design and spec\n"
        "- Add brief explanations between code blocks when helpful\n\n"
        "Output ONLY the Markdown document with code blocks, no preamble."
    )

    # Whisper (Voice transcription)
    whisper_model_size: str = "base"

    # Voice classification
    voice_classification_system_prompt: str = (
        "You are a meeting transcript analyzer. Given a transcribed meeting text, "
        "classify and extract structured information.\n\n"
        "Respond ONLY with a JSON object:\n"
        "{\n"
        '  "summary": "Brief summary of the meeting content",\n'
        '  "requirements": ["List of requirements or feature requests mentioned"],\n'
        '  "questions": ["Open questions raised during the meeting"],\n'
        '  "decisions": ["Decisions made during the meeting"],\n'
        '  "action_items": ["Action items assigned"]\n'
        "}\n\n"
        "If a category has no items, use an empty array.\n\n"
        "IMPORTANT: Output ONLY the JSON object. Do NOT include any thinking, reasoning, or explanation. /no_think"
    )

    # Issue structuring (Non-Engineer Client)
    issue_structuring_system_prompt: str = (
        "You are an assistant that converts natural language requests from non-engineers "
        "into well-structured GitHub Issues.\n\n"
        "Given a user's request in plain language, create a structured GitHub Issue.\n\n"
        "Respond ONLY with a JSON object:\n"
        "{\n"
        '  "title": "Concise issue title (max 80 chars)",\n'
        '  "body": "Detailed issue body in Markdown format with sections:\\n'
        "## Summary\\n"
        "Brief description of the request.\\n\\n"
        "## Expected Behavior\\n"
        "What the user expects to happen.\\n\\n"
        "## Additional Context\\n"
        'Any relevant details.",\n'
        '  "labels": ["list", "of", "suggested", "labels"]\n'
        "}\n\n"
        "Guidelines:\n"
        "- Write the title clearly and concisely\n"
        "- Expand vague requests into actionable descriptions\n"
        "- Suggest appropriate labels (e.g., enhancement, bug, documentation)\n"
        "- Keep the original intent intact while making it developer-friendly\n"
        "- If the request is in Japanese, write the issue in Japanese\n\n"
        "IMPORTANT: Output ONLY the JSON object. Do NOT include any thinking, reasoning, or explanation. /no_think"
    )

    # Internal Audit
    audit_system_prompt: str = (
        "You are an internal audit assistant. Analyze all artifacts in a conversation "
        "(specifications, designs, tasks, code) and identify quality issues, "
        "inconsistencies, completeness gaps, dependency problems, and redundancies.\n\n"
        "For each finding, provide:\n"
        "- severity: One of: info, warning, error, critical\n"
        "- category: One of: consistency, completeness, quality, dependency, redundancy\n"
        "- title: A concise title for the finding\n"
        "- description: Detailed explanation of the issue\n"
        "- affected_entity_type: The type of artifact affected (specification, design, task, code) or null\n"
        "- affected_entity_id: The ID of the affected artifact or null\n"
        "- suggestion: A recommended fix or improvement, or null\n\n"
        "Respond ONLY with a JSON object in this exact format:\n"
        '{"findings": [\n'
        '  {"severity": "warning", "category": "consistency", "title": "...", '
        '"description": "...", "affected_entity_type": "specification", '
        '"affected_entity_id": "...", "suggestion": "..."}\n'
        "]}\n\n"
        "If there are no findings, return: {\"findings\": []}\n\n"
        "IMPORTANT: Output ONLY the JSON object. Do NOT include any thinking, reasoning, or explanation. /no_think"
    )

    # External Watch
    watch_system_prompt: str = (
        "You are an external watch assistant. Given a project's specifications, designs, "
        "and technology stack, identify relevant external changes that could impact the project. "
        "Consider dependency updates, API changes, security advisories, ecosystem shifts, "
        "and competitor developments.\n\n"
        "For each finding, provide:\n"
        "- source_type: One of: dependency, api_change, security, competitor, ecosystem\n"
        "- impact_level: One of: none, low, medium, high, critical\n"
        "- title: A concise title for the finding\n"
        "- description: Detailed explanation of the external change\n"
        "- source_url: URL to the source of information, or null\n"
        "- affected_area: The project area affected (backend, frontend, infrastructure, etc.), or null\n"
        "- recommendation: Recommended action to take, or null\n\n"
        "Respond ONLY with a JSON object in this exact format:\n"
        '{"findings": [\n'
        '  {"source_type": "dependency", "impact_level": "medium", "title": "...", '
        '"description": "...", "source_url": "...", "affected_area": "backend", '
        '"recommendation": "..."}\n'
        "]}\n\n"
        "If there are no findings, return: {\"findings\": []}\n\n"
        "IMPORTANT: Output ONLY the JSON object. Do NOT include any thinking, reasoning, or explanation. /no_think"
    )

    # Spec review auto-trigger: review after N incremental spec updates
    spec_review_auto_trigger_interval: int = 3

    # LLM fallback for large prompts (when JSON model limit exceeded)
    lexora_fallback_model: str = ""  # e.g., claude-sonnet-4-20250514

    # Auto pipeline
    auto_pipeline_concurrency: int = 4  # max concurrent Code+PR operations

    # GitHub
    github_token: str = ""
    github_owner: str = ""  # Legacy: used as fallback
    github_repo: str = ""   # Legacy: used as fallback
    github_org: str = ""    # Organization to list repos from
    github_base_branch: str = "main"

    model_config = {"env_file": ".env", "extra": "ignore"}

    def localized_prompt(self, prompt: str) -> str:
        """Append language instruction to a system prompt if output_language is set."""
        if self.output_language:
            return f"{prompt}\n\nIMPORTANT: Always respond in {self.output_language}."
        return prompt


settings = Settings()
