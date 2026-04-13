"""
Phase 4 — Rank and explain filtered restaurants using Groq (no calls before filtering).

``recommend_with_llm`` returns strict-shaped recommendations; on parse/API failure it
falls back to top rows by rating (up to ``prefs.top_k``).
"""

from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd
from groq import Groq

from phase_2.models import UserPreferences
from phase_4.config import GroqSettings, get_groq_settings

DEFAULT_FALLBACK_EXPLANATION = (
    "Selected based on highest rating matching your filters (AI ranking unavailable)."
)

_SYSTEM_PROMPT = """You are a restaurant recommendation assistant for a food app.
You MUST only rank and describe restaurants from the JSON list the user provides.
Do NOT invent restaurants, ratings, prices, or addresses.

CRITICAL: Each explanation MUST be data-grounded and specific. Follow this EXACT format:

"Rated [X.X] with [Cuisine1] and [Cuisine2] cuisine, [RestaurantName] fits your preference for [specific aspect] and stays within your ₹[budget] budget."

OR

"At ₹[cost] for two, [RestaurantName] offers [cuisine types] with a solid [X.X] rating — [specific reason it matches preferences]."

Rules:
1. ALWAYS include specific numbers: rating (X.X), cost (₹X), budget (₹X)
2. ALWAYS mention actual cuisine names from the data
3. ALWAYS reference the restaurant name
4. ALWAYS mention how it fits user's budget constraint
5. Compare to user preferences explicitly
6. Use conversational but data-rich language
7. Each explanation must be UNIQUE - no two should follow the same pattern

Examples of PERFECT explanations:
- "Rated 4.7 with North Indian and Thai cuisine, Hammered fits your preference for diverse options and stays within your ₹2400 budget."
- "At ₹800 for two, Spice Route offers South Indian and Chinese with a solid 4.3 rating — perfect for your ₹1200 budget with room to spare."
- "With 4.8 stars and pure Italian cuisine, La Pino'z Pizza matches your ₹2000 budget exactly and exceeds your 4+ rating preference."
- "Priced at ₹600 (well under your ₹1500 limit), The Biryani House serves authentic Hyderabadi with a respectable 4.1 rating."

BAD examples (too vague):
- "A multicultural culinary gem..." ❌
- "Highly rated restaurant..." ❌
- "Matches your preferences..." ❌

Reply with a single JSON object only (no markdown fences, no commentary) using this shape:
{"recommendations":[{"id":"<id from list>","rank":1,"explanation":"<data-grounded reason with specific numbers>"}]}
Ranks must start at 1 and increase by 1 with no gaps. Use only ids that appear in the list."""


