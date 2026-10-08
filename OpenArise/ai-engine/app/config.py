from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings for AI Engine; environment/.env override defaults."""

    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"
    OLLAMA_TIMEOUT_SECONDS: int = Field(default=180, ge=30, le=900)
    LUMINOUS_MODEL: str = "Luminous 1.1"
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

class DesktopSettings(Settings):
    """Desktop defaults use the installed validation model, with the same overrides."""

    OLLAMA_HOST: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen2.5-coder:7b"

settings = Settings()
