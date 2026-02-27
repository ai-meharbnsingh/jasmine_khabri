"""Pydantic v2 schema models for seen article store (seen.json, history.json)."""

from pydantic import BaseModel, Field


class SeenEntry(BaseModel):
    url_hash: str
    title_hash: str
    seen_at: str  # ISO 8601 datetime string
    source: str
    title: str = ""  # Original title for debugging/display


class SeenStore(BaseModel):
    entries: list[SeenEntry] = Field(default_factory=list)
