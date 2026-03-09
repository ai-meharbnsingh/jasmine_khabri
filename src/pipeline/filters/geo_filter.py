"""Geographic tier classifier and filter.

Tier assignment rules:
- Tier 1: Major metro cities (Delhi, Mumbai, Bangalore, Hyderabad, Chennai, Kolkata, Pune,
  Ahmedabad) — always included in delivery pipeline.
- Tier 2: Large secondary cities — included if score is in the top two-thirds of the batch range.
- Tier 3: Everything else — included if score is in the top third of the batch range.
- Special case: Government-source articles with no city match treated as Tier 1
  (national-scope announcements from MOHUA, NHAI, AAI, Smart Cities).

Thresholds are computed dynamically from each batch's score distribution (curve grading)
so that articles always appear regardless of absolute score levels.
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


def compute_score_bands(scores: list[int]) -> tuple[float, float]:
    """Compute dynamic tier thresholds from a batch of relevance scores.

    Divides the score range into 3 equal bands (curve grading):
    - Top band:    [max - band, max]       → tier 3 must be here
    - Middle band: [max - 2*band, max - band) → tier 2 threshold
    - Bottom band: [min, max - 2*band)      → below both thresholds

    When all scores are equal (range=0), both thresholds equal the score
    so every article passes.

    Returns:
        (tier2_threshold, tier3_threshold) — float values for comparison.
    """
    if not scores:
        return (0.0, 0.0)

    max_score = max(scores)
    min_score = min(scores)
    score_range = max_score - min_score

    if score_range == 0:
        # All identical scores — everything passes
        return (float(min_score), float(min_score))

    band = score_range / 3
    tier2_threshold = max_score - 2 * band  # top 2/3 of range
    tier3_threshold = max_score - band  # top 1/3 of range
    return (tier2_threshold, tier3_threshold)


def filter_by_geo_tier(articles: list[Article]) -> list[Article]:
    """Filter articles by geographic tier with dynamic score thresholds.

    Thresholds are computed from the batch's actual score distribution
    (curve grading), so articles always appear regardless of absolute
    score levels.

    Inclusion rules:
    - Tier 1: always included (high-impact metro cities + gov national-scope).
    - Tier 2: included if relevance_score >= tier2_threshold (top 2/3 of range).
    - Tier 3: included if relevance_score >= tier3_threshold (top 1/3 of range).

    Each passing article has geo_tier set via model_copy (original unchanged).

    Args:
        articles: List of articles to filter.

    Returns:
        Filtered list with geo_tier set on each passing article.
    """
    if not articles:
        return []

    scores = [a.relevance_score for a in articles]
    tier2_threshold, tier3_threshold = compute_score_bands(scores)

    logger.info(
        "Geo filter dynamic thresholds: tier2=%.1f, tier3=%.1f (score range %d-%d)",
        tier2_threshold,
        tier3_threshold,
        min(scores),
        max(scores),
    )

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
