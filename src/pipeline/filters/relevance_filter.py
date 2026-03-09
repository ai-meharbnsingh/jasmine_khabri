"""Keyword relevance scoring and exclusion filter — first stage of filter pipeline."""

import logging

from pipeline.schemas.article_schema import Article
from pipeline.schemas.keywords_schema import KeywordsConfig

logger = logging.getLogger(__name__)


def score_article(article: Article, keywords: KeywordsConfig) -> tuple[bool, int]:
    """Score an article against keyword library.

    Returns (passes_exclusion, score) where:
    - passes_exclusion=False means article must be discarded regardless of score
    - score is cumulative keyword relevance score (title hit=20, body hit=10)

    Algorithm:
    1. Exclusion check first (short-circuit): if any exclusion keyword found
       anywhere in title+summary text, return (False, 0).
    2. Keyword scoring: for each active keyword —
       - title match → 20 points
       - summary-only match → 10 points
       Each keyword counted at most once (title match takes priority).
    """
    text = f"{article.title} {article.summary}".lower()

    # Exclusion check — short-circuit before scoring
    for exclusion in keywords.exclusions:
        if exclusion.lower() in text:
            return (False, 0)

    # Keyword scoring
    score = 0
    title_lower = article.title.lower()

    for keyword in keywords.active_keywords():
        kw = keyword.lower()
        if kw in title_lower:
            score += 20
        elif kw in text:
            score += 10

    return (True, score)


def filter_by_relevance(
    articles: list[Article],
    keywords: KeywordsConfig,
    threshold: int = 20,
) -> list[Article]:
    """Filter articles by keyword relevance.

    Returns only articles that:
    1. Pass exclusion check (no exclusion keyword in title or summary)
    2. Score at or above threshold

    Each passing article has relevance_score set via model_copy (original unchanged).
    """
    results: list[Article] = []

    for article in articles:
        passes_exclusion, score = score_article(article, keywords)
        if not passes_exclusion:
            continue
        if score < threshold:
            continue
        results.append(article.model_copy(update={"relevance_score": score}))

    logger.info(
        "Relevance filter: %d/%d articles passed (threshold=%d)",
        len(results),
        len(articles),
        threshold,
    )
    return results
