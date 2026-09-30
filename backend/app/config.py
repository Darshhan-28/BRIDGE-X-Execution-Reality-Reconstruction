"""BRIDGE-X application configuration.

All settings load from environment / .env. The app must start with
NO api key configured (offline-first, CPU-only prototype).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "BRIDGE-X"
    APP_VERSION: str = "0.16.0-p16"
    DATABASE_URL: str = "sqlite:///./bridge_x.db"

    # Optional LLM gateway (OpenRouter). Empty = fallback parser only.
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "meta-llama/llama-3.1-8b-instruct:free"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_TIMEOUT_S: float = 15.0

    # Matching weights (P5, configurable). Must sum ~1.0.
    W_SEMANTIC: float = 0.25
    W_LEXICAL: float = 0.20
    W_DISCIPLINE: float = 0.15
    W_LOCATION: float = 0.12
    W_OBJECT: float = 0.10
    W_SIZE_TAG: float = 0.08
    W_WBS: float = 0.05
    W_STATE: float = 0.05

    # Confidence gate thresholds (P7).
    HIGH_THRESHOLD: float = 85.0
    MEDIUM_THRESHOLD: float = 60.0
    MIN_MARGIN: float = 15.0

    @property
    def llm_configured(self) -> bool:
        return bool(self.OPENROUTER_API_KEY.strip())


settings = Settings()
