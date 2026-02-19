"""lt_common - Shared configuration."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./ace_platform.db"
    chroma_persist_dir: str = "./chroma_db"
    rag_top_k: int = 5
    case_decision_days_limit: int = 90
    p0_courts: list[str] = ["US Supreme Court", "Federal Circuit", "State Supreme Court", "US Court of Appeals"]
    p0_shepard_letters: list[str] = ["O", "W", "X", "A"]
    openai_api_key: str = ""
    task_center_url: str = "http://localhost:8002"
    schedule_svc_url: str = "http://localhost:8000"
    data_injection_url: str = "http://localhost:8001"
    ai_service_url: str = "http://localhost:8100"
    enable_case_sqs_listener: bool = True
    sqs_books_queue_url: str = ""
    sqs_case_source_url: str = ""
    casci_poll_url: str = "http://localhost:8200/mock/casci"
    datalake_base_url: str = "http://localhost:8200/mock/datalake"
    shepard_base_url: str = "http://localhost:8200/mock/shepard"
    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
