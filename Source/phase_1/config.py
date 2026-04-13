"""
Application configuration for data loading and downstream phases.

Budget tiers map ``cost_for_two`` (approximate INR for two people) to low / medium / high.
Thresholds are inclusive on the upper bound for low and medium.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Workspace root (parent of ``Source/``): phase_1 → Source → repo root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Load from environment variables and optional ``.env`` at repo root."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Hugging Face dataset (public; HF_TOKEN optional for higher rate limits)
    hf_dataset_name: str = Field(
        default="ManikaSaini/zomato-restaurant-recommendation",
        description="Hugging Face dataset id for Zomato restaurants.",
    )
    hf_dataset_split: str = Field(default="train", description="Dataset split to load.")

    # INR thresholds for budget_tier (cost_for_two)
    budget_low_max_inr: int = Field(
        default=500,
        ge=0,
        description="cost_for_two <= this → low",
    )
    budget_medium_max_inr: int = Field(
        default=1200,
        ge=0,
        description="cost_for_two <= this (and > low max) → medium; above → high",
    )

    # Optional local cache under project ``data/`` (for future Parquet export)
    data_dir: Path = Field(default=PROJECT_ROOT / "data")

    def validate_budget_thresholds(self) -> None:
        """Ensure medium band is strictly above low band."""
        if self.budget_medium_max_inr <= self.budget_low_max_inr:
            raise ValueError(
                "budget_medium_max_inr must be greater than budget_low_max_inr"
            )


def get_settings() -> Settings:
    """Fresh settings instance (suitable for tests overriding env)."""
    s = Settings()
    s.validate_budget_thresholds()
    return s
