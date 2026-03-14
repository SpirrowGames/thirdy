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

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
