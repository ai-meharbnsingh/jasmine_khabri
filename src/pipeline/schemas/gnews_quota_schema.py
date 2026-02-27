"""Pydantic v2 schema for GNews API daily quota tracking."""

from pydantic import BaseModel


class GNewsQuota(BaseModel):
    date: str  # ISO date string "YYYY-MM-DD" in UTC
    calls_used: int = 0
    daily_limit: int = 25
