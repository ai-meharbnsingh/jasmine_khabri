"""PipelineStatus schema and loader/saver unit tests.

TDD Phase 8 Plan 01 — RED phase tests written before implementation.
Tests cover:
- PipelineStatus model defaults
- PipelineStatus model with populated fields
- load_pipeline_status from missing file
- load_pipeline_status from empty file
- load_pipeline_status from valid JSON
- save_pipeline_status writes correct format
- Round-trip: save then load returns equivalent model
"""

import json

import pytest

from pipeline.schemas.pipeline_status_schema import PipelineStatus


class TestPipelineStatusDefaults:
    """Tests for PipelineStatus model default values."""

    def test_all_defaults(self):
        """PipelineStatus with no args uses all defaults."""
        status = PipelineStatus()
        assert status.last_run_utc == ""
        assert status.articles_fetched == 0
        assert status.articles_delivered == 0
        assert status.telegram_success == 0
        assert status.telegram_failures == 0
        assert status.email_success == 0
        assert status.sources_active == 0
        assert status.run_duration_seconds == 0.0


class TestPipelineStatusPopulated:
    """Tests for PipelineStatus model with populated fields."""

    def test_with_values(self):
        """PipelineStatus validates with all fields set."""
        status = PipelineStatus(
            last_run_utc="2026-03-07T11:00:00Z",
            articles_fetched=25,
            articles_delivered=12,
            telegram_success=10,
            telegram_failures=2,
            email_success=3,
            sources_active=5,
            run_duration_seconds=8.3,
        )
        assert status.last_run_utc == "2026-03-07T11:00:00Z"
        assert status.articles_fetched == 25
        assert status.articles_delivered == 12
        assert status.telegram_success == 10
        assert status.telegram_failures == 2
        assert status.email_success == 3
        assert status.sources_active == 5
        assert status.run_duration_seconds == 8.3


class TestLoadPipelineStatus:
    """Tests for load_pipeline_status from loader.py."""

    def test_missing_file_returns_defaults(self, tmp_path):
        """Returns default PipelineStatus when file does not exist."""
        from pipeline.utils.loader import load_pipeline_status

        result = load_pipeline_status(str(tmp_path / "nonexistent.json"))
        assert result.last_run_utc == ""
        assert result.articles_fetched == 0
        assert result.run_duration_seconds == 0.0

    def test_empty_file_returns_defaults(self, tmp_path):
        """Returns default PipelineStatus when file is empty."""
        from pipeline.utils.loader import load_pipeline_status

        p = tmp_path / "status.json"
        p.write_text("")
        result = load_pipeline_status(str(p))
        assert result.last_run_utc == ""
        assert result.articles_fetched == 0

    def test_valid_json_loads(self, tmp_path):
        """Parses valid JSON into PipelineStatus."""
        from pipeline.utils.loader import load_pipeline_status

        data = {
            "last_run_utc": "2026-03-07T11:00:00Z",
            "articles_fetched": 15,
            "articles_delivered": 8,
            "telegram_success": 6,
            "telegram_failures": 1,
            "email_success": 2,
            "sources_active": 4,
            "run_duration_seconds": 5.2,
        }
        p = tmp_path / "status.json"
        p.write_text(json.dumps(data))

        result = load_pipeline_status(str(p))
        assert result.last_run_utc == "2026-03-07T11:00:00Z"
        assert result.articles_fetched == 15
        assert result.articles_delivered == 8
        assert result.telegram_success == 6
        assert result.telegram_failures == 1
        assert result.email_success == 2
        assert result.sources_active == 4
        assert result.run_duration_seconds == 5.2


class TestSavePipelineStatus:
    """Tests for save_pipeline_status from loader.py."""

    def test_writes_json_with_indent_and_newline(self, tmp_path):
        """save_pipeline_status writes JSON with indent=2 and trailing newline."""
        from pipeline.utils.loader import save_pipeline_status

        status = PipelineStatus(
            last_run_utc="2026-03-07T11:00:00Z",
            articles_fetched=10,
            run_duration_seconds=3.5,
        )
        p = tmp_path / "status.json"
        save_pipeline_status(status, str(p))

        text = p.read_text()
        assert text.endswith("\n")
        parsed = json.loads(text)
        assert parsed["last_run_utc"] == "2026-03-07T11:00:00Z"
        assert parsed["articles_fetched"] == 10
        assert parsed["run_duration_seconds"] == 3.5


class TestPipelineStatusRoundTrip:
    """Tests for round-trip save then load equivalence."""

    def test_roundtrip(self, tmp_path):
        """save then load returns equivalent model."""
        from pipeline.utils.loader import load_pipeline_status, save_pipeline_status

        original = PipelineStatus(
            last_run_utc="2026-03-07T12:00:00Z",
            articles_fetched=20,
            articles_delivered=15,
            telegram_success=12,
            telegram_failures=1,
            email_success=3,
            sources_active=6,
            run_duration_seconds=7.8,
        )
        p = tmp_path / "status.json"
        save_pipeline_status(original, str(p))

        restored = load_pipeline_status(str(p))
        assert restored.last_run_utc == original.last_run_utc
        assert restored.articles_fetched == original.articles_fetched
        assert restored.articles_delivered == original.articles_delivered
        assert restored.telegram_success == original.telegram_success
        assert restored.telegram_failures == original.telegram_failures
        assert restored.email_success == original.email_success
        assert restored.sources_active == original.sources_active
        assert restored.run_duration_seconds == pytest.approx(original.run_duration_seconds)
