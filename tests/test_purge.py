"""Tests for purge utility — created RED phase before purge.py exists.

Tests cover:
- Old entries removed (> 7 days)
- Recent entries kept (<= 7 days)
- Mixed store: old removed, new kept
- Malformed timestamp: entry kept (not silently dropped)
- Empty store: no exception
- Naive timestamp: treated as UTC, kept if recent
"""

from datetime import UTC, datetime, timedelta

from pipeline.schemas.seen_schema import SeenEntry, SeenStore
from pipeline.utils.purge import purge_old_entries


def _make_entry(url_hash: str, days_ago: float, seen_at_override: str | None = None) -> SeenEntry:
    """Helper: create a SeenEntry with seen_at N days ago from now (UTC)."""
    if seen_at_override is not None:
        ts = seen_at_override
    else:
        ts = (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()
    return SeenEntry(
        url_hash=url_hash,
        title_hash=f"th-{url_hash}",
        seen_at=ts,
        source="test",
        title=f"Test article {url_hash}",
    )


class TestPurgeOldEntries:
    """Tests for purge_old_entries(store, days=7) -> SeenStore."""

    def test_purge_removes_old_entries(self):
        """Entry whose seen_at is 10 days ago must be removed after purge(days=7)."""
        entry = _make_entry("old-001", days_ago=10)
        store = SeenStore(entries=[entry])

        result = purge_old_entries(store, days=7)

        assert len(result.entries) == 0

    def test_purge_keeps_recent_entries(self):
        """Entry whose seen_at is 2 days ago must be kept after purge(days=7)."""
        entry = _make_entry("recent-001", days_ago=2)
        store = SeenStore(entries=[entry])

        result = purge_old_entries(store, days=7)

        assert len(result.entries) == 1
        assert result.entries[0].url_hash == "recent-001"

    def test_purge_mixed_old_and_new(self):
        """Store with 3 entries: 10-day-old removed; 5-day and 1-day kept."""
        old_entry = _make_entry("old-mix", days_ago=10)
        mid_entry = _make_entry("mid-mix", days_ago=5)
        new_entry = _make_entry("new-mix", days_ago=1)
        store = SeenStore(entries=[old_entry, mid_entry, new_entry])

        result = purge_old_entries(store, days=7)

        url_hashes = [e.url_hash for e in result.entries]
        assert len(result.entries) == 2
        assert "old-mix" not in url_hashes
        assert "mid-mix" in url_hashes
        assert "new-mix" in url_hashes

    def test_purge_keeps_malformed_timestamp(self):
        """Entry with unparseable seen_at must be kept (fail-safe, not fail-silent)."""
        entry = _make_entry("malformed-001", days_ago=0, seen_at_override="not-a-date")
        store = SeenStore(entries=[entry])

        result = purge_old_entries(store, days=7)

        assert len(result.entries) == 1
        assert result.entries[0].url_hash == "malformed-001"

    def test_purge_empty_store(self):
        """Purging an empty SeenStore must return empty store without raising."""
        store = SeenStore()

        result = purge_old_entries(store, days=7)

        assert len(result.entries) == 0

    def test_purge_handles_naive_timestamp(self):
        """Naive ISO timestamps (no tz) are treated as UTC — recent entry kept."""
        # Naive datetime 2 days ago (no tzinfo)
        naive_ts = (datetime.now(UTC) - timedelta(days=2)).replace(tzinfo=None).isoformat()
        entry = _make_entry("naive-001", days_ago=0, seen_at_override=naive_ts)
        store = SeenStore(entries=[entry])

        result = purge_old_entries(store, days=7)

        assert len(result.entries) == 1
        assert result.entries[0].url_hash == "naive-001"
