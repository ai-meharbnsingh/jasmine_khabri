"""Title-hash deduplication and UPDATE detection."""

import hashlib
import logging
from datetime import UTC, datetime
from difflib import SequenceMatcher

from pipeline.schemas.article_schema import Article
from pipeline.schemas.seen_schema import SeenEntry, SeenStore
from pipeline.utils.hashing import compute_title_hash, normalize_title

logger = logging.getLogger(__name__)


def check_duplicate(article: Article, seen: SeenStore) -> tuple[str, str | None]:
    """Check if an article is a duplicate, update, or new.

    Two-stage detection:
    1. Exact hash match: title hashes identical → DUPLICATE
    2. Similarity scan using SequenceMatcher:
       - ratio >= 0.80 → DUPLICATE
       - 0.50 <= ratio < 0.80 → UPDATE (returns original title as reference)
    3. No match → NEW

    Args:
        article: Article to check.
        seen: Current seen article store.

    Returns:
        Tuple of (status, ref) where:
        - status is "NEW", "DUPLICATE", or "UPDATE"
        - ref is the original title if UPDATE, else None
    """
    title_hash = compute_title_hash(article.title)
    norm_title = normalize_title(article.title)

    # Stage 1: Exact hash match — O(n) scan, short-circuit on first match
    for entry in seen.entries:
        if entry.title_hash == title_hash:
            return ("DUPLICATE", None)

    # Stage 2: Similarity scan using SequenceMatcher
    best_update: tuple[float, str] | None = None

    for entry in seen.entries:
        ratio = SequenceMatcher(None, norm_title, normalize_title(entry.title)).ratio()

        if ratio >= 0.80:
            return ("DUPLICATE", None)

        if 0.50 <= ratio < 0.80:
            # Track best UPDATE candidate (highest similarity in range)
            if best_update is None or ratio > best_update[0]:
                best_update = (ratio, entry.title)

    if best_update is not None:
        return ("UPDATE", best_update[1])

    return ("NEW", None)


def add_to_seen(article: Article, seen: SeenStore) -> SeenStore:
    """Add an article to the seen store (functional style — no mutation).

    Args:
        article: Article to add.
        seen: Current seen store.

    Returns:
        New SeenStore with article entry appended.
    """
    url_hash = hashlib.sha256(article.url.encode("utf-8")).hexdigest()
    title_hash = compute_title_hash(article.title)
    entry = SeenEntry(
        url_hash=url_hash,
        title_hash=title_hash,
        seen_at=datetime.now(UTC).isoformat(),
        source=article.source,
        title=article.title,
    )
    return SeenStore(entries=[*seen.entries, entry])


def filter_duplicates(
    articles: list[Article],
    seen: SeenStore,
) -> tuple[list[Article], SeenStore]:
    """Filter duplicate articles using title-hash dedup and similarity UPDATE detection.

    For each article:
    - DUPLICATE: excluded from results, not added to seen
    - NEW: included with dedup_status='NEW', added to seen
    - UPDATE: included with dedup_status='UPDATE' and dedup_ref set, added to seen

    Logs filter counts at INFO level.

    Args:
        articles: List of articles to deduplicate.
        seen: Current seen article store.

    Returns:
        Tuple of (filtered_articles, updated_seen).
    """
    results: list[Article] = []
    new_count = 0
    update_count = 0
    duplicate_count = 0

    for article in articles:
        status, ref = check_duplicate(article, seen)

        if status == "DUPLICATE":
            duplicate_count += 1
            # Do not add to seen and do not include in results
        elif status == "NEW":
            new_count += 1
            results.append(article.model_copy(update={"dedup_status": "NEW"}))
            seen = add_to_seen(article, seen)
        elif status == "UPDATE":
            update_count += 1
            results.append(
                article.model_copy(update={"dedup_status": "UPDATE", "dedup_ref": ref or ""})
            )
            seen = add_to_seen(article, seen)

    logger.info(
        "Dedup filter: %d/%d articles passed (%d new, %d updates, %d duplicates)",
        len(results),
        len(articles),
        new_count,
        update_count,
        duplicate_count,
    )
    return (results, seen)
