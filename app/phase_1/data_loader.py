"""
Phase 1 — Load Zomato data from Hugging Face and build a canonical pandas DataFrame.

Output columns: id, name, city, cuisines, rating, cost_for_two, budget_tier
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd
from datasets import load_dataset

from phase_1.config import Settings, get_settings

# HF dataset column names (ManikaSaini/zomato-restaurant-recommendation)
COL_NAME = "name"
COL_CUISINES = "cuisines"
COL_RATE = "rate"
COL_COST = "approx_cost(for two people)"
# Area / listing: prefer listed_in(city) for broader locality; fallback location
COL_LISTED_CITY = "listed_in(city)"
COL_LOCATION = "location"


def _parse_rating(raw: Any) -> float | None:
    """
    Parse Zomato ``rate`` strings like '4.1/5', 'NEW', '-', or numeric.
    Returns None if missing or not parseable.
    """
    if isinstance(raw, (int, float)) and not pd.isna(raw):
        try:
            v = float(raw)
            if 0 <= v <= 5:
                return v
        except (TypeError, ValueError):
            pass
        return None
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).strip()
    if not s or s in {"-", "nan", "None"}:
        return None
    if s.upper() == "NEW" or not any(c.isdigit() for c in s):
        return None
    # First number in string (handles "4.1/5" and "4.1")
    m = re.search(r"(\d+\.?\d*)", s)
    if not m:
        return None
    try:
        val = float(m.group(1))
        if val < 0 or val > 5:
            return None
        return val
    except ValueError:
        return None


def _parse_cost_for_two(raw: Any) -> float | None:
    """Parse cost strings like '800', '1,200' to float INR."""
    if isinstance(raw, (int, float)) and not pd.isna(raw):
        try:
            v = float(raw)
            return v if v >= 0 else None
        except (TypeError, ValueError):
            return None
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).strip()
    if not s or s in {"-", "nan", "None"}:
        return None
    digits = re.sub(r"[^\d.]", "", s)
    if not digits:
        return None
    try:
        return float(digits)
    except ValueError:
        return None


def _cuisines_to_list(raw: Any) -> list[str]:
    """Split comma-separated cuisines, lowercase, strip empties."""
    if isinstance(raw, (list, tuple)):
        return [str(x).strip().lower() for x in raw if str(x).strip()]
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    s = str(raw).strip()
    if not s:
        return []
    parts = [p.strip().lower() for p in s.split(",")]
    return [p for p in parts if p]


def _normalize_city(row: pd.Series) -> str:
    """
    Use listed_in(city) when present, else location — Zomato export uses both.
    Lowercase for consistent filtering later.
    """
    listed = row.get(COL_LISTED_CITY)
    loc = row.get(COL_LOCATION)
    for val in (listed, loc):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            continue
        t = str(val).strip().lower()
        if t:
            return t
    return ""


def _budget_tier(cost: float | None, settings: Settings) -> str | None:
    """Map cost_for_two to low / medium / high; None if cost unknown."""
    if cost is None or pd.isna(cost):
        return None
    if cost <= settings.budget_low_max_inr:
        return "low"
    if cost <= settings.budget_medium_max_inr:
        return "medium"
    return "high"


def load_and_process_data(settings: Settings | None = None) -> pd.DataFrame:
    """
    Download/load the Hugging Face dataset, normalize fields, return canonical DataFrame.

    Does not write to disk by default (datasets may cache in HF home directory).

    Returns
    -------
    pandas.DataFrame
        Columns: id, name, city, cuisines, rating, cost_for_two, budget_tier
    """
    cfg = settings or get_settings()

    ds = load_dataset(cfg.hf_dataset_name, split=cfg.hf_dataset_split)
    df = ds.to_pandas()

    required = {COL_NAME, COL_CUISINES, COL_RATE, COL_COST}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Dataset missing expected columns {missing}. Found: {list(df.columns)}"
        )

    # Stable string id from row index (reproducible for same dataset version)
    out = pd.DataFrame()
    out["id"] = df.index.astype(str)
    out["name"] = df[COL_NAME].astype(str).str.strip()
    out["city"] = df.apply(_normalize_city, axis=1)

    out["cuisines"] = df[COL_CUISINES].apply(_cuisines_to_list)
    out["rating"] = df[COL_RATE].apply(_parse_rating)
    out["cost_for_two"] = df[COL_COST].apply(_parse_cost_for_two)

    out["budget_tier"] = out["cost_for_two"].apply(lambda c: _budget_tier(c, cfg))

    # Drop rows with no name (invalid records); keep ``id`` as original dataset row index
    out = out[out["name"].str.len() > 0].reset_index(drop=True)

    return out


if __name__ == "__main__":
    # Smoke test: requires network on first run (Hugging Face download)
    # Run from repo root after: pip install -e .
    frame = load_and_process_data()
    print(frame.head())
    print(frame.dtypes)
    print("rows:", len(frame))
