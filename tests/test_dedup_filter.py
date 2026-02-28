"""Tests for title-hash deduplication and UPDATE detection (Phase 4 Plan 03).

Requirements: AI-03 (exact hash dedup), AI-04 (similarity UPDATE detection)
"""

import hashlib

from pipeline.filters.dedup_filter import add_to_seen, check_duplicate, filter_duplicates
from pipeline.schemas.article_schema import Article
from pipeline.schemas.seen_schema import SeenEntry, SeenStore
from pipeline.utils.hashing import compute_title_hash

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_article(
    title: str,
    url: str = "http://example.com/test",
    source: str = "Test",
) -> Article:
    """Return a minimal Article with dummy non-schema fields."""
    return Article(
        title=title,
        url=url,
        source=source,
        published_at="2026-02-28T00:00:00Z",
        fetched_at="2026-02-28T08:00:00Z",
    )


def _make_seen_entry(
    title: str,
    url: str = "http://example.com/old",
) -> SeenEntry:
    """Return a SeenEntry with hashes computed from the given title/url."""
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
    title_hash = compute_title_hash(title)
    return SeenEntry(
        url_hash=url_hash,
        title_hash=title_hash,
        seen_at="2026-02-28T06:00:00+00:00",
        source="Test",
        title=title,
    )


# ---------------------------------------------------------------------------
# TestCheckDuplicate (AI-03)
# ---------------------------------------------------------------------------


class TestCheckDuplicate:
    def test_exact_title_duplicate(self) -> None:
        """Article with same title as a seen entry returns DUPLICATE."""
        seen_title = "Delhi Metro Phase 4 Construction Update"
        seen = SeenStore(entries=[_make_seen_entry(seen_title)])
        article = _make_article(seen_title)

        status, ref = check_duplicate(article, seen)

        assert status == "DUPLICATE"
        assert ref is None

    def test_exact_title_with_punctuation_difference(self) -> None:
        """'Delhi Metro Phase-4' vs seen 'Delhi Metro Phase 4' -> DUPLICATE (normalization)."""
        seen = SeenStore(entries=[_make_seen_entry("Delhi Metro Phase 4")])
        article = _make_article("Delhi Metro Phase-4")

        status, ref = check_duplicate(article, seen)

        assert status == "DUPLICATE"
        assert ref is None

    def test_new_article_not_in_seen(self) -> None:
        """Completely different title returns NEW."""
        seen = SeenStore(entries=[_make_seen_entry("Delhi Metro Phase 4 Construction")])
        article = _make_article("Mumbai Airport Terminal 3 Expansion")

        status, ref = check_duplicate(article, seen)

        assert status == "NEW"
        assert ref is None

    def test_high_similarity_above_80_is_duplicate(self) -> None:
        """Two titles with ~85% similarity are treated as DUPLICATE (not UPDATE)."""
        seen_title = "Delhi Metro Phase 4 Construction Begins"
        article_title = "Delhi Metro Phase 4 Construction Begins Today"
        seen = SeenStore(entries=[_make_seen_entry(seen_title)])
        article = _make_article(article_title)

        status, ref = check_duplicate(article, seen)

        assert status == "DUPLICATE"
        assert ref is None


# ---------------------------------------------------------------------------
# TestUpdateDetection (AI-04)
# ---------------------------------------------------------------------------


class TestUpdateDetection:
    def test_update_detected_in_range(self) -> None:
        """Two titles with ~65% similarity return UPDATE with original title."""
        seen_title = "Delhi Metro Phase 4 Construction Begins"
        article_title = "Delhi Metro Phase 4 Faces Major Delays"
        seen = SeenStore(entries=[_make_seen_entry(seen_title)])
        article = _make_article(article_title)

        status, ref = check_duplicate(article, seen)

        assert status == "UPDATE"
        assert ref == seen_title

    def test_below_50_is_new(self) -> None:
        """Two very different titles (~30% similarity) return NEW."""
        seen = SeenStore(entries=[_make_seen_entry("Delhi Metro construction begins")])
        article = _make_article("Mumbai Airport expansion approved by government")

        status, ref = check_duplicate(article, seen)

        assert status == "NEW"
        assert ref is None

    def test_update_ref_contains_original_title(self) -> None:
        """The dedup_ref for an UPDATE article contains the original seen entry's title string."""
        original_title = "Delhi Metro Phase 4 Construction Begins"
        seen = SeenStore(entries=[_make_seen_entry(original_title)])
        article = _make_article("Delhi Metro Phase 4 Faces Major Delays")

        status, ref = check_duplicate(article, seen)

        assert status == "UPDATE"
        # ref must be the human-readable original title, not a hash
        assert ref == original_title
        assert len(ref) > 10  # not a hash digest


