"""Application configuration management using Pydantic Settings.

Loads and validates all environment variables for the application.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration object for the entire application.

    All values are loaded from environment variables or the .env file.
    Sensitive defaults are deliberately absent so deployment fails fast
    when a required secret is missing.

    Attributes:
        groq_api_key: API key for the Groq inference provider.
        hf_api_key: Hugging Face Inference API key (fallback LLM).
        twitter_bearer_token: Twitter/X API v2 bearer token.
        twitter_api_key: Twitter/X OAuth1 consumer key.
        twitter_api_secret: Twitter/X OAuth1 consumer secret.
        twitter_access_token: Twitter/X OAuth1 access token.
        twitter_access_secret: Twitter/X OAuth1 access secret.
        linkedin_client_id: LinkedIn OAuth2 client ID.
        linkedin_client_secret: LinkedIn OAuth2 client secret.
        linkedin_access_token: LinkedIn OAuth2 access token.
        proxycurl_api_key: Proxycurl API key for LinkedIn scraping.
        database_url: SQLAlchemy-compatible database connection string.
        vector_store_path: File-system path for persisting FAISS index.
        app_env: Runtime environment label.
        log_level: Logging verbosity level.
        secret_key: Secret used for internal signing / session tokens.
        use_mock_data: When True, agents use curated sample data instead of live APIs.
        enable_publishing: Gate for live social-media publish actions.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ──────────────────────────────────────────────────────────────────
    groq_api_key: str = Field(default="", description="Groq API key")
    hf_api_key: str = Field(default="", description="Hugging Face API key")
    llm_model: str = Field(
        default="llama-3.1-8b-instant",
        description="Default Groq model identifier",
    )
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=512, ge=128)

    # ── Twitter / X ───────────────────────────────────────────────────────────
    twitter_bearer_token: str = Field(default="")
    twitter_api_key: str = Field(default="")
    twitter_api_secret: str = Field(default="")
    twitter_access_token: str = Field(default="")
    twitter_access_secret: str = Field(default="")

    # ── LinkedIn ──────────────────────────────────────────────────────────────
    linkedin_client_id: str = Field(default="")
    linkedin_client_secret: str = Field(default="")
    linkedin_access_token: str = Field(default="")
    proxycurl_api_key: str = Field(default="")

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(default="sqlite:///./social_agent.db")

    # ── Vector Store ──────────────────────────────────────────────────────────
    vector_store_path: str = Field(default="./data/vector_store")
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="HuggingFace embedding model for RAG",
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    secret_key: str = Field(default="change_me")

    # ── Feature Flags ─────────────────────────────────────────────────────────
    use_mock_data: bool = Field(default=True)
    enable_publishing: bool = Field(default=False)

    @field_validator("llm_temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Ensure temperature is within model-acceptable bounds."""
        if not 0.0 <= v <= 2.0:
            raise ValueError("llm_temperature must be between 0.0 and 2.0")
        return v

    @property
    def is_production(self) -> bool:
        """Return True when running in the production environment."""
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton.

    Returns:
        The fully validated Settings instance.
    """
    return Settings()
