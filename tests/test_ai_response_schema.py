"""Schema validation tests for AI response models, AICost, and Article extensions.

TDD Phase 5 Plan 01 — RED phase tests written before implementation.
Tests cover:
- ArticleAnalysis model validation (priority, summary, location, etc.)
- BatchClassificationResponse validation and JSON round-trip
- AICost model validation and defaults
- Article backward compatibility with new AI-populated fields
"""

import pytest
from pydantic import ValidationError


class TestArticleAnalysis:
    """Tests for ArticleAnalysis Pydantic model."""

    def test_valid_article_analysis(self):
        """All fields populated — validates OK."""
        from pipeline.schemas.ai_response_schema import ArticleAnalysis

        analysis = ArticleAnalysis(
            index=0,
            priority="HIGH",
            summary="Major metro expansion in Mumbai",
            location="Mumbai",
            project_name="Mumbai Metro Phase 3",
            budget="5000 crore",
            authority="MMRDA",
        )
        assert analysis.index == 0
        assert analysis.priority == "HIGH"
        assert analysis.summary == "Major metro expansion in Mumbai"
        assert analysis.location == "Mumbai"
        assert analysis.project_name == "Mumbai Metro Phase 3"
        assert analysis.budget == "5000 crore"
        assert analysis.authority == "MMRDA"

    def test_priority_accepts_high_medium_low(self):
        """Priority accepts exactly HIGH, MEDIUM, LOW."""
        from pipeline.schemas.ai_response_schema import ArticleAnalysis

        for p in ("HIGH", "MEDIUM", "LOW"):
            a = ArticleAnalysis(index=0, priority=p, summary="test")
            assert a.priority == p

    def test_priority_rejects_invalid(self):
        """Priority rejects values outside HIGH/MEDIUM/LOW."""
        from pipeline.schemas.ai_response_schema import ArticleAnalysis

        with pytest.raises(ValidationError):
            ArticleAnalysis(index=0, priority="CRITICAL", summary="test")
        with pytest.raises(ValidationError):
            ArticleAnalysis(index=0, priority="low", summary="test")
        with pytest.raises(ValidationError):
            ArticleAnalysis(index=0, priority="", summary="test")

    def test_optional_fields_default_empty(self):
        """location, project_name, budget, authority default to empty string."""
        from pipeline.schemas.ai_response_schema import ArticleAnalysis

        a = ArticleAnalysis(index=1, priority="LOW", summary="test summary")
        assert a.location == ""
        assert a.project_name == ""
        assert a.budget == ""
        assert a.authority == ""

    def test_index_is_required_int(self):
        """index must be provided as an int."""
        from pipeline.schemas.ai_response_schema import ArticleAnalysis

        with pytest.raises(ValidationError):
            ArticleAnalysis(priority="HIGH", summary="test")  # missing index

    def test_summary_is_required(self):
        """summary is a required field."""
        from pipeline.schemas.ai_response_schema import ArticleAnalysis

        with pytest.raises(ValidationError):
            ArticleAnalysis(index=0, priority="HIGH")  # missing summary


class TestBatchClassificationResponse:
    """Tests for BatchClassificationResponse Pydantic model."""

    def test_valid_batch_response(self):
        """Batch with multiple articles validates OK."""
        from pipeline.schemas.ai_response_schema import (
            ArticleAnalysis,
            BatchClassificationResponse,
        )

        batch = BatchClassificationResponse(
            articles=[
                ArticleAnalysis(index=0, priority="HIGH", summary="Metro expansion"),
                ArticleAnalysis(index=1, priority="LOW", summary="Minor update"),
            ]
        )
        assert len(batch.articles) == 2
        assert batch.articles[0].priority == "HIGH"
        assert batch.articles[1].priority == "LOW"

    def test_empty_batch(self):
        """Empty articles list is valid."""
        from pipeline.schemas.ai_response_schema import BatchClassificationResponse

        batch = BatchClassificationResponse(articles=[])
        assert batch.articles == []

    def test_json_roundtrip(self):
        """model_dump_json -> model_validate_json preserves all fields."""
        from pipeline.schemas.ai_response_schema import (
            ArticleAnalysis,
            BatchClassificationResponse,
        )

        original = BatchClassificationResponse(
            articles=[
                ArticleAnalysis(
                    index=0,
                    priority="HIGH",
                    summary="RERA reform",
                    location="Delhi",
                    project_name="RERA Phase 2",
                    budget="200 crore",
                    authority="DPIIT",
                ),
                ArticleAnalysis(
                    index=1,
                    priority="MEDIUM",
                    summary="Highway update",
                ),
            ]
        )
        json_str = original.model_dump_json()
        restored = BatchClassificationResponse.model_validate_json(json_str)
        assert len(restored.articles) == 2
        assert restored.articles[0].priority == "HIGH"
        assert restored.articles[0].location == "Delhi"
        assert restored.articles[1].priority == "MEDIUM"
        assert restored.articles[1].location == ""


