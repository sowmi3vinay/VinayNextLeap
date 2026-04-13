"""
Groq (Phase 4) settings — loaded from environment / repo-root ``.env``.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from phase_1.config import PROJECT_ROOT


class GroqSettings(BaseSettings):
    """API key and model id for ``recommend_with_llm``."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: str | None = Field(
        default=None,
        description="Groq API key; if missing, Phase 4 uses fallback rankings only.",
    )
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq chat model id (see Groq console / docs).",
    )

    @field_validator("groq_api_key", mode="before")
    @classmethod
    def strip_blank_key(cls, value: object) -> str | None:
        if value is None:
            return None
        s = str(value).strip()
        return s if s else None


def get_groq_settings() -> GroqSettings:
    return GroqSettings()
