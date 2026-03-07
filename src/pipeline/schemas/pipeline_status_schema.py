"""Pydantic v2 schema for pipeline run status.

Follows ai_cost_schema.py pattern — simple Pydantic model with defaults.
Written by the batch pipeline at the end of every run; read by the bot /status command.
"""

from pydantic import BaseModel


class PipelineStatus(BaseModel):
    last_run_utc: str = ""
    articles_fetched: int = 0
    articles_delivered: int = 0
    telegram_success: int = 0
    telegram_failures: int = 0
    email_success: int = 0
    sources_active: int = 0
    run_duration_seconds: float = 0.0
