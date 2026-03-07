"""Pydantic v2 schema for monthly AI cost tracking.

Follows gnews_quota_schema.py pattern — simple Pydantic model, no complex validators.
"""

from pydantic import BaseModel


class AICost(BaseModel):
    month: str  # "YYYY-MM" format
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    call_count: int = 0
