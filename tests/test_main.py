"""Tests for pipeline entrypoint (src/pipeline/main.py).

Tests cover:
- run() executes without raising an exception
- run() logs START and END markers at INFO level
"""

import logging

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
