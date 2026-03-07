"""Pydantic v2 schema for fetched articles."""

from typing import Literal

from pydantic import BaseModel


class Article(BaseModel):
    title: str
    url: str
    source: str  # Human-readable source name e.g. "ET Realty"
    published_at: str  # ISO 8601 UTC string; defaults to fetched_at if unavailable
    summary: str = ""  # ALWAYS empty in Phase 3 — Phase 5 AI will populate
    fetched_at: str  # ISO 8601 UTC string — when pipeline fetched this article

    # Phase 4 filter results — populated by filter pipeline
    relevance_score: int = 0
    geo_tier: int = 0  # 0=unclassified, 1/2/3 after geo filter
    dedup_status: Literal["NEW", "DUPLICATE", "UPDATE", ""] = ""
    dedup_ref: str = ""  # Original title if UPDATE, else empty

    # Phase 5 AI analysis results — populated by AI classifier
    priority: Literal["HIGH", "MEDIUM", "LOW", ""] = ""
    location: str = ""
    project_name: str = ""
    budget_amount: str = ""  # Named budget_amount to avoid collision with BaseModel internals
    authority: str = ""
