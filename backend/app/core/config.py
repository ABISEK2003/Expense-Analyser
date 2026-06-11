from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Expense Intelligence"
    DEBUG: bool = False

    # Groq (cloud) — set this for production deployment
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    # Ollama (local) — used when GROQ_API_KEY is not set
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"
    OLLAMA_PRIMARY_MODEL: str = "qwen3:8b"
    OLLAMA_FALLBACK_MODEL: str = "qwen3:4b"
    OLLAMA_TIMEOUT: int = 120
    OLLAMA_MAX_RETRIES: int = 3

    MAX_UPLOAD_SIZE_MB: int = 50

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