def _rows_from_candidates(candidates: pd.DataFrame | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(candidates, pd.DataFrame):
        raw = candidates.to_dict("records")
    else:
        raw = list(candidates)
    out: list[dict[str, Any]] = []
    for r in raw:
        cuisines = r.get("cuisines")
        if cuisines is not None and not isinstance(cuisines, list):
            cuisines = list(cuisines) if cuisines is not None else []
        out.append(
            {
                "id": str(r["id"]),
                "name": r.get("name"),
                "city": r.get("city"),
                "cuisines": cuisines or [],
                "rating": r.get("rating"),
                "cost_for_two": r.get("cost_for_two"),
                "budget_tier": r.get("budget_tier"),
            }
        )
    return out


def _rating_sort_key(row: dict[str, Any]) -> float:
    r = row.get("rating")
    if r is None or (isinstance(r, float) and pd.isna(r)):
        return -1.0
    try:
        return float(r)
    except (TypeError, ValueError):
        return -1.0


def _fallback_from_rows(rows: list[dict[str, Any]], prefs: UserPreferences) -> list[dict[str, Any]]:
    """Top ``prefs.top_k`` by ``rating`` (desc); missing/invalid ratings sort last."""
    sorted_rows = sorted(rows, key=_rating_sort_key, reverse=True)
    recs: list[dict[str, Any]] = []
    for i, r in enumerate(sorted_rows[: prefs.top_k], start=1):
        recs.append(
            {
                "id": r["id"],
                "rank": i,
                "explanation": DEFAULT_FALLBACK_EXPLANATION,
            }
        )
    return recs


def _parse_json_object(content: str) -> dict[str, Any] | None:
    """Parse model output; tolerate optional ```json fences and trailing text."""
    raw = content.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```\s*$", "", raw)
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(raw[start : end + 1])
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _normalize_llm_recommendations(
    data: dict[str, Any],
    valid_ids: set[str],
    top_k: int,
) -> list[dict[str, Any]] | None:
    recs = data.get("recommendations")
    if not isinstance(recs, list) or not recs:
        return None

    parsed: list[dict[str, Any]] = []
    for item in recs:
        if not isinstance(item, dict):
            continue
        rid = item.get("id")
        if rid is None:
            continue
        rid_s = str(rid)
        if rid_s not in valid_ids:
            continue
        try:
            rank = int(item["rank"])
        except (KeyError, TypeError, ValueError):
            continue
        exp = item.get("explanation")
        if not isinstance(exp, str):
            exp = str(exp) if exp is not None else ""
        exp = exp.strip() or "Matches your stated preferences."

        parsed.append({"id": rid_s, "rank": rank, "explanation": exp})

    if not parsed:
        return None

    # Keep best rank per id
    best: dict[str, dict[str, Any]] = {}
    for p in parsed:
        cur = best.get(p["id"])
        if cur is None or p["rank"] < cur["rank"]:
            best[p["id"]] = p

    ordered = sorted(best.values(), key=lambda x: (x["rank"], x["id"]))
    limited = ordered[:top_k]
    # Renumber ranks 1..n for a clean API surface
    return [
        {"id": x["id"], "rank": i, "explanation": x["explanation"]}
        for i, x in enumerate(limited, start=1)
    ]


def _user_prompt(prefs: UserPreferences, payload: list[dict[str, Any]]) -> str:
    cuisine_note = prefs.cuisines if prefs.cuisines else "any"
    
    # Calculate stats for context
    ratings = [r.get("rating") for r in payload if r.get("rating")]
    costs = [r.get("cost_for_two") for r in payload if r.get("cost_for_two")]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0
    avg_cost = sum(costs) / len(costs) if costs else 0
    max_rating = max(ratings) if ratings else 0
    min_cost = min(costs) if costs else 0
    
    return (
        f"User preferences:\n"
        f"- location (match area/city): {prefs.location}\n"
        f"- maximum cost for two (INR): {prefs.budget}\n"
        f"- minimum rating: {prefs.min_rating}\n"
        f"- cuisines wanted: {cuisine_note}\n"
        f"- return at most {prefs.top_k} recommendations, ranked best first (rank 1 = best).\n\n"
        f"Context for comparisons:\n"
        f"- Average rating in this list: {avg_rating:.1f}\n"
        f"- Average cost: ₹{avg_cost:.0f}\n"
        f"- Highest rating: {max_rating:.1f}\n"
        f"- Lowest cost: ₹{min_cost:.0f}\n\n"
        f"Restaurants (JSON array of objects):\n{json.dumps(payload, ensure_ascii=False)}\n\n"
        f"Remember: Each explanation must be UNIQUE. Compare restaurants to each other. "
        f"Highlight what makes each one special!"
    )


def _call_groq(
    client: Groq,
    model: str,
    user_content: str,
) -> str:
    completion = client.chat.completions.create(
        model=model,
        temperature=0.2,
        max_tokens=2048,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    choice = completion.choices[0].message
    text = choice.content
    if not text:
        raise ValueError("Empty completion content from Groq")
    return text


def recommend_with_llm(
    candidates: pd.DataFrame | list[dict[str, Any]],
    prefs: UserPreferences,
    *,
    settings: GroqSettings | None = None,
    client: Groq | None = None,
) -> dict[str, Any]:
    """
    Ask Groq to rank up to ``prefs.top_k`` restaurants from ``candidates``.

    Returns
    -------
    dict
        ``{"recommendations": [{"id", "rank", "explanation"}, ...], "fallback": bool}``
        ``fallback`` is True when the Groq path was skipped or failed and defaults were used.
    """
    rows = _rows_from_candidates(candidates)
    if not rows:
        return {"recommendations": [], "fallback": False}

    valid_ids = {r["id"] for r in rows}
    cfg = settings or get_groq_settings()

    if not cfg.groq_api_key:
        return {
            "recommendations": _fallback_from_rows(rows, prefs),
            "fallback": True,
        }

    groq_client = client or Groq(api_key=cfg.groq_api_key)
    user_prompt = _user_prompt(prefs, rows)

    def try_parse_from_response(content: str) -> list[dict[str, Any]] | None:
        obj = _parse_json_object(content)
        if obj is None:
            return None
        return _normalize_llm_recommendations(obj, valid_ids, prefs.top_k)

    last_content: str | None = None
    try:
        last_content = _call_groq(groq_client, cfg.groq_model, user_prompt)
        normalized = try_parse_from_response(last_content)
        if normalized is not None:
            return {"recommendations": normalized, "fallback": False}

        # Retry once: JSON parsing / validation failed
        repair_prompt = (
            "Your previous answer was not valid JSON or did not match the required schema "
            "or used unknown ids. Return ONLY one JSON object of the form:\n"
            '{"recommendations":[{"id":"...","rank":1,"explanation":"..."}]}\n'
            "Use only ids from the restaurant list below.\n\n"
            + user_prompt
        )
        if last_content:
            repair_prompt = (
                f"Invalid previous output (do not repeat it): {last_content[:800]}\n\n" + repair_prompt
            )

        last_content = _call_groq(groq_client, cfg.groq_model, repair_prompt)
        normalized = try_parse_from_response(last_content)
        if normalized is not None:
            return {"recommendations": normalized, "fallback": False}
    except Exception:
        # API or unexpected errors → fallback
        pass

    return {
        "recommendations": _fallback_from_rows(rows, prefs),
        "fallback": True,
    }
