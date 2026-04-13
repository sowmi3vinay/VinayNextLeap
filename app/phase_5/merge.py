"""
Merge LLM ranks/explanations with canonical restaurant rows from the candidate set.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from phase_5.schemas import RecommendationItem, RecommendResponse


def _scalar_float(value: Any) -> float | None:
    if value is None:
        return None
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass
    try:
        if value is not None and pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_maps_url(name: str, city: str | None) -> str:
    """Build Google Maps search URL from restaurant name and city."""
    query = name
    if city:
        query = f"{name} {city}"
    # URL-encode the query for safe URL usage
    encoded = query.replace(" ", "+").replace("&", "%26").replace("?", "%3F")
    return f"https://www.google.com/maps/search/?api=1&query={encoded}"


def merge_llm_with_candidates(
    candidates: pd.DataFrame,
    llm_result: dict[str, Any],
) -> RecommendResponse:
    """
    Build the HTTP response: only restaurants present in ``candidates`` survive the join.
    Order follows ``llm_result['recommendations']`` (rank order).
    """
    recs_in: list[dict[str, Any]] = llm_result.get("recommendations") or []
    if not isinstance(recs_in, list):
        recs_in = []

    rows = candidates.to_dict("records")
    lookup = {str(r["id"]): r for r in rows}

    items: list[RecommendationItem] = []
    seen_ids: set[str] = set()
    
    for part in recs_in:
        if not isinstance(part, dict):
            continue
        rid = part.get("id")
        if rid is None:
            continue
        rid_str = str(rid)
        
        # Skip duplicates
        if rid_str in seen_ids:
            continue
        seen_ids.add(rid_str)
        
        row = lookup.get(rid_str)
        if row is None:
            continue

        cuisines = row.get("cuisines") or []
        if not isinstance(cuisines, list):
            cuisines = list(cuisines) if cuisines is not None else []

        exp = part.get("explanation")
        if not isinstance(exp, str):
            exp = str(exp) if exp is not None else ""

        items.append(
            RecommendationItem(
                name=str(row.get("name") or ""),
                cuisines=cuisines,
                rating=_scalar_float(row.get("rating")),
                cost=_scalar_float(row.get("cost_for_two")),
                explanation=exp.strip() or "Matches your preferences.",
                maps_url=_build_maps_url(
                    str(row.get("name") or ""),
                    str(row.get("city") or "") if row.get("city") else None
                ),
            )
        )

    return RecommendResponse(
        recommendations=items,
        fallback=bool(llm_result.get("fallback", False)),
        candidates_considered=len(candidates),
    )
