"""Tests for relevance scoring and exclusion filtering (Phase 4 Plan 01).

Requirements: FETCH-03 (relevance scoring), FETCH-04 (exclusion filtering)
"""

from pathlib import Path

import pytest

from pipeline.filters.relevance_filter import filter_by_relevance, score_article
from pipeline.schemas.article_schema import Article
from pipeline.schemas.keywords_schema import KeywordsConfig
from pipeline.utils.loader import load_keywords

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_article(title: str, summary: str = "", source: str = "Test") -> Article:
    """Return a minimal Article with dummy non-schema fields."""
    return Article(
        title=title,
        url=f"https://example.com/{title.replace(' ', '-').lower()[:40]}",
        source=source,
        published_at="2026-02-28T00:00:00Z",
        summary=summary,
        fetched_at="2026-02-28T08:00:00Z",
    )


@pytest.fixture
def real_keywords(data_dir: Path) -> KeywordsConfig:
    """Load real keywords.yaml from data directory."""
    return load_keywords(data_dir / "keywords.yaml")


@pytest.fixture
def minimal_keywords() -> KeywordsConfig:
    """Minimal KeywordsConfig for unit tests — avoids disk access."""
    return KeywordsConfig(
        categories={
            "infra": {
                "active": True,
                "keywords": ["metro", "airport", "highway"],
            }
        },
        exclusions=["obituary", "gossip"],
    )


# ---------------------------------------------------------------------------
# TestScoreArticle (FETCH-03)
# ---------------------------------------------------------------------------


class TestScoreArticle:
    def test_delhi_metro_passes_threshold(self, real_keywords: KeywordsConfig) -> None:
        """Article with 'Delhi Metro Phase 4' in title should score >= 40."""
        article = _make_article("Delhi Metro Phase 4 construction begins")
        passes, score = score_article(article, real_keywords)
        assert passes is True, "Delhi Metro article should pass exclusion check"
        assert score >= 40, f"Expected score >= 40, got {score}"

    def test_title_match_scores_higher_than_body(self, minimal_keywords: KeywordsConfig) -> None:
        """Title keyword match gives 20 pts; description-only match gives 10 pts."""
        title_article = _make_article("metro expansion announced")
        body_article = _make_article("New transit project", summary="metro expansion")

        _, title_score = score_article(title_article, minimal_keywords)
        _, body_score = score_article(body_article, minimal_keywords)

        assert title_score == 20, f"Expected title match = 20 pts, got {title_score}"
        assert body_score == 10, f"Expected body match = 10 pts, got {body_score}"

    def test_no_keyword_match_scores_zero(self, minimal_keywords: KeywordsConfig) -> None:
        """Article with no relevant keywords scores 0."""
        article = _make_article("Weather forecast for tomorrow")
        passes, score = score_article(article, minimal_keywords)
        assert passes is True  # no exclusion keywords
        assert score == 0

    def test_multiple_keywords_accumulate(self, minimal_keywords: KeywordsConfig) -> None:
        """Article with both 'metro' and 'airport' in title accumulates both scores."""
        article = _make_article("New metro and airport connectivity project")
        _, score = score_article(article, minimal_keywords)
        # 'metro' in title = 20, 'airport' in title = 20 → total = 40
        assert score == 40, f"Expected score = 40, got {score}"

    def test_keyword_counted_once_not_twice(self, minimal_keywords: KeywordsConfig) -> None:
        """A keyword in both title and summary is only counted once (title wins)."""
        article = _make_article("metro expansion", summary="metro routes announced")
        _, score = score_article(article, minimal_keywords)
        # 'metro' in title = 20 only (not also 10 from body)
        assert score == 20, f"Expected score = 20, got {score}"


# ---------------------------------------------------------------------------
# TestExclusionFilter (FETCH-04)
# ---------------------------------------------------------------------------


class TestExclusionFilter:
    def test_obituary_excluded(self, minimal_keywords: KeywordsConfig) -> None:
        """Article with 'obituary' in title returns (False, 0)."""
        article = _make_article("obituary of a famous developer")
        passes, score = score_article(article, minimal_keywords)
        assert passes is False
        assert score == 0

    def test_gossip_in_summary_excluded(self, minimal_keywords: KeywordsConfig) -> None:
        """Article with 'gossip' in summary returns (False, 0)."""
        article = _make_article("News roundup", summary="gossip about real estate")
        passes, score = score_article(article, minimal_keywords)
        assert passes is False
        assert score == 0

    def test_exclusion_overrides_high_score(self, minimal_keywords: KeywordsConfig) -> None:
        """Article with 'metro obituary' is excluded even though metro is a keyword."""
        article = _make_article("Delhi metro obituary of project head")
        passes, score = score_article(article, minimal_keywords)
        assert passes is False
        assert score == 0


# ---------------------------------------------------------------------------
# TestFilterByRelevance
# ---------------------------------------------------------------------------


class TestFilterByRelevance:
    def test_filters_below_threshold(self, minimal_keywords: KeywordsConfig) -> None:
        """Only articles at or above threshold pass through."""
        articles = [
            _make_article("metro expansion project"),  # score 20, below 40
            _make_article("metro and airport project"),  # score 40, at threshold
            _make_article("unrelated news today"),  # score 0
        ]
        results = filter_by_relevance(articles, minimal_keywords, threshold=40)
        assert len(results) == 1
        assert results[0].title == "metro and airport project"

    def test_relevance_score_set_on_passing_article(self, minimal_keywords: KeywordsConfig) -> None:
        """Passing article has relevance_score > 0 on the returned Article instance."""
        articles = [_make_article("metro and airport project")]
        results = filter_by_relevance(articles, minimal_keywords, threshold=40)
        assert len(results) == 1
        assert results[0].relevance_score > 0

    def test_excluded_article_not_in_results(self, minimal_keywords: KeywordsConfig) -> None:
        """Article containing exclusion keyword is absent from results."""
        articles = [
            _make_article("metro and airport project"),  # passes
            _make_article("metro obituary column"),  # excluded
        ]
        results = filter_by_relevance(articles, minimal_keywords, threshold=40)
        titles = [a.title for a in results]
        assert "metro obituary column" not in titles

    def test_empty_list_returns_empty(self, minimal_keywords: KeywordsConfig) -> None:
        """Empty input list produces empty output."""
        results = filter_by_relevance([], minimal_keywords)
        assert results == []

    def test_original_article_unchanged(self, minimal_keywords: KeywordsConfig) -> None:
        """Original article object relevance_score is not mutated — model_copy used."""
        original = _make_article("metro and airport project")
        assert original.relevance_score == 0  # default
        results = filter_by_relevance([original], minimal_keywords, threshold=40)
        assert original.relevance_score == 0  # unchanged
        assert results[0].relevance_score > 0  # new copy has score
