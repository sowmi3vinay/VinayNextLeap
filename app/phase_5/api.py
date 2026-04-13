"""
Phase 5 — HTTP API: validate → filter → Groq rank → merge for response.
Includes what-if suggestions and filter relaxation.
"""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends

from phase_2.models import UserPreferences
from phase_3.filter import filter_restaurants, filter_with_relaxation
from phase_4.llm import recommend_with_llm
from phase_5.deps import get_restaurant_df
from phase_5.merge import merge_llm_with_candidates
from phase_5.schemas import (
    FilterRelaxation,
    LocalitiesResponse,
    RecommendRequest,
    RecommendResponse,
    WhatIfSuggestion,
)

router = APIRouter(tags=["recommendations"])


def _distinct_localities(df: pd.DataFrame) -> list[str]:
    """Sorted unique non-empty ``city`` values (dataset is already normalized lowercase)."""
    col = df["city"]
    mask = col.notna()
    s = col.loc[mask].astype(str).str.strip()
    s = s[(s != "") & (s.str.lower() != "nan")]
    return sorted(s.unique().tolist())


@router.get(
    "/localities",
    response_model=LocalitiesResponse,
    summary="List localities for UI dropdowns",
)
def get_localities(df=Depends(get_restaurant_df)) -> LocalitiesResponse:
    return LocalitiesResponse(localities=_distinct_localities(df))


def _generate_what_if_suggestions(
    df: pd.DataFrame,
    prefs: UserPreferences,
    current_candidates: pd.DataFrame,
    was_relaxed: bool = False,
) -> list[WhatIfSuggestion]:
    """Generate 'what if' suggestions for better options."""
    suggestions = []
    current_count = len(current_candidates)
    
    # Suggestion 1: Higher budget for premium options (always show if it would give more)
    higher_budget = prefs.budget * 2  # Double the budget for more dramatic suggestion
    premium_prefs = UserPreferences(
        location=prefs.location,
        budget=higher_budget,
        min_rating=prefs.min_rating,
        cuisines=prefs.cuisines,
        top_k=5,
    )
    premium_candidates = filter_restaurants(df, premium_prefs)
    if len(premium_candidates) > current_count:
        premium_names = premium_candidates.head(3)["name"].tolist()
        suggestions.append(WhatIfSuggestion(
            type="budget",
            message=f"💰 If you increase budget to ₹{higher_budget:.0f}, you could explore {len(premium_candidates)} premium options like {', '.join(premium_names[:2])}",
            suggested_value=higher_budget,
            example_restaurants=premium_names,
        ))
    
    # Suggestion 2: Lower rating for more variety (show if user has strict rating)
    if prefs.min_rating >= 4.0:
        lower_rating = max(3.0, prefs.min_rating - 1.0)  # More dramatic drop
        more_options_prefs = UserPreferences(
            location=prefs.location,
            budget=prefs.budget,
            min_rating=lower_rating,
            cuisines=prefs.cuisines,
            top_k=5,
        )
        more_candidates = filter_restaurants(df, more_options_prefs)
        if len(more_candidates) > current_count:
            more_names = more_candidates.head(3)["name"].tolist()
            suggestions.append(WhatIfSuggestion(
                type="rating",
                message=f"⭐ With rating {lower_rating}+, you'd have {len(more_candidates)} more options to explore",
                suggested_value=lower_rating,
                example_restaurants=more_names,
            ))
    
    # Suggestion 3: Remove cuisine filter if user has one
    if prefs.cuisines:
        no_cuisine_prefs = UserPreferences(
            location=prefs.location,
            budget=prefs.budget,
            min_rating=prefs.min_rating,
            cuisines=None,
            top_k=5,
        )
        no_cuisine_candidates = filter_restaurants(df, no_cuisine_prefs)
        if len(no_cuisine_candidates) > current_count + 1:
            suggestions.append(WhatIfSuggestion(
                type="cuisine",
                message=f"🍽️ Remove cuisine filters to see {len(no_cuisine_candidates)} total options in this area",
                suggested_value=None,
                example_restaurants=no_cuisine_candidates.head(3)["name"].tolist(),
            ))
    
    # Suggestion 4: Different location (if few results)
    if current_count <= 2:
        # Find other locations with more options
        other_locations = df[df["city"] != prefs.location]["city"].unique()
        for other_loc in other_locations[:3]:
            other_loc_prefs = UserPreferences(
                location=other_loc,
                budget=prefs.budget,
                min_rating=prefs.min_rating,
                cuisines=prefs.cuisines,
                top_k=5,
            )
            other_candidates = filter_restaurants(df, other_loc_prefs)
            if len(other_candidates) >= 5:
                suggestions.append(WhatIfSuggestion(
                    type="location",
                    message=f"📍 Try {other_loc.title()} — {len(other_candidates)} options available there with your budget",
                    suggested_value=other_loc,
                    example_restaurants=other_candidates.head(3)["name"].tolist(),
                ))
                break
    
    return suggestions[:3]  # Limit to 3 suggestions


@router.post(
    "/recommend",
    response_model=RecommendResponse,
    summary="Personalized restaurant recommendations",
)
def post_recommend(
    body: RecommendRequest,
    df=Depends(get_restaurant_df),
) -> RecommendResponse:
    """
    Full pipeline: preferences → deterministic filter (max 30 candidates) → Groq ranking
    → merge explanations with structured fields for the UI.
    Includes what-if suggestions and filter relaxation when needed.
    """
    # Use filter with relaxation
    filter_result = filter_with_relaxation(df, body)
    candidates = filter_result.candidates
    
    # Generate what-if suggestions (based on original filters, not relaxed)
    what_if_suggestions = _generate_what_if_suggestions(df, body, candidates, filter_result.was_relaxed)
    
    # Get LLM recommendations
    llm_out = recommend_with_llm(candidates, body)
    response = merge_llm_with_candidates(candidates, llm_out)
    
    # Add what-if suggestions
    response.what_if_suggestions = what_if_suggestions
    
    # Add filter relaxation info if applicable
    if filter_result.was_relaxed:
        response.filter_relaxation = FilterRelaxation(
            was_relaxed=True,
            original_filters=filter_result.original_filters or {},
            relaxed_filters=filter_result.relaxed_filters or {},
            message=filter_result.relaxation_message,
        )
    
    return response
