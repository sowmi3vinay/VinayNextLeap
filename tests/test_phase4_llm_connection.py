"""
Integration checks for Groq (Phase 4). Requires ``GROQ_API_KEY`` in repo-root ``.env``.

Run from repo root: ``pytest tests/test_phase4_llm_connection.py -v``
"""

from __future__ import annotations

import pytest
from groq import Groq

from phase_2.models import UserPreferences
from phase_4 import get_groq_settings, recommend_with_llm


def _require_groq_key():
    cfg = get_groq_settings()
    if not cfg.groq_api_key:
        pytest.skip("GROQ_API_KEY missing in .env (see .env.example)")
    return cfg


def test_groq_settings_loads_api_key():
    """Settings read from ``.env`` include a non-empty Groq API key."""
    cfg = _require_groq_key()
    assert len(cfg.groq_api_key) > 20, "API key looks too short; check .env"


def test_groq_client_minimal_chat_completion():
    """Direct Groq chat call returns non-empty assistant content (connection + auth)."""
    cfg = _require_groq_key()
    client = Groq(api_key=cfg.groq_api_key)
    completion = client.chat.completions.create(
        model=cfg.groq_model,
        temperature=0,
        max_tokens=16,
        messages=[
            {"role": "user", "content": 'Reply with exactly the word OK in JSON: {"ok":true}'},
        ],
    )
    text = completion.choices[0].message.content
    assert text and text.strip(), "Empty completion from Groq"


def test_recommend_with_llm_returns_valid_shape():
    """End-to-end ``recommend_with_llm`` with stub candidates returns ranked explanations."""
    _require_groq_key()
    prefs = UserPreferences(
        location="testville",
        budget=1500.0,
        cuisines=["italian"],
        min_rating=4.0,
        top_k=3,
    )
    candidates = [
        {
            "id": "a1",
            "name": "Trattoria Stub",
            "city": "testville",
            "cuisines": ["italian", "pizza"],
            "rating": 4.5,
            "cost_for_two": 900.0,
            "budget_tier": "medium",
        },
        {
            "id": "b2",
            "name": "Pasta Place Stub",
            "city": "testville",
            "cuisines": ["italian"],
            "rating": 4.2,
            "cost_for_two": 700.0,
            "budget_tier": "medium",
        },
    ]
    out = recommend_with_llm(candidates, prefs)
    assert "recommendations" in out and "fallback" in out
    recs = out["recommendations"]
    assert isinstance(recs, list)
    assert len(recs) <= prefs.top_k
    for i, item in enumerate(recs, start=1):
        assert set(item.keys()) >= {"id", "rank", "explanation"}
        assert item["id"] in {"a1", "b2"}
        assert isinstance(item["explanation"], str) and item["explanation"].strip()
        assert item["rank"] == i
    # If LLM path worked we usually get fallback False; allow True if model misbehaved
    assert len(recs) >= 1


def test_recommend_with_llm_empty_candidates_no_call():
    """No restaurants → empty list, no need for API."""
    prefs = UserPreferences(
        location="nowhere",
        budget=500.0,
        top_k=5,
    )
    out = recommend_with_llm([], prefs)
    assert out == {"recommendations": [], "fallback": False}
