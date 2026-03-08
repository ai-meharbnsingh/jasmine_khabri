"""Tests for pipeline entrypoint (src/pipeline/main.py).

Tests cover:
- run() executes without raising an exception
- run() logs START and END markers at INFO level
- run() calls deliver_articles after AI classification
- Phase 11-02: run() increments monthly_deliver_runs and est_actions_minutes
"""

import logging
from unittest.mock import patch

from pipeline.main import run
from pipeline.schemas.ai_cost_schema import AICost
from pipeline.schemas.pipeline_status_schema import PipelineStatus


class TestPipelineMain:
    """Tests for the pipeline run() entrypoint."""

    def test_run_exits_zero(self):
        """run() must complete without raising any exception."""
        with (
            patch("pipeline.main.fetch_all_rss", return_value=([], [])),
            patch("pipeline.main.classify_articles", return_value=([], AICost(month="2026-01"))),
            patch("pipeline.main.deliver_articles", return_value=0),
            patch("pipeline.main.deliver_email", return_value=0),
        ):
            run()  # Should not raise

    def test_run_logs_start_and_end(self, caplog):
        """run() must emit START and END log lines at INFO level."""
        with (
            patch("pipeline.main.fetch_all_rss", return_value=([], [])),
            patch("pipeline.main.classify_articles", return_value=([], AICost(month="2026-01"))),
            patch("pipeline.main.deliver_articles", return_value=0),
            patch("pipeline.main.deliver_email", return_value=0),
            caplog.at_level(logging.INFO),
        ):
            run()

        assert "Khabri pipeline START" in caplog.text
        assert "Khabri pipeline END" in caplog.text

    def test_run_calls_deliver_articles(self, caplog):
        """run() must call deliver_articles after AI classification."""
        with (
            patch("pipeline.main.fetch_all_rss", return_value=([], [])),
            patch("pipeline.main.classify_articles", return_value=([], AICost(month="2026-01"))),
            patch("pipeline.main.deliver_articles", return_value=0) as mock_deliver,
            patch("pipeline.main.deliver_email", return_value=0),
            caplog.at_level(logging.INFO),
        ):
            run()

        mock_deliver.assert_called_once()
        # First arg should be the classified articles list
        args = mock_deliver.call_args
        assert isinstance(args[0][0], list)
        assert "Telegram delivery complete" in caplog.text


class TestRunCounter:
    """Tests that main.py increments monthly_deliver_runs and est_actions_minutes."""

    def test_deliver_run_counter_increments(self, tmp_path):
        """After run(), pipeline_status.json has monthly_deliver_runs incremented by 1."""
        # Seed with existing usage data
        from datetime import UTC, datetime

        current_month = datetime.now(UTC).strftime("%Y-%m")
        seed = PipelineStatus(
            usage_month=current_month,
            monthly_deliver_runs=3,
            monthly_breaking_runs=10,
            monthly_breaking_alerts=2,
            est_actions_minutes=24.0,
        )
        (tmp_path / "pipeline_status.json").write_text(seed.model_dump_json(indent=2))

        with (
            patch("pipeline.main.load_pipeline_status") as mock_load,
            patch("pipeline.main.save_pipeline_status") as mock_save,
            patch("pipeline.main.fetch_all_rss", return_value=([], [])),
            patch("pipeline.main.classify_articles", return_value=([], AICost(month="2026-01"))),
            patch("pipeline.main.deliver_articles", return_value=0),
            patch("pipeline.main.deliver_email", return_value=0),
        ):
            mock_load.return_value = seed
            run()
            # save_pipeline_status should have been called
            mock_save.assert_called()
            saved_status = mock_save.call_args[0][0]
            assert saved_status.monthly_deliver_runs == 4
            assert saved_status.est_actions_minutes == 27.0  # 24.0 + 3.0
            # Preserve breaking counters
            assert saved_status.monthly_breaking_runs == 10
            assert saved_status.monthly_breaking_alerts == 2
