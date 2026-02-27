"""History purge utility: removes SeenStore entries older than N days."""

import logging
from datetime import UTC, datetime, timedelta

from pipeline.schemas.seen_schema import SeenStore

log = logging.getLogger(__name__)


def purge_old_entries(store: SeenStore, days: int = 7) -> SeenStore:
    """Return a new SeenStore with entries older than `days` removed.

    Uses `seen_at` (ISO 8601, fetch time) as the age reference.
    Entries with malformed timestamps are kept (not silently dropped).
    Naive timestamps (no tzinfo) are assumed UTC.
    """
    cutoff = datetime.now(UTC) - timedelta(days=days)
    before = len(store.entries)
    kept = []
    for entry in store.entries:
        try:
            ts = datetime.fromisoformat(entry.seen_at)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            if ts >= cutoff:
                kept.append(entry)
        except ValueError:
            log.warning("Malformed seen_at for %s — keeping entry", entry.url_hash)
            kept.append(entry)
    purged = before - len(kept)
    if purged:
        log.info("Purged %d entries older than %d days from store", purged, days)
    return SeenStore(entries=kept)