class TestAICost:
    """Tests for AICost Pydantic model."""

    def test_valid_ai_cost(self):
        """All fields populated — validates OK."""
        from pipeline.schemas.ai_cost_schema import AICost

        cost = AICost(
            month="2026-03",
            total_input_tokens=1000,
            total_output_tokens=500,
            total_cost_usd=0.0075,
            call_count=2,
        )
        assert cost.month == "2026-03"
        assert cost.total_input_tokens == 1000
        assert cost.total_output_tokens == 500
        assert cost.total_cost_usd == 0.0075
        assert cost.call_count == 2

    def test_defaults_all_numeric_to_zero(self):
        """All numeric fields default to 0."""
        from pipeline.schemas.ai_cost_schema import AICost

        cost = AICost(month="2026-03")
        assert cost.total_input_tokens == 0
        assert cost.total_output_tokens == 0
        assert cost.total_cost_usd == 0.0
        assert cost.call_count == 0

    def test_month_is_required(self):
        """month field has no default — must be provided."""
        from pipeline.schemas.ai_cost_schema import AICost

        with pytest.raises(ValidationError):
            AICost()  # missing month

    def test_seed_json_loads(self):
        """AICost can parse the seed ai_cost.json format."""
        from pipeline.schemas.ai_cost_schema import AICost

        seed = {
            "month": "1970-01",
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost_usd": 0.0,
            "call_count": 0,
        }
        cost = AICost.model_validate(seed)
        assert cost.month == "1970-01"
        assert cost.total_cost_usd == 0.0


class TestArticleAIExtensions:
    """Tests that Article model has new AI-populated fields with correct defaults."""

    def test_article_has_priority_field(self):
        """Article has optional priority field defaulting to empty string."""
        from pipeline.schemas.article_schema import Article

        article = Article(
            title="Test",
            url="https://example.com",
            source="Test",
            published_at="2026-03-07T00:00:00+00:00",
            fetched_at="2026-03-07T00:00:00+00:00",
        )
        assert article.priority == ""

    def test_article_priority_accepts_valid_values(self):
        """Article priority accepts HIGH, MEDIUM, LOW, and empty string."""
        from pipeline.schemas.article_schema import Article

        for p in ("HIGH", "MEDIUM", "LOW", ""):
            a = Article(
                title="Test",
                url="https://example.com",
                source="Test",
                published_at="2026-03-07T00:00:00+00:00",
                fetched_at="2026-03-07T00:00:00+00:00",
                priority=p,
            )
            assert a.priority == p

    def test_article_has_location_field(self):
        """Article has optional location field defaulting to empty string."""
        from pipeline.schemas.article_schema import Article

        article = Article(
            title="Test",
            url="https://example.com",
            source="Test",
            published_at="2026-03-07T00:00:00+00:00",
            fetched_at="2026-03-07T00:00:00+00:00",
        )
        assert article.location == ""

    def test_article_has_project_name_field(self):
        """Article has optional project_name field defaulting to empty string."""
        from pipeline.schemas.article_schema import Article

        article = Article(
            title="Test",
            url="https://example.com",
            source="Test",
            published_at="2026-03-07T00:00:00+00:00",
            fetched_at="2026-03-07T00:00:00+00:00",
        )
        assert article.project_name == ""

    def test_article_has_budget_amount_field(self):
        """Article has optional budget_amount field defaulting to empty string."""
        from pipeline.schemas.article_schema import Article

        article = Article(
            title="Test",
            url="https://example.com",
            source="Test",
            published_at="2026-03-07T00:00:00+00:00",
            fetched_at="2026-03-07T00:00:00+00:00",
        )
        assert article.budget_amount == ""

    def test_article_has_authority_field(self):
        """Article has optional authority field defaulting to empty string."""
        from pipeline.schemas.article_schema import Article

        article = Article(
            title="Test",
            url="https://example.com",
            source="Test",
            published_at="2026-03-07T00:00:00+00:00",
            fetched_at="2026-03-07T00:00:00+00:00",
        )
        assert article.authority == ""

    def test_existing_constructors_unchanged(self):
        """Phase 3/4 Article constructors still work — all new fields default."""
        from pipeline.schemas.article_schema import Article

        # Phase 3 minimal constructor (no filter fields)
        article = Article(
            title="Mumbai Metro Phase 3 Opens",
            url="https://example.com/metro",
            source="ET Realty",
            published_at="2026-02-27T10:00:00+00:00",
            summary="",
            fetched_at="2026-02-27T10:05:00+00:00",
        )
        assert article.priority == ""
        assert article.location == ""
        assert article.project_name == ""
        assert article.budget_amount == ""
        assert article.authority == ""

        # Phase 4 constructor (with filter fields)
        article2 = Article(
            title="RERA Update",
            url="https://example.com/rera",
            source="Moneycontrol",
            published_at="2026-02-27T08:00:00+00:00",
            fetched_at="2026-02-27T08:01:00+00:00",
            relevance_score=85,
            geo_tier=1,
            dedup_status="NEW",
        )
        assert article2.relevance_score == 85
        assert article2.priority == ""
        assert article2.location == ""
