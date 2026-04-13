"""
Phase 2 — User preference schema for restaurant recommendations.

Validates API / CLI input and normalizes text for consistent filtering (Phase 3).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserPreferences(BaseModel):
    """
    Structured preferences from the user.

    * ``location`` and ``cuisines`` entries are lowercased and stripped.
    * Empty ``cuisines`` after normalization becomes ``None`` (treat as any cuisine).
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    location: str = Field(..., min_length=1, description="City or area, e.g. delhi, banashankari")
    budget: float = Field(
        ...,
        gt=0,
        le=200_000,
        description="Maximum acceptable approximate cost for two people (INR).",
    )
    cuisines: list[str] | None = Field(
        default=None,
        description="Optional; if set, filter uses intersection with restaurant cuisines.",
    )
    min_rating: float = Field(
        default=0.0,
        ge=0.0,
        le=5.0,
        description="Only restaurants with rating >= this value (unknown ratings excluded).",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
        description="How many recommendations to return after ranking.",
    )

    @field_validator("location", mode="before")
    @classmethod
    def normalize_location(cls, value: Any) -> str:
        if value is None:
            raise ValueError("location is required")
        text = str(value).strip().lower()
        if not text:
            raise ValueError("location cannot be empty")
        return text

    @field_validator("budget", mode="before")
    @classmethod
    def coerce_budget(cls, value: Any) -> float:
        """Accept int/float or numeric string from JSON/forms."""
        if value is None:
            raise ValueError("budget is required")
        if isinstance(value, bool):
            raise TypeError("budget must be a number")
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()
        if not s:
            raise ValueError("budget is required")
        try:
            return float(s)
        except ValueError as e:
            raise ValueError("budget must be a positive number (INR)") from e

    @field_validator("cuisines", mode="before")
    @classmethod
    def normalize_cuisines(cls, value: Any) -> list[str] | None:
        if value is None:
            return None
        if not isinstance(value, list):
            raise TypeError("cuisines must be a list of strings or null")
        out = [str(item).strip().lower() for item in value if str(item).strip()]
        return out if out else None
