"""Tests for pipeline entrypoint (src/pipeline/main.py).

Tests cover:
- run() executes without raising an exception
- run() logs START and END markers at INFO level
- run() calls deliver_articles after AI classification
"""

import logging
from unittest.mock import patch

from pipeline.main import run


class TestPipelineMain:
    """Tests for the pipeline run() entrypoint."""

    def test_run_exits_zero(self):
        """run() must complete without raising any exception."""
        run()  # Should not raise

    def test_run_logs_start_and_end(self, caplog):
        """run() must emit START and END log lines at INFO level."""
        with caplog.at_level(logging.INFO):
            run()

        assert "Khabri pipeline START" in caplog.text
        assert "Khabri pipeline END" in caplog.text

    def test_run_calls_deliver_articles(self, caplog):
        """run() must call deliver_articles after AI classification."""
        with (
            patch("pipeline.main.deliver_articles", return_value=0) as mock_deliver,
            caplog.at_level(logging.INFO),
        ):
            run()

        mock_deliver.assert_called_once()
        # First arg should be the classified articles list
        args = mock_deliver.call_args
        assert isinstance(args[0][0], list)
        assert "Telegram delivery complete" in caplog.text
