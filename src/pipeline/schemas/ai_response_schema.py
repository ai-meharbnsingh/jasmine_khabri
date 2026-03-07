"""Pydantic v2 schemas for structured AI classification output.

These models are used as the output_format for Anthropic's .parse() method —
they MUST be plain Pydantic models without custom validators that would break
structured output.
"""

from typing import Literal

from pydantic import BaseModel


class ArticleAnalysis(BaseModel):
    index: int
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    summary: str
    location: str = ""
    project_name: str = ""
    budget: str = ""
    authority: str = ""


class BatchClassificationResponse(BaseModel):
    articles: list[ArticleAnalysis]
