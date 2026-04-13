"""
Request-scoped access to the loaded restaurant table (set in Phase 6 lifespan or lazy-loaded).
"""

from __future__ import annotations

import pandas as pd
from fastapi import Request

from phase_1.data_loader import load_and_process_data


def get_restaurant_df(request: Request) -> pd.DataFrame:
    """
    Return the app-wide restaurant DataFrame.

    Prefer ``app.state.restaurants_df`` populated at startup; otherwise load once lazily
    (useful for tests or minimal apps without lifespan).
    """
    cached = getattr(request.app.state, "restaurants_df", None)
    if cached is not None:
        return cached
    df = load_and_process_data()
    request.app.state.restaurants_df = df
    return df
