"""Tests for geographic tier classification and filtering (Phase 4 Plan 02).

Requirements: FETCH-05 (geographic filtering)
"""

from pipeline.filters.geo_filter import classify_geo_tier, filter_by_geo_tier
from pipeline.schemas.article_schema import Article

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_article(
    title: str,
    source: str = "Test",
    summary: str = "",
    relevance_score: int = 0,
) -> Article:
    """Return a minimal Article with dummy non-schema fields."""
    return Article(
        title=title,
        url=f"https://example.com/{title.replace(' ', '-').lower()[:40]}",
        source=source,
        published_at="2026-02-28T00:00:00Z",
        summary=summary,
        fetched_at="2026-02-28T08:00:00Z",
        relevance_score=relevance_score,
    )


# ---------------------------------------------------------------------------
# TestClassifyGeoTier
# ---------------------------------------------------------------------------


class TestClassifyGeoTier:
    def test_tier1_delhi_ncr(self) -> None:
        """Article with 'Delhi NCR' in title classified as Tier 1."""
        article = _make_article("New metro line in Delhi NCR announced")
        assert classify_geo_tier(article) == 1

    def test_tier1_mumbai(self) -> None:
        """Article with 'Mumbai' in title classified as Tier 1."""
        article = _make_article("Mumbai coastal road project update")
        assert classify_geo_tier(article) == 1

    def test_tier1_bangalore_variant(self) -> None:
        """Article with 'Bengaluru' in title classified as Tier 1 (variant spelling)."""
        article = _make_article("Bengaluru metro phase 3 approved")
        assert classify_geo_tier(article) == 1

    def test_tier2_noida(self) -> None:
        """Article with 'Noida' in title classified as Tier 2."""
        article = _make_article("Noida expressway widening project")
        assert classify_geo_tier(article) == 2

    def test_tier2_gurugram(self) -> None:
        """Article with 'Gurugram' in title classified as Tier 2."""
        article = _make_article("Gurugram rapid metro expansion plan")
        assert classify_geo_tier(article) == 2

    def test_tier2_gurgaon_variant(self) -> None:
        """Article with 'Gurgaon' in title classified as Tier 2 (variant spelling)."""
        article = _make_article("Gurgaon flyover construction begins")
        assert classify_geo_tier(article) == 2

    def test_tier3_unknown_city(self) -> None:
        """Article with 'Siliguri' (not in any tier list) classified as Tier 3."""
        article = _make_article("Siliguri real estate prices rise")
        assert classify_geo_tier(article) == 3

    def test_no_city_non_gov_defaults_tier3(self) -> None:
        """Article with no city and non-government source defaults to Tier 3."""
        article = _make_article("Real estate investment trends Q1 2026", source="ET Realty")
        assert classify_geo_tier(article) == 3

    def test_national_scope_gov_mohua(self) -> None:
        """Article with no city, source 'MOHUA' classified as Tier 1 (national scope)."""
        article = _make_article("New housing policy announced", source="MOHUA")
        assert classify_geo_tier(article) == 1

    def test_national_scope_gov_nhai(self) -> None:
        """Article with no city, source 'NHAI' classified as Tier 1 (national scope)."""
        article = _make_article("Highway expansion budget doubled", source="NHAI")
        assert classify_geo_tier(article) == 1

    def test_national_scope_gov_aai(self) -> None:
        """Article with no city, source 'AAI' classified as Tier 1 (national scope)."""
        article = _make_article("New terminal construction approved", source="AAI")
        assert classify_geo_tier(article) == 1

    def test_national_scope_gov_smart_cities(self) -> None:
        """Article with no city, source 'Smart Cities' classified as Tier 1."""
        article = _make_article("Smart infrastructure rollout nationwide", source="Smart Cities")
        assert classify_geo_tier(article) == 1

    def test_tier1_in_summary(self) -> None:
        """Article with 'Hyderabad' in summary (not title) classified as Tier 1."""
        article = _make_article(
            "Major real estate project unveiled",
            summary="The project is located in Hyderabad's western corridor",
        )
        assert classify_geo_tier(article) == 1


# ---------------------------------------------------------------------------
# TestFilterByGeoTier
# ---------------------------------------------------------------------------


class TestFilterByGeoTier:
    def test_tier1_always_passes(self) -> None:
        """Tier 1 article passes regardless of low relevance score."""
        article = _make_article("Delhi NCR expressway approved", relevance_score=10)
        results = filter_by_geo_tier([article])
        assert len(results) == 1

    def test_tier2_passes_high_score(self) -> None:
        """Tier 2 article passes when relevance_score >= 30."""
        article = _make_article("Noida metro extension", relevance_score=30)
        results = filter_by_geo_tier([article])
        assert len(results) == 1

    def test_tier2_fails_low_score(self) -> None:
        """Tier 2 article dropped when relevance_score < 30."""
        article = _make_article("Noida sector development", relevance_score=20)
        results = filter_by_geo_tier([article])
        assert len(results) == 0

    def test_tier3_passes_high_score(self) -> None:
        """Tier 3 article passes when relevance_score >= 50."""
        article = _make_article("Siliguri real estate boom", relevance_score=50)
        results = filter_by_geo_tier([article])
        assert len(results) == 1

    def test_tier3_fails_below_50(self) -> None:
        """Tier 3 article dropped when relevance_score < 50."""
        article = _make_article("Siliguri housing project", relevance_score=40)
        results = filter_by_geo_tier([article])
        assert len(results) == 0

    def test_geo_tier_set_on_output(self) -> None:
        """Passing article has geo_tier field populated (not 0)."""
        article = _make_article("Mumbai metro new line", relevance_score=50)
        results = filter_by_geo_tier([article])
        assert len(results) == 1
        assert results[0].geo_tier != 0

    def test_mixed_tiers_filtered_correctly(self) -> None:
        """Mixed tier list: tier1/score20, tier2/score60, tier2/score20, tier3/score90.

        Only 3 should pass: tier1 always passes, tier2 score60 passes (>=30),
        tier2 score20 dropped (<30), tier3 score90 passes (>=50).
        """
        articles = [
            _make_article("Delhi NCR highway project", relevance_score=20),  # tier1, passes
            _make_article("Noida elevated road", relevance_score=60),  # tier2, passes
            _make_article("Gurugram sector news", relevance_score=20),  # tier2, dropped
            _make_article("Siliguri port expansion", relevance_score=90),  # tier3, passes
        ]
        results = filter_by_geo_tier(articles)
        assert len(results) == 3
        titles = [a.title for a in results]
        assert "Gurugram sector news" not in titles
