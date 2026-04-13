"""Phase 5 — FastAPI HTTP layer."""

from phase_5.api import router
from phase_5.schemas import (
    LocalitiesResponse,
    RecommendRequest,
    RecommendationItem,
    RecommendResponse,
)

__all__ = [
    "LocalitiesResponse",
    "RecommendationItem",
    "RecommendRequest",
    "RecommendResponse",
    "router",
]
