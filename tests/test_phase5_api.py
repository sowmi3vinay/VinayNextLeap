"""
Phase 5 backend tests: ``POST /recommend`` with mocked DataFrame and LLM (no Hugging Face / Groq).

Run: ``pytest tests/test_phase5_api.py -v``
"""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from phase_5.api import router
from phase_5.deps import get_restaurant_df


def _make_sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id": "r1",
                "name": "Test Bistro",
                "city": "testville",
                "cuisines": ["italian", "pizza"],
                "rating": 4.5,
                "cost_for_two": 800.0,
                "budget_tier": "medium",
            },
            {
                "id": "r2",
                "name": "Other City Diner",
                "city": "elsewhere",
                "cuisines": ["italian"],
                "rating": 4.8,
                "cost_for_two": 600.0,
                "budget_tier": "medium",
            },
        ]
    )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    df = _make_sample_df()

    def override_df(request: Request) -> pd.DataFrame:
        return df

    def fake_llm(candidates, prefs):
        # Simulate Groq: rank the first candidate id from filtered set
        ids = [str(x) for x in candidates["id"].tolist()] if len(candidates) else []
        if not ids:
            return {"recommendations": [], "fallback": False}
        return {
            "recommendations": [
                {
                    "id": ids[0],
                    "rank": 1,
                    "explanation": "Mock: best match for your preferences.",
                }
            ],
            "fallback": False,
        }

    import phase_5.api as api_mod

    monkeypatch.setattr(api_mod, "recommend_with_llm", fake_llm)

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_restaurant_df] = override_df
    return TestClient(app)


def test_post_recommend_happy_path_returns_merged_fields(client: TestClient) -> None:
    """Valid body → 200, response includes name, cuisines, rating, cost, explanation."""
    res = client.post(
        "/recommend",
        json={
            "location": "testville",
            "budget": 2000,
            "cuisines": ["italian"],
            "min_rating": 4.0,
            "top_k": 5,
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["fallback"] is False
    assert data["candidates_considered"] >= 1
    assert len(data["recommendations"]) == 1
    item = data["recommendations"][0]
    assert item["name"] == "Test Bistro"
    assert "italian" in item["cuisines"]
    assert item["rating"] == 4.5
    assert item["cost"] == 800.0
    assert "Mock:" in item["explanation"]


def test_get_localities_sorted_unique(client: TestClient) -> None:
    """GET /localities returns distinct city values from the (mocked) dataset."""
    res = client.get("/localities")
    assert res.status_code == 200, res.text
    data = res.json()
    assert "localities" in data
    assert data["localities"] == ["elsewhere", "testville"]
    assert len(data["localities"]) == len(set(data["localities"]))


def test_post_recommend_validation_error_invalid_budget(client: TestClient) -> None:
    """Non-numeric or out-of-range budget → 422."""
    res = client.post(
        "/recommend",
        json={
            "location": "testville",
            "budget": -100,
            "top_k": 5,
        },
    )
    assert res.status_code == 422


def test_post_recommend_no_matches_empty_recommendations(client: TestClient) -> None:
    """Filter yields no rows → 200 with empty list and zero candidates considered."""
    res = client.post(
        "/recommend",
        json={
            "location": "nomatch",
            "budget": 2000,
            "min_rating": 0.0,
            "top_k": 5,
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["recommendations"] == []
    assert data["candidates_considered"] == 0
    assert data["fallback"] is False
</think>
Fixing test 3: removing incomplete code and using the existing client fixture with a non-matching location.

<｜tool▁calls▁begin｜><｜tool▁call▁begin｜>
Read