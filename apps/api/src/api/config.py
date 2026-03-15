from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://thirdy:thirdy@localhost:5432/thirdy"

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
    chat_history_limit: int = 50
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
        "If there are no decision points, return: {\"decision_points\": []}"
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
        "If there are no decision points, return: {\"decision_points\": []}"
    )

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
