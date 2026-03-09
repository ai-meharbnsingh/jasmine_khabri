"""Classifier unit tests with mocked API calls.

TDD Phase 5 Plan 02 — Tests cover:
- Batch classification with Claude primary provider
- Summary generation (writer-focused impact summaries)
- Entity extraction (location, project_name, budget_amount, authority)
- Gemini fallback on Claude failure
- Budget gate at $4.75 threshold
- Article title/summary truncation
"""

from unittest.mock import MagicMock, patch

from pipeline.schemas.ai_cost_schema import AICost
from pipeline.schemas.ai_response_schema import ArticleAnalysis, BatchClassificationResponse
from pipeline.schemas.article_schema import Article


def _make_article(**overrides):
    """Create a test article with sensible defaults."""
    defaults = {
        "title": "Metro Phase 4 approved by Cabinet",
        "url": "https://example.com/metro",
        "source": "ET Realty",
        "published_at": "2026-03-07T00:00:00Z",
        "summary": "Cabinet approves Metro Phase 4 expansion.",
        "fetched_at": "2026-03-07T01:00:00Z",
        "relevance_score": 85,
        "geo_tier": 1,
        "dedup_status": "NEW",
    }
    defaults.update(overrides)
    return Article(**defaults)


def _make_ai_cost(**overrides):
    """Create a test AICost with defaults."""
    defaults = {
        "month": "2026-03",
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cost_usd": 0.0,
        "call_count": 0,
    }
    defaults.update(overrides)
    return AICost(**defaults)


def _mock_claude_response(analyses):
    """Build a mock Claude response with parsed_output and usage."""
    batch = BatchClassificationResponse(articles=analyses)
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.parsed_output = batch
    response.usage = MagicMock()
    response.usage.input_tokens = 8500
    response.usage.output_tokens = 1500
    response.usage.cache_creation_input_tokens = 0
    response.usage.cache_read_input_tokens = 0
    return response


def _mock_gemini_response(analyses):
    """Build a mock Gemini response with text and usage_metadata."""
    batch = BatchClassificationResponse(articles=analyses)
    response = MagicMock()
    response.text = batch.model_dump_json()
    response.usage_metadata = MagicMock()
    response.usage_metadata.prompt_token_count = 8500
    response.usage_metadata.candidates_token_count = 1500
    return response


SAMPLE_ANALYSES = [
    ArticleAnalysis(
        index=0,
        priority="HIGH",
        summary=(
            "Delhi Metro Phase 4 approval unlocks 3 new corridor stories. Budget: Rs 46,000 crore."
        ),
        location="Delhi",
        project_name="Delhi Metro Phase 4",
        budget="Rs 46,000 crore",
        authority="Cabinet Committee",
    ),
    ArticleAnalysis(
        index=1,
        priority="MEDIUM",
        summary=(
            "RERA compliance deadline extension gives builders breathing room."
            " Impacts ongoing projects in Mumbai."
        ),
        location="Mumbai",
        project_name="",
        budget="",
        authority="Maharashtra RERA",
    ),
    ArticleAnalysis(
        index=2,
        priority="LOW",
        summary="Expert panel discusses housing affordability trends for 2026. General commentary.",
        location="",
        project_name="",
        budget="",
        authority="",
    ),
]


class TestBatchClassification:
    """Tests for batch classification via Claude primary provider."""

    def test_empty_articles(self):
        """Empty list returns empty list, cost unchanged."""
        from pipeline.analyzers.classifier import classify_articles

        cost = _make_ai_cost()
        result_articles, result_cost = classify_articles([], cost)
        assert result_articles == []
        assert result_cost == cost

    @patch("pipeline.analyzers.classifier.anthropic")
    def test_successful_classification(self, mock_anthropic):
        """Mock Claude response with 3 articles, verify priority/summary/entities populated."""
        from pipeline.analyzers.classifier import classify_articles

        articles = [
            _make_article(title="Metro Phase 4 approved"),
            _make_article(title="RERA deadline extended", relevance_score=70),
            _make_article(title="Housing expert opinion", relevance_score=40),
        ]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.parse.return_value = _mock_claude_response(SAMPLE_ANALYSES)

        cost = _make_ai_cost()
        result_articles, result_cost = classify_articles(articles, cost)

        assert len(result_articles) == 3
        assert result_articles[0].priority == "HIGH"
        assert result_articles[1].priority == "MEDIUM"
        assert result_articles[2].priority == "LOW"

    @patch("pipeline.analyzers.classifier.anthropic")
    def test_classification_counts_logged(self, mock_anthropic, caplog):
        """Verify HIGH/MEDIUM/LOW counts logged."""
        from pipeline.analyzers.classifier import classify_articles

        articles = [
            _make_article(title="Article 1"),
            _make_article(title="Article 2"),
            _make_article(title="Article 3"),
        ]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.parse.return_value = _mock_claude_response(SAMPLE_ANALYSES)

        cost = _make_ai_cost()
        import logging

        with caplog.at_level(logging.INFO):
            classify_articles(articles, cost)

        log_text = caplog.text
        assert "HIGH" in log_text
        assert "MEDIUM" in log_text
        assert "LOW" in log_text


