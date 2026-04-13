"""
Phase 3 — Filter restaurants BEFORE any LLM call.

``filter_restaurants`` applies city, cuisine, rating, and budget filters, sorts by
rating (highest first), and returns at most ``MAX_LLM_CANDIDATES`` rows.

Also includes ``filter_with_relaxation`` for smart fallback when no matches found.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from phase_2.models import UserPreferences

# Architecture cap: never pass more than this many rows to the LLM (Phase 4).
MAX_LLM_CANDIDATES = 30


@dataclass
class FilterResult:
    """Result from filter operation including relaxation info."""

    candidates: pd.DataFrame
    was_relaxed: bool = False
    relaxation_message: str = ""
    original_filters: dict | None = None
    relaxed_filters: dict | None = None

# Canonical columns produced by ``phase_1.data_loader.load_and_process_data``.
REQUIRED_COLUMNS = frozenset(
    {"id", "name", "city", "cuisines", "rating", "cost_for_two", "budget_tier"}
)


def _apply_filters(
    df: pd.DataFrame,
    prefs: UserPreferences,
) -> pd.DataFrame:
    """Apply all filters without relaxation - internal helper."""
    # 1) City — exact match on normalized locality/city string from Phase 1.
    mask = df["city"] == prefs.location

    # 2) Cuisines — intersection: at least one requested cuisine on the row.
    if prefs.cuisines:
        wanted = set(prefs.cuisines)

        def _hits(cell: object) -> bool:
            if cell is None or (isinstance(cell, float) and pd.isna(cell)):
                return False
            if isinstance(cell, list):
                return bool(wanted.intersection(cell))
            # Defensive: treat non-list as empty
            return False

        mask &= df["cuisines"].apply(_hits)

    # 3) Rating — unknown ratings cannot satisfy a minimum threshold.
    mask &= df["rating"].notna() & (df["rating"] >= prefs.min_rating)

    # 4) Budget — max approximate cost for two (INR); unknown cost excluded.
    mask &= df["cost_for_two"].notna() & (df["cost_for_two"] <= prefs.budget)

    return df.loc[mask].copy()


def filter_restaurants(
    df: pd.DataFrame,
    prefs: UserPreferences,
    *,
    max_candidates: int = MAX_LLM_CANDIDATES,
) -> pd.DataFrame:
    """
    Filter ``df`` using ``prefs``; sort by ``rating`` descending; cap at ``max_candidates``.

    Steps (all AND):

    1. ``city`` equals ``prefs.location`` (both normalized lowercase from earlier phases).
    2. If ``prefs.cuisines`` is set, keep rows whose ``cuisines`` list intersects it.
    3. ``rating`` is not null and ``rating >= prefs.min_rating``.
    4. ``cost_for_two`` is not null and ``<= prefs.budget`` (max INR for two).

    Returns
    -------
    pandas.DataFrame
        Subset of ``df`` with same columns, or **0 rows** if nothing matches (never None).
    """
    if max_candidates < 1:
        raise ValueError("max_candidates must be at least 1")

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"DataFrame missing required columns {sorted(missing)}. "
            f"Expected {sorted(REQUIRED_COLUMNS)}."
        )

    # 1) City — exact match on normalized locality/city string from Phase 1.
    mask = df["city"] == prefs.location

    # 2) Cuisines — intersection: at least one requested cuisine on the row.
    if prefs.cuisines:
        wanted = set(prefs.cuisines)

        def _hits(cell: object) -> bool:
            if cell is None or (isinstance(cell, float) and pd.isna(cell)):
                return False
            if isinstance(cell, list):
                return bool(wanted.intersection(cell))
            # Defensive: treat non-list as empty
            return False

        mask &= df["cuisines"].apply(_hits)

    # 3) Rating — unknown ratings cannot satisfy a minimum threshold.
    mask &= df["rating"].notna() & (df["rating"] >= prefs.min_rating)

    # 4) Budget — max approximate cost for two (INR); unknown cost excluded.
    mask &= df["cost_for_two"].notna() & (df["cost_for_two"] <= prefs.budget)

    out = _apply_filters(df, prefs)
    if out.empty:
        return df.iloc[:0].copy()

    out = out.sort_values("rating", ascending=False, na_position="last")
    out = out.head(max_candidates).reset_index(drop=True)
    return out


def filter_with_relaxation(
    df: pd.DataFrame,
    prefs: UserPreferences,
    *,
    max_candidates: int = MAX_LLM_CANDIDATES,
) -> FilterResult:
    """
    Filter with smart relaxation when no exact matches found.
    
    Tries relaxing filters in order: rating → budget → cuisines
    Returns FilterResult with relaxation info for UI display.
    """
    # First try exact filters
    candidates = _apply_filters(df, prefs)
    
    if not candidates.empty:
        candidates = candidates.sort_values("rating", ascending=False, na_position="last")
        candidates = candidates.head(max_candidates).reset_index(drop=True)
        return FilterResult(candidates=candidates, was_relaxed=False)
    
    # No matches - try relaxing filters one by one
    original_filters = {
        "location": prefs.location,
        "budget": prefs.budget,
        "min_rating": prefs.min_rating,
        "cuisines": prefs.cuisines,
    }
    
    # Try 1: Relax rating by 0.5
    if prefs.min_rating > 3.0:
        relaxed_rating = max(3.0, prefs.min_rating - 0.5)
        relaxed_prefs = UserPreferences(
            location=prefs.location,
            budget=prefs.budget,
            min_rating=relaxed_rating,
            cuisines=prefs.cuisines,
            top_k=prefs.top_k,
        )
        candidates = _apply_filters(df, relaxed_prefs)
        if not candidates.empty:
            candidates = candidates.sort_values("rating", ascending=False, na_position="last")
            candidates = candidates.head(max_candidates).reset_index(drop=True)
            return FilterResult(
                candidates=candidates,
                was_relaxed=True,
                relaxation_message=f"No exact matches found. Showing results with relaxed rating ({relaxed_rating}+).",
                original_filters=original_filters,
                relaxed_filters={**original_filters, "min_rating": relaxed_rating},
            )
    
    # Try 2: Relax budget by 50%
    relaxed_budget = prefs.budget * 1.5
    relaxed_prefs = UserPreferences(
        location=prefs.location,
        budget=relaxed_budget,
        min_rating=prefs.min_rating,
        cuisines=prefs.cuisines,
        top_k=prefs.top_k,
    )
    candidates = _apply_filters(df, relaxed_prefs)
    if not candidates.empty:
        candidates = candidates.sort_values("rating", ascending=False, na_position="last")
        candidates = candidates.head(max_candidates).reset_index(drop=True)
        return FilterResult(
            candidates=candidates,
            was_relaxed=True,
            relaxation_message=f"No matches in your budget. Showing options up to ₹{relaxed_budget:.0f}.",
            original_filters=original_filters,
            relaxed_filters={**original_filters, "budget": relaxed_budget},
        )
    
    # Try 3: Remove cuisine filter
    if prefs.cuisines:
        relaxed_prefs = UserPreferences(
            location=prefs.location,
            budget=relaxed_budget,
            min_rating=relaxed_rating if prefs.min_rating > 3.0 else prefs.min_rating,
            cuisines=None,
            top_k=prefs.top_k,
        )
        candidates = _apply_filters(df, relaxed_prefs)
        if not candidates.empty:
            candidates = candidates.sort_values("rating", ascending=False, na_position="last")
            candidates = candidates.head(max_candidates).reset_index(drop=True)
            return FilterResult(
                candidates=candidates,
                was_relaxed=True,
                relaxation_message="No matches with your cuisine preferences. Showing all cuisines.",
                original_filters=original_filters,
                relaxed_filters={**original_filters, "cuisines": None},
            )
    
    # Nothing worked - return empty
    return FilterResult(
        candidates=df.iloc[:0].copy(),
        was_relaxed=False,
        relaxation_message="No restaurants found in this area.",
    )
