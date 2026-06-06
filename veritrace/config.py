"""Settings loaded from environment variables.

All configuration comes from the environment; never hardcode values here.
When MOCK_LLM=true the LLM wrapper returns deterministic stubs — no network
calls are made and no API key is required.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- API keys ---
    openai_api_key: str = "sk-MOCK"

    # --- Model tier names (configurable; verify against OpenAI dashboard) ---
    mini_model: str = "gpt-5.4-mini"
    nano_model: str = "gpt-5.4-nano"
    embed_model: str = "text-embedding-3-small"

    # --- Mock flag ---
    mock_llm: bool = True

    # --- Chroma / storage ---
    chroma_path: str = "chroma"
    sqlite_path: str = "veritrace.sqlite"

    # --- Retrieval knobs ---
    retrieval_top_k_wide: int = 20   # broad candidate set before re-rank
    retrieval_top_k_final: int = 4   # final top-k after cross-encoder

    # --- Default tenant ---
    default_tenant: str = "demo"


# Module-level singleton — import `settings` everywhere
settings = Settings()