class TestSummaryGeneration:
    """Tests for writer-focused impact summaries."""

    @patch("pipeline.analyzers.classifier.anthropic")
    def test_summaries_populated(self, mock_anthropic):
        """Mock response with summaries, verify each article.summary is non-empty."""
        from pipeline.analyzers.classifier import classify_articles

        articles = [
            _make_article(title="Metro Phase 4 approved"),
            _make_article(title="RERA deadline extended"),
            _make_article(title="Housing expert opinion"),
        ]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.parse.return_value = _mock_claude_response(SAMPLE_ANALYSES)

        cost = _make_ai_cost()
        result_articles, _ = classify_articles(articles, cost)

        for article in result_articles:
            assert article.summary != ""
            assert len(article.summary) > 10


class TestEntityExtraction:
    """Tests for entity extraction (location, project_name, budget_amount, authority)."""

    @patch("pipeline.analyzers.classifier.anthropic")
    def test_entities_populated(self, mock_anthropic):
        """Mock response with entities, verify location/project_name/budget_amount/authority."""
        from pipeline.analyzers.classifier import classify_articles

        articles = [
            _make_article(title="Metro Phase 4 approved"),
            _make_article(title="RERA deadline extended"),
            _make_article(title="Housing expert opinion"),
        ]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.parse.return_value = _mock_claude_response(SAMPLE_ANALYSES)

        cost = _make_ai_cost()
        result_articles, _ = classify_articles(articles, cost)

        # First article has all entities
        assert result_articles[0].location == "Delhi"
        assert result_articles[0].project_name == "Delhi Metro Phase 4"
        assert result_articles[0].budget_amount == "Rs 46,000 crore"
        assert result_articles[0].authority == "Cabinet Committee"

    @patch("pipeline.analyzers.classifier.anthropic")
    def test_missing_entities_default_empty(self, mock_anthropic):
        """Mock response with empty entity strings, verify empty strings (not None)."""
        from pipeline.analyzers.classifier import classify_articles

        articles = [
            _make_article(title="Housing expert opinion"),
        ]

        analysis_no_entities = [
            ArticleAnalysis(
                index=0,
                priority="LOW",
                summary="General commentary on housing market trends.",
                location="",
                project_name="",
                budget="",
                authority="",
            ),
        ]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.parse.return_value = _mock_claude_response(analysis_no_entities)

        cost = _make_ai_cost()
        result_articles, _ = classify_articles(articles, cost)

        assert result_articles[0].location == ""
        assert result_articles[0].project_name == ""
        assert result_articles[0].budget_amount == ""
        assert result_articles[0].authority == ""


class TestGeminiFallback:
    """Tests for Gemini fallback when Claude fails."""

    @patch("pipeline.analyzers.classifier.genai")
    @patch("pipeline.analyzers.classifier.anthropic")
    def test_claude_fails_gemini_succeeds(self, mock_anthropic, mock_genai):
        """Claude raises Exception, Gemini returns valid response."""
        from pipeline.analyzers.classifier import classify_articles

        articles = [
            _make_article(title="Metro Phase 4 approved"),
            _make_article(title="RERA deadline extended"),
            _make_article(title="Housing expert opinion"),
        ]

        # Claude fails
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.parse.side_effect = Exception("Claude API error")

        # Gemini succeeds
        mock_gemini_client = MagicMock()
        mock_genai.Client.return_value = mock_gemini_client
        mock_gemini_client.models.generate_content.return_value = _mock_gemini_response(
            SAMPLE_ANALYSES
        )

        with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}):
            cost = _make_ai_cost()
            result_articles, result_cost = classify_articles(articles, cost)

        assert len(result_articles) == 3
        assert result_articles[0].priority == "HIGH"
        assert result_articles[1].priority == "MEDIUM"
        # Cost recorded for gemini provider
        assert result_cost.call_count == 1

    @patch("pipeline.analyzers.classifier.genai")
    @patch("pipeline.analyzers.classifier.anthropic")
    def test_both_providers_fail(self, mock_anthropic, mock_genai):
        """Both Claude and Gemini raise Exception, articles get MEDIUM default."""
        from pipeline.analyzers.classifier import classify_articles

        articles = [
            _make_article(title="Metro Phase 4 approved"),
            _make_article(title="RERA deadline extended"),
        ]

        # Claude fails
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.parse.side_effect = Exception("Claude API error")

        # Gemini fails
        mock_gemini_client = MagicMock()
        mock_genai.Client.return_value = mock_gemini_client
        mock_gemini_client.models.generate_content.side_effect = Exception("Gemini API error")

        with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}):
            cost = _make_ai_cost()
            result_articles, result_cost = classify_articles(articles, cost)

        assert len(result_articles) == 2
        for article in result_articles:
            assert article.priority == "MEDIUM"
            assert article.summary == ""
            assert article.location == ""
            assert article.project_name == ""
            assert article.budget_amount == ""
            assert article.authority == ""
        # No API calls succeeded, cost unchanged
        assert result_cost.call_count == 0

    @patch("pipeline.analyzers.classifier.anthropic")
    def test_gemini_no_api_key(self, mock_anthropic):
        """GOOGLE_API_KEY absent, Gemini fallback returns None."""
        from pipeline.analyzers.classifier import classify_articles

        articles = [_make_article(title="Test article")]

        # Claude fails
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.parse.side_effect = Exception("Claude API error")

        # No GOOGLE_API_KEY in env
        with patch.dict("os.environ", {}, clear=False):
            # Remove GOOGLE_API_KEY if set
            import os

            env_backup = os.environ.pop("GOOGLE_API_KEY", None)
            try:
                cost = _make_ai_cost()
                result_articles, result_cost = classify_articles(articles, cost)
            finally:
                if env_backup is not None:
                    os.environ["GOOGLE_API_KEY"] = env_backup

        # Should fall through to MEDIUM default
        assert result_articles[0].priority == "MEDIUM"
        assert result_cost.call_count == 0


