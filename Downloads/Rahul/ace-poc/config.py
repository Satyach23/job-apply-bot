"""ACE POC Configuration."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Database
    database_url: str = "sqlite+aiosqlite:///./ace_poc.db"

    # RAG
    chroma_persist_dir: str = "./chroma_db"
    rag_top_k: int = 5

    # P0 Filter
    case_decision_days_limit: int = 90
    p0_courts: list[str] = [
        "US Supreme Court",
        "Federal Circuit",
        "State Supreme Court",
        "US Court of Appeals",
    ]
    p0_shepard_letters: list[str] = ["O", "W", "X", "A"]  # Overruled, Withdrawn, etc.

    # Optional OpenAI for impact reasoning (leave empty to use mock)
    openai_api_key: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