# ---------------------------------------------------------------------------
# TestFilterDuplicates
# ---------------------------------------------------------------------------


class TestFilterDuplicates:
    def test_duplicates_excluded_from_results(self) -> None:
        """3 articles, 1 is duplicate of seen entry. Filtered result has 2 articles."""
        seen = SeenStore(entries=[_make_seen_entry("Delhi Metro Phase 4 Construction Begins")])
        articles = [
            _make_article("Delhi Metro Phase 4 Construction Begins"),  # duplicate
            _make_article("Mumbai Airport Terminal 3 Expansion"),  # new
            _make_article("Bengaluru Smart City Road Project"),  # new
        ]

        results, _ = filter_duplicates(articles, seen)

        assert len(results) == 2
        titles = [a.title for a in results]
        assert "Delhi Metro Phase 4 Construction Begins" not in titles

    def test_new_articles_marked_as_new(self) -> None:
        """NEW articles in result have dedup_status == 'NEW'."""
        seen = SeenStore()
        articles = [
            _make_article("Delhi Metro Phase 4 Construction"),
            _make_article("Mumbai Airport Expansion Plans"),
        ]

        results, _ = filter_duplicates(articles, seen)

        assert all(a.dedup_status == "NEW" for a in results)

    def test_update_articles_included_with_status(self) -> None:
        """UPDATE article is included in result with dedup_status='UPDATE' and dedup_ref set."""
        original_title = "Delhi Metro Phase 4 Construction Begins"
        seen = SeenStore(entries=[_make_seen_entry(original_title)])
        article = _make_article("Delhi Metro Phase 4 Faces Major Delays")

        results, _ = filter_duplicates([article], seen)

        assert len(results) == 1
        assert results[0].dedup_status == "UPDATE"
        assert results[0].dedup_ref == original_title

    def test_new_and_update_added_to_seen(self) -> None:
        """After filtering, returned SeenStore contains new entries for NEW and UPDATE articles."""
        original_title = "Delhi Metro Phase 4 Construction Begins"
        seen = SeenStore(entries=[_make_seen_entry(original_title)])
        new_article = _make_article(
            "Bengaluru Smart City Road Project", url="http://example.com/new1"
        )
        update_article = _make_article(
            "Delhi Metro Phase 4 Faces Major Delays", url="http://example.com/new2"
        )

        _, updated_seen = filter_duplicates([new_article, update_article], seen)

        # Should have original entry + 2 new entries
        assert len(updated_seen.entries) == 3

    def test_duplicate_not_added_to_seen(self) -> None:
        """DUPLICATE articles are NOT added to the returned SeenStore."""
        seen_title = "Delhi Metro Phase 4 Construction Begins"
        seen = SeenStore(entries=[_make_seen_entry(seen_title)])
        duplicate = _make_article(seen_title)

        _, updated_seen = filter_duplicates([duplicate], seen)

        # Count must remain 1 (not incremented)
        assert len(updated_seen.entries) == 1


# ---------------------------------------------------------------------------
# TestAddToSeen
# ---------------------------------------------------------------------------


class TestAddToSeen:
    def test_adds_entry_with_correct_hashes(self) -> None:
        """add_to_seen returns new SeenStore with one more entry with correct hashes."""
        seen = SeenStore()
        article = _make_article(
            "Delhi Metro Phase 4 Construction", url="http://example.com/article1"
        )

        updated = add_to_seen(article, seen)

        assert len(updated.entries) == 1
        entry = updated.entries[0]

        expected_url_hash = hashlib.sha256(article.url.encode("utf-8")).hexdigest()
        expected_title_hash = compute_title_hash(article.title)

        assert entry.url_hash == expected_url_hash
        assert entry.title_hash == expected_title_hash
        assert entry.source == article.source
        assert entry.title == article.title

    def test_functional_no_mutation(self) -> None:
        """Original SeenStore is not mutated (functional style per project convention)."""
        seen = SeenStore()
        article = _make_article("Delhi Metro Phase 4 Construction")

        updated = add_to_seen(article, seen)

        # Original unchanged
        assert len(seen.entries) == 0
        # New copy has entry
        assert len(updated.entries) == 1
        # They are distinct objects
        assert updated is not seen