class TestBudgetGate:
    """Tests for budget gate behavior."""

    @patch("pipeline.analyzers.classifier.anthropic")
    def test_budget_exceeded_skips_ai(self, mock_anthropic):
        """Cost at $4.75, no API calls made, articles get dynamic keyword-based priority.

        Scores: 85, 65, 40. Range=45, band=15.
        HIGH >= 70, MEDIUM >= 55, LOW < 55.
        """
        from pipeline.analyzers.classifier import classify_articles

        articles = [
            _make_article(title="Metro Phase 4 approved", relevance_score=85),
            _make_article(title="RERA deadline extended", relevance_score=65),
            _make_article(title="Housing commentary", relevance_score=40),
        ]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        cost = _make_ai_cost(total_cost_usd=4.75)
        result_articles, result_cost = classify_articles(articles, cost)

        # No API call should be made
        mock_client.messages.parse.assert_not_called()

        # Dynamic bands: range=45, band=15. HIGH>=70, MEDIUM>=55.
        assert result_articles[0].priority == "HIGH"  # 85 >= 70
        assert result_articles[1].priority == "MEDIUM"  # 65 >= 55
        assert result_articles[2].priority == "LOW"  # 40 < 55

        # Cost unchanged
        assert result_cost == cost

    @patch("pipeline.analyzers.classifier.anthropic")
    def test_budget_warning_proceeds(self, mock_anthropic):
        """Cost at $4.00, API call still made."""
        from pipeline.analyzers.classifier import classify_articles

        articles = [_make_article(title="Metro Phase 4 approved")]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.parse.return_value = _mock_claude_response([SAMPLE_ANALYSES[0]])

        cost = _make_ai_cost(total_cost_usd=4.00)
        result_articles, result_cost = classify_articles(articles, cost)

        # API call WAS made
        mock_client.messages.parse.assert_called_once()
        assert result_articles[0].priority == "HIGH"

    @patch("pipeline.analyzers.classifier.anthropic")
    def test_cost_recorded_after_call(self, mock_anthropic):
        """Verify ai_cost.call_count incremented and total_cost_usd increased."""
        from pipeline.analyzers.classifier import classify_articles

        articles = [_make_article(title="Metro Phase 4 approved")]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.parse.return_value = _mock_claude_response([SAMPLE_ANALYSES[0]])

        cost = _make_ai_cost()
        _, result_cost = classify_articles(articles, cost)

        assert result_cost.call_count == 1
        assert result_cost.total_cost_usd > 0
        assert result_cost.total_input_tokens > 0
        assert result_cost.total_output_tokens > 0


class TestArticleTruncation:
    """Tests for article title/summary truncation."""

    def test_long_title_truncated(self):
        """Article with 300-char title, verify articles_text has truncated version."""
        from pipeline.analyzers.classifier import build_articles_text

        long_title = "A" * 300
        article = _make_article(title=long_title)
        text = build_articles_text([article])

        # Title should be truncated to 200 chars
        assert "A" * 200 in text
        assert "A" * 201 not in text

    def test_long_summary_truncated(self):
        """Article with 1000-char summary, verify truncation at 500."""
        from pipeline.analyzers.classifier import build_articles_text

        long_summary = "B" * 1000
        article = _make_article(summary=long_summary)
        text = build_articles_text([article])

        # Summary should be truncated to 500 chars
        assert "B" * 500 in text
        assert "B" * 501 not in text
