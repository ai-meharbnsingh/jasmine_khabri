"""Tests for geographic tier classification and filtering (Phase 4 Plan 02).

Requirements: FETCH-05 (geographic filtering)
Uses dynamic curve-graded thresholds instead of fixed values.
"""

from pipeline.filters.geo_filter import (
    classify_geo_tier,
    compute_score_bands,
    filter_by_geo_tier,
)
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
# TestComputeScoreBands
# ---------------------------------------------------------------------------


class TestComputeScoreBands:
    def test_empty_scores(self) -> None:
        """Empty list returns (0, 0)."""
        assert compute_score_bands([]) == (0.0, 0.0)

    def test_identical_scores(self) -> None:
        """All same score — both thresholds equal the score (everything passes)."""
        t2, t3 = compute_score_bands([40, 40, 40])
        assert t2 == 40.0
        assert t3 == 40.0

    def test_range_30_to_90(self) -> None:
        """Scores 30-90: range=60, band=20. tier2=50, tier3=70."""
        t2, t3 = compute_score_bands([30, 50, 70, 90])
        assert t2 == 50.0  # 90 - 2*20
        assert t3 == 70.0  # 90 - 20

    def test_low_range_20_to_40(self) -> None:
        """Even low scores get meaningful thresholds. Range=20, band≈6.67."""
        t2, t3 = compute_score_bands([20, 30, 40])
        # tier2 = 40 - 2*(20/3) ≈ 26.67
        # tier3 = 40 - (20/3) ≈ 33.33
        assert round(t2, 1) == 26.7
        assert round(t3, 1) == 33.3


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
        articles = [
            _make_article("Delhi NCR expressway approved", relevance_score=10),
            _make_article("Siliguri port expansion", relevance_score=50),
        ]
        results = filter_by_geo_tier(articles)
        titles = [a.title for a in results]
        assert "Delhi NCR expressway approved" in titles

    def test_tier2_passes_when_in_top_two_thirds(self) -> None:
        """Tier 2 article with score in top 2/3 of range passes."""
        # Scores: 20, 50, 80. Range=60, band=20. tier2_threshold=40.
        articles = [
            _make_article("Delhi NCR expressway", relevance_score=80),  # tier1
            _make_article("Noida metro extension", relevance_score=50),  # tier2, 50>=40 passes
            _make_article("Siliguri housing", relevance_score=20),  # tier3
        ]
        results = filter_by_geo_tier(articles)
        titles = [a.title for a in results]
        assert "Noida metro extension" in titles

    def test_tier2_dropped_when_in_bottom_third(self) -> None:
        """Tier 2 article with lowest score in batch gets dropped."""
        # Scores: 20, 60, 90. Range=70, band≈23.3. tier2≈43.3.
        articles = [
            _make_article("Delhi NCR expressway", relevance_score=90),  # tier1
            _make_article("Noida metro extension", relevance_score=20),  # tier2, 20<43.3 dropped
            _make_article("Siliguri housing", relevance_score=60),  # tier3
        ]
        results = filter_by_geo_tier(articles)
        titles = [a.title for a in results]
        assert "Noida metro extension" not in titles

    def test_tier3_passes_when_in_top_third(self) -> None:
        """Tier 3 article with score in top 1/3 of range passes."""
        # Scores: 20, 50, 80. Range=60, band=20. tier3_threshold=60.
        articles = [
            _make_article("Delhi NCR expressway", relevance_score=20),  # tier1
            _make_article("Noida metro extension", relevance_score=50),  # tier2
            _make_article("Siliguri housing boom", relevance_score=80),  # tier3, 80>=60 passes
        ]
        results = filter_by_geo_tier(articles)
        titles = [a.title for a in results]
        assert "Siliguri housing boom" in titles

    def test_tier3_dropped_when_below_top_third(self) -> None:
        """Tier 3 article with score below top 1/3 of range dropped."""
        # Scores: 20, 50, 80. Range=60, band=20. tier3_threshold=60.
        articles = [
            _make_article("Delhi NCR expressway", relevance_score=80),  # tier1
            _make_article("Noida metro extension", relevance_score=50),  # tier2
            _make_article("Siliguri housing", relevance_score=20),  # tier3, 20<60 dropped
        ]
        results = filter_by_geo_tier(articles)
        titles = [a.title for a in results]
        assert "Siliguri housing" not in titles

    def test_geo_tier_set_on_output(self) -> None:
        """Passing article has geo_tier field populated (not 0)."""
        article = _make_article("Mumbai metro new line", relevance_score=50)
        results = filter_by_geo_tier([article])
        assert len(results) == 1
        assert results[0].geo_tier != 0

    def test_all_same_score_all_pass(self) -> None:
        """When all articles have the same score, all tiers pass (range=0)."""
        articles = [
            _make_article("Delhi NCR expressway", relevance_score=30),  # tier1
            _make_article("Noida metro extension", relevance_score=30),  # tier2
            _make_article("Siliguri housing", relevance_score=30),  # tier3
        ]
        results = filter_by_geo_tier(articles)
        assert len(results) == 3

    def test_low_scores_still_produce_results(self) -> None:
        """Even when all scores are low (20-40), dynamic bands let articles through."""
        # Range=20, band≈6.67. tier2≈26.67, tier3≈33.33.
        articles = [
            _make_article("Noida metro extension", relevance_score=35),  # tier2, 35>=26.67
            _make_article("Siliguri housing boom", relevance_score=40),  # tier3, 40>=33.33
            _make_article("Jaipur development plan", relevance_score=20),  # tier2, 20<26.67
        ]
        results = filter_by_geo_tier(articles)
        titles = [a.title for a in results]
        # Noida (35>=26.67) and Siliguri (40>=33.33) pass
        assert "Noida metro extension" in titles
        assert "Siliguri housing boom" in titles
        # Jaipur (20<26.67) dropped
        assert "Jaipur development plan" not in titles

    def test_mixed_tiers_filtered_correctly(self) -> None:
        """Mixed tier list with dynamic thresholds.

        Scores: 20, 60, 20, 90. Range=70, band≈23.3.
        tier2_threshold≈43.3, tier3_threshold≈66.7.
        """
        articles = [
            _make_article("Delhi NCR highway project", relevance_score=20),  # tier1, always passes
            _make_article("Noida elevated road", relevance_score=60),  # tier2, 60>=43.3 passes
            _make_article("Gurugram sector news", relevance_score=20),  # tier2, 20<43.3 dropped
            _make_article("Siliguri port expansion", relevance_score=90),  # tier3, 90>=66.7 passes
        ]
        results = filter_by_geo_tier(articles)
        assert len(results) == 3
        titles = [a.title for a in results]
        assert "Gurugram sector news" not in titles

    def test_empty_list_returns_empty(self) -> None:
        """Empty input returns empty list."""
        assert filter_by_geo_tier([]) == []
