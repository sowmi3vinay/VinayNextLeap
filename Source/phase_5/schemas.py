"""
API request/response models for Phase 5 (aligned with Phase 2 preferences and problem statement).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from phase_2.models import UserPreferences


class RecommendRequest(UserPreferences):
    """JSON body for ``POST /recommend`` — same rules as :class:`UserPreferences`."""

    model_config = ConfigDict(json_schema_extra={"title": "RecommendRequest"})


class RecommendationItem(BaseModel):
    """One displayed recommendation (merged LLM + dataset row)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    cuisines: list[str]
    rating: float | None
    cost: float | None = Field(
        None,
        description="Approximate cost for two (same unit as dataset, typically INR).",
    )
    explanation: str
    maps_url: str | None = Field(
        None,
        description="Google Maps search URL for the restaurant.",
    )


class LocalitiesResponse(BaseModel):
    """Distinct locality names from the loaded dataset (``city`` column, sorted)."""

    model_config = ConfigDict(extra="forbid")

    localities: list[str] = Field(
        ...,
        description="Lowercase locality strings matching filter ``location`` values.",
    )


class WhatIfSuggestion(BaseModel):
    """A 'what if' scenario showing what users could get with different preferences."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(..., description="Type of change: 'budget', 'rating', 'cuisine'")
    message: str = Field(..., description="Human-readable suggestion message")
    suggested_value: float | str | None = Field(None, description="The suggested alternative value")
    example_restaurants: list[str] = Field(default=[], description="Example restaurant names if user accepts suggestion")


class FilterRelaxation(BaseModel):
    """Information about relaxed filters when no exact matches found."""

    model_config = ConfigDict(extra="forbid")

    was_relaxed: bool = Field(False, description="Whether filters were relaxed to find results")
    original_filters: dict[str, Any] = Field(default={}, description="Original filter values")
    relaxed_filters: dict[str, Any] = Field(default={}, description="Relaxed filter values that yielded results")
    message: str = Field("", description="User-friendly message explaining the relaxation")


class RecommendResponse(BaseModel):
    """API envelope after filter + LLM + merge."""

    model_config = ConfigDict(extra="forbid")

    recommendations: list[RecommendationItem]
    fallback: bool = Field(
        ...,
        description="True when Groq output was not used and defaults were applied.",
    )
    candidates_considered: int = Field(
        0,
        ge=0,
        description="Rows passed into the LLM (after filtering, before top_k merge).",
    )
    what_if_suggestions: list[WhatIfSuggestion] = Field(
        default=[],
        description="Alternative suggestions if user wants different options",
    )
    filter_relaxation: FilterRelaxation = Field(
        default_factory=FilterRelaxation,
        description="Information about relaxed filters if applicable",
    )
