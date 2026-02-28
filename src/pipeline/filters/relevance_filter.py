"""Keyword relevance scoring and exclusion filter — first stage of filter pipeline."""

import logging

from pipeline.schemas.article_schema import Article
from pipeline.schemas.keywords_schema import KeywordsConfig
from pipeline.utils.hashing import normalize_title  # noqa: F401

logger = logging.getLogger(__name__)


def score_article(article: Article, keywords: KeywordsConfig) -> tuple[bool, int]:
    """Score an article against keyword library.

    Returns (passes_exclusion, score) where:
    - passes_exclusion=False means article must be discarded regardless of score
    - score is cumulative keyword relevance score (title hit=20, body hit=10)
    """
    raise NotImplementedError


def filter_by_relevance(
    articles: list[Article],
    keywords: KeywordsConfig,
    threshold: int = 40,
) -> list[Article]:
    """Filter articles by keyword relevance.

    Returns only articles that:
    1. Pass exclusion check (no exclusion keyword in title or summary)
    2. Score at or above threshold

    Each passing article has relevance_score set via model_copy.
    """
    raise NotImplementedError
