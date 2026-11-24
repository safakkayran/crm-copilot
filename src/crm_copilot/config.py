"""Configuration settings for crm-copilot."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LiteLLM
    LLM_BASE_URL: str = "http://127.0.0.1:4000"
    LLM_API_KEY: str = "not-needed"
    LLM_MODEL: str = "nim-laguna"

    # Twenty CRM
    TWENTY_BASE_URL: str = "http://localhost:3000"
    TWENTY_API_KEY: str = ""
    TWENTY_REST_PREFIX: str = "/rest"

    # Behavior
    AUTO_APPLY: bool = False
    CACHE_DIR: str = ".cache"


settings = Settings()