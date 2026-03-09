"""Geographic tier classifier and filter.

Tier assignment rules:
- Tier 1: Major metro cities (Delhi, Mumbai, Bangalore, Hyderabad, Chennai, Kolkata, Pune,
  Ahmedabad) — always included in delivery pipeline.
- Tier 2: Large secondary cities — included only if relevance_score >= 30.
- Tier 3: Everything else — included only if relevance_score >= 50.
- Special case: Government-source articles with no city match treated as Tier 1
  (national-scope announcements from MOHUA, NHAI, AAI, Smart Cities).

NOTE: relevance_score thresholds are Phase 4 proxies for AI priority.
Phase 5 AI classification will refine these signals with semantic understanding.
"""

import logging

from pipeline.schemas.article_schema import Article

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# City taxonomy (frozensets for O(1) lookup)
# ---------------------------------------------------------------------------

TIER_1_CITIES: frozenset[str] = frozenset(
    {
        "delhi",
        "delhi ncr",
        "ncr",
        "mumbai",
        "bangalore",
        "bengaluru",
        "hyderabad",
        "chennai",
        "kolkata",
        "pune",
        "ahmedabad",
    }
)

TIER_2_CITIES: frozenset[str] = frozenset(
    {
        "noida",
        "gurugram",
        "gurgaon",
        "faridabad",
        "ghaziabad",
        "jaipur",
        "surat",
        "lucknow",
        "kanpur",
        "nagpur",
        "indore",
        "bhopal",
        "visakhapatnam",
        "patna",
        "vadodara",
        "thane",
        "navi mumbai",
    }
)

# Government feed source names (from data/config.yaml rss_feeds).
# Articles from these sources with no city match are treated as national-scope Tier 1.
GOV_SOURCES: frozenset[str] = frozenset(
    {
        "mohua",
        "nhai",
        "aai",
        "smart cities",
    }
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_geo_tier(article: Article) -> int:
    """Classify an article into geographic tier 1, 2, or 3.

    Algorithm:
    1. Build search text from title + summary (lowercased).
    2. Scan for any Tier 1 city → return 1.
    3. Scan for any Tier 2 city → return 2.
    4. No city found: if source is a government feed → return 1 (national scope).
    5. Otherwise → return 3.

    Args:
        article: Article to classify.

    Returns:
        1 for Tier 1, 2 for Tier 2, 3 for Tier 3.
    """
    text = f"{article.title} {article.summary}".lower()

    for city in TIER_1_CITIES:
        if city in text:
            return 1

    for city in TIER_2_CITIES:
        if city in text:
            return 2

    # No city matched — check if national-scope government source
    if article.source.lower() in GOV_SOURCES:
        return 1

    return 3


def filter_by_geo_tier(
    articles: list[Article],
    tier2_threshold: int = 30,
    tier3_threshold: int = 50,
) -> list[Article]:
    """Filter articles by geographic tier and relevance score thresholds.

    Inclusion rules:
    - Tier 1: always included (high-impact metro cities + gov national-scope).
    - Tier 2: included only if relevance_score >= tier2_threshold (default 30).
    - Tier 3: included only if relevance_score >= tier3_threshold (default 50).

    Each passing article has geo_tier set via model_copy (original unchanged).

    NOTE: Tier 2/3 thresholds are Phase 4 proxies. Phase 5 AI classification
    will refine these signals with semantic understanding.

    Args:
        articles: List of articles to filter.
        tier2_threshold: Minimum relevance_score for Tier 2 articles. Default 30.
        tier3_threshold: Minimum relevance_score for Tier 3 articles. Default 50.

    Returns:
        Filtered list with geo_tier set on each passing article.
    """
    results: list[Article] = []
    tier_counts = {1: 0, 2: 0, 3: 0}

    for article in articles:
        tier = classify_geo_tier(article)

        if tier == 1:
            results.append(article.model_copy(update={"geo_tier": tier}))
            tier_counts[1] += 1
        elif tier == 2 and article.relevance_score >= tier2_threshold:
            results.append(article.model_copy(update={"geo_tier": tier}))
            tier_counts[2] += 1
        elif tier == 3 and article.relevance_score >= tier3_threshold:
            results.append(article.model_copy(update={"geo_tier": tier}))
            tier_counts[3] += 1

    logger.info(
        "Geo filter: %d/%d articles passed (T1:%d T2:%d T3:%d)",
        len(results),
        len(articles),
        tier_counts[1],
        tier_counts[2],
        tier_counts[3],
    )
    return results
