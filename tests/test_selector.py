"""Tests for priority-based article selector."""

from pipeline.deliverers.selector import select_articles
from pipeline.schemas.article_schema import Article


def _make_article(
    priority: str = "HIGH",
    dedup_status: str = "NEW",
    title: str = "Test Article",
) -> Article:
    """Helper to create a test article with minimal required fields."""
    return Article(
        title=title,
        url="https://example.com/article",
        source="Test Source",
        published_at="2026-03-07T00:00:00Z",
        fetched_at="2026-03-07T00:00:00Z",
        priority=priority,
        dedup_status=dedup_status,
    )


class TestSelectArticlesBasicAllocation:
    """Test priority allocation with various article distributions."""

    def test_standard_allocation_caps_high_at_8(self):
        """15 articles: 10 HIGH, 3 MED, 2 LOW -> high capped at 8."""
        articles = (
            [_make_article("HIGH", title=f"High {i}") for i in range(10)]
            + [_make_article("MEDIUM", title=f"Med {i}") for i in range(3)]
            + [_make_article("LOW", title=f"Low {i}") for i in range(2)]
        )
        high, medium, low = select_articles(articles)
        assert len(high) == 8
        assert len(medium) == 3
        assert len(low) == 2
        assert len(high) + len(medium) + len(low) <= 15

    def test_under_cap_returns_all(self):
        """5 articles: all included when under 15."""
        articles = (
            [_make_article("HIGH", title=f"High {i}") for i in range(2)]
            + [_make_article("MEDIUM", title=f"Med {i}") for i in range(2)]
            + [_make_article("LOW", title=f"Low {i}") for i in range(1)]
        )
        high, medium, low = select_articles(articles)
        assert len(high) == 2
        assert len(medium) == 2
        assert len(low) == 1

    def test_surplus_medium_fills_when_high_low(self):
        """20 articles: 3 HIGH, 10 MED, 7 LOW -> fill from medium surplus."""
        articles = (
            [_make_article("HIGH", title=f"High {i}") for i in range(3)]
            + [_make_article("MEDIUM", title=f"Med {i}") for i in range(10)]
            + [_make_article("LOW", title=f"Low {i}") for i in range(7)]
        )
        high, medium, low = select_articles(articles)
        assert len(high) == 3
        assert len(medium) == 10
        assert len(low) == 2
        assert len(high) + len(medium) + len(low) == 15

    def test_total_never_exceeds_max_stories(self):
        """With many articles, total must not exceed max_stories."""
        articles = (
            [_make_article("HIGH", title=f"High {i}") for i in range(20)]
            + [_make_article("MEDIUM", title=f"Med {i}") for i in range(20)]
            + [_make_article("LOW", title=f"Low {i}") for i in range(20)]
        )
        high, medium, low = select_articles(articles, max_stories=15)
        assert len(high) + len(medium) + len(low) <= 15


class TestSelectArticlesFiltering:
    """Test dedup_status filtering."""

    def test_only_new_articles_selected(self):
        """Only NEW articles are considered; DUPLICATE/UPDATE ignored."""
        articles = [
            _make_article("HIGH", "NEW", title="New article"),
            _make_article("HIGH", "DUPLICATE", title="Dupe article"),
            _make_article("HIGH", "UPDATE", title="Update article"),
            _make_article("MEDIUM", "NEW", title="New medium"),
            _make_article("LOW", "", title="Empty status"),
        ]
        high, medium, low = select_articles(articles)
        all_selected = high + medium + low
        assert len(all_selected) == 2
        assert all(a.dedup_status == "NEW" for a in all_selected)


class TestSelectArticlesEdgeCases:
    """Test edge cases: empty input, missing tiers, single tier."""

    def test_empty_input_returns_empty_tuples(self):
        """Empty input returns empty lists."""
        high, medium, low = select_articles([])
        assert high == []
        assert medium == []
        assert low == []

    def test_single_tier_high_only(self):
        """5 HIGH only -> (high=5, medium=[], low=[])."""
        articles = [_make_article("HIGH", title=f"High {i}") for i in range(5)]
        high, medium, low = select_articles(articles)
        assert len(high) == 5
        assert medium == []
        assert low == []

    def test_single_tier_medium_fills_to_cap(self):
        """0 HIGH, 20 MED, 0 LOW -> medium capped at 15."""
        articles = [_make_article("MEDIUM", title=f"Med {i}") for i in range(20)]
        high, medium, low = select_articles(articles)
        assert high == []
        assert len(medium) == 15
        assert low == []

    def test_custom_max_stories(self):
        """Custom max_stories is respected."""
        articles = [_make_article("HIGH", title=f"High {i}") for i in range(5)] + [
            _make_article("MEDIUM", title=f"Med {i}") for i in range(5)
        ]
        high, medium, low = select_articles(articles, max_stories=7)
        assert len(high) + len(medium) + len(low) <= 7

    def test_articles_with_no_priority_ignored(self):
        """Articles with empty priority are not selected."""
        articles = [
            _make_article("", "NEW", title="No priority"),
            _make_article("HIGH", "NEW", title="Has priority"),
        ]
        high, medium, low = select_articles(articles)
        all_selected = high + medium + low
        assert len(all_selected) == 1
        assert all_selected[0].title == "Has priority"
