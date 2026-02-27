"""Pydantic v2 schema for fetched articles."""

from pydantic import BaseModel


class Article(BaseModel):
    title: str
    url: str
    source: str  # Human-readable source name e.g. "ET Realty"
    published_at: str  # ISO 8601 UTC string; defaults to fetched_at if unavailable
    summary: str = ""  # ALWAYS empty in Phase 3 — Phase 5 AI will populate
    fetched_at: str  # ISO 8601 UTC string — when pipeline fetched this article
