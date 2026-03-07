"""Cost tracker unit tests with budget gate verification.

TDD Phase 5 Plan 01 — RED phase tests written before implementation.
Tests cover:
- check_budget threshold logic (ok/warning/exceeded)
- record_cost pricing for Claude Haiku and Gemini Flash
- record_cost accumulation, call_count, immutability
- load_ai_cost from file, missing file, monthly reset
- save_ai_cost round-trip
"""

import json
from datetime import UTC, datetime

import pytest

from pipeline.schemas.ai_cost_schema import AICost


class TestCheckBudget:
    """Tests for check_budget threshold logic."""

    def test_ok_when_under_warning(self):
        """Returns 'ok' when total_cost_usd < $4.00."""
        from pipeline.analyzers.cost_tracker import check_budget

        cost = AICost(month="2026-03", total_cost_usd=0.0)
        assert check_budget(cost) == "ok"

        cost2 = AICost(month="2026-03", total_cost_usd=3.99)
        assert check_budget(cost2) == "ok"

    def test_warning_at_threshold(self):
        """Returns 'warning' when total_cost_usd >= $4.00 and < $4.75."""
        from pipeline.analyzers.cost_tracker import check_budget

        cost = AICost(month="2026-03", total_cost_usd=4.00)
        assert check_budget(cost) == "warning"

        cost2 = AICost(month="2026-03", total_cost_usd=4.50)
        assert check_budget(cost2) == "warning"

        cost3 = AICost(month="2026-03", total_cost_usd=4.74)
        assert check_budget(cost3) == "warning"

    def test_exceeded_at_threshold(self):
        """Returns 'exceeded' when total_cost_usd >= $4.75."""
        from pipeline.analyzers.cost_tracker import check_budget

        cost = AICost(month="2026-03", total_cost_usd=4.75)
        assert check_budget(cost) == "exceeded"

        cost2 = AICost(month="2026-03", total_cost_usd=5.00)
        assert check_budget(cost2) == "exceeded"

        cost3 = AICost(month="2026-03", total_cost_usd=10.00)
        assert check_budget(cost3) == "exceeded"


class TestRecordCost:
    """Tests for record_cost pricing and accumulation."""

    def test_claude_pricing(self):
        """Claude Haiku pricing: $1/MTok input, $5/MTok output."""
        from pipeline.analyzers.cost_tracker import record_cost

        cost = AICost(month="2026-03")
        result = record_cost(cost, input_tokens=1000, output_tokens=500, provider="claude")

        expected_cost = (1000 * 1.0 / 1_000_000) + (500 * 5.0 / 1_000_000)
        assert result.total_input_tokens == 1000
        assert result.total_output_tokens == 500
        assert result.total_cost_usd == pytest.approx(expected_cost)
        assert result.call_count == 1

    def test_gemini_pricing(self):
        """Gemini Flash pricing: $0.30/MTok input, $2.50/MTok output."""
        from pipeline.analyzers.cost_tracker import record_cost

        cost = AICost(month="2026-03")
        result = record_cost(cost, input_tokens=2000, output_tokens=1000, provider="gemini")

        expected_cost = (2000 * 0.30 / 1_000_000) + (1000 * 2.50 / 1_000_000)
        assert result.total_input_tokens == 2000
        assert result.total_output_tokens == 1000
        assert result.total_cost_usd == pytest.approx(expected_cost)
        assert result.call_count == 1

    def test_accumulation(self):
        """Subsequent calls accumulate tokens and cost."""
        from pipeline.analyzers.cost_tracker import record_cost

        cost = AICost(
            month="2026-03",
            total_input_tokens=500,
            total_output_tokens=200,
            total_cost_usd=0.001,
            call_count=1,
        )
        result = record_cost(cost, input_tokens=1000, output_tokens=500, provider="claude")

        assert result.total_input_tokens == 1500
        assert result.total_output_tokens == 700
        assert result.call_count == 2
        # Cost should be previous + new
        new_cost = (1000 * 1.0 / 1_000_000) + (500 * 5.0 / 1_000_000)
        assert result.total_cost_usd == pytest.approx(0.001 + new_cost)

    def test_call_count_increment(self):
        """Each record_cost call increments call_count by 1."""
        from pipeline.analyzers.cost_tracker import record_cost

        cost = AICost(month="2026-03", call_count=5)
        result = record_cost(cost, input_tokens=100, output_tokens=50)
        assert result.call_count == 6

    def test_immutability(self):
        """record_cost returns new AICost, does not mutate input."""
        from pipeline.analyzers.cost_tracker import record_cost

        original = AICost(month="2026-03", total_cost_usd=0.0, call_count=0)
        result = record_cost(original, input_tokens=1000, output_tokens=500)

        # Original unchanged
        assert original.total_cost_usd == 0.0
        assert original.call_count == 0
        assert original.total_input_tokens == 0
        assert original.total_output_tokens == 0

        # Result is different object with updated values
        assert result is not original
        assert result.call_count == 1
        assert result.total_cost_usd > 0

    def test_default_provider_is_claude(self):
        """Provider defaults to 'claude' when not specified."""
        from pipeline.analyzers.cost_tracker import record_cost

        cost = AICost(month="2026-03")
        result_default = record_cost(cost, input_tokens=1000, output_tokens=500)
        result_claude = record_cost(cost, input_tokens=1000, output_tokens=500, provider="claude")
        assert result_default.total_cost_usd == result_claude.total_cost_usd


class TestLoadAiCost:
    """Tests for load_ai_cost from loader.py."""

    def test_missing_file_returns_current_month(self, tmp_path):
        """Returns AICost with current month if file doesn't exist."""
        from pipeline.utils.loader import load_ai_cost

        result = load_ai_cost(str(tmp_path / "nonexistent.json"))
        current_month = datetime.now(UTC).strftime("%Y-%m")
        assert result.month == current_month
        assert result.total_cost_usd == 0.0
        assert result.call_count == 0

    def test_valid_file_loads(self, tmp_path):
        """Loads AICost from valid JSON file."""
        from pipeline.utils.loader import load_ai_cost

        cost_data = {
            "month": "2026-03",
            "total_input_tokens": 5000,
            "total_output_tokens": 2000,
            "total_cost_usd": 0.015,
            "call_count": 3,
        }
        p = tmp_path / "ai_cost.json"
        p.write_text(json.dumps(cost_data))

        result = load_ai_cost(str(p))
        assert result.month == "2026-03"
        assert result.total_input_tokens == 5000
        assert result.total_output_tokens == 2000
        assert result.total_cost_usd == 0.015
        assert result.call_count == 3

    def test_monthly_reset(self, tmp_path):
        """Resets to current month if stored month differs from current."""
        from pipeline.utils.loader import load_ai_cost

        # Write data for a previous month
        cost_data = {
            "month": "2025-01",
            "total_input_tokens": 50000,
            "total_output_tokens": 20000,
            "total_cost_usd": 3.50,
            "call_count": 100,
        }
        p = tmp_path / "ai_cost.json"
        p.write_text(json.dumps(cost_data))

        result = load_ai_cost(str(p))
        current_month = datetime.now(UTC).strftime("%Y-%m")
        assert result.month == current_month
        assert result.total_cost_usd == 0.0
        assert result.call_count == 0
        assert result.total_input_tokens == 0
        assert result.total_output_tokens == 0

    def test_current_month_no_reset(self, tmp_path):
        """Does NOT reset if stored month matches current month."""
        from pipeline.utils.loader import load_ai_cost

        current_month = datetime.now(UTC).strftime("%Y-%m")
        cost_data = {
            "month": current_month,
            "total_input_tokens": 5000,
            "total_output_tokens": 2000,
            "total_cost_usd": 1.50,
            "call_count": 10,
        }
        p = tmp_path / "ai_cost.json"
        p.write_text(json.dumps(cost_data))

        result = load_ai_cost(str(p))
        assert result.month == current_month
        assert result.total_cost_usd == 1.50
        assert result.call_count == 10


class TestSaveAiCost:
    """Tests for save_ai_cost from loader.py."""

    def test_roundtrip(self, tmp_path):
        """save_ai_cost then load_ai_cost preserves all fields."""
        from pipeline.utils.loader import load_ai_cost, save_ai_cost

        current_month = datetime.now(UTC).strftime("%Y-%m")
        original = AICost(
            month=current_month,
            total_input_tokens=3000,
            total_output_tokens=1500,
            total_cost_usd=0.0105,
            call_count=2,
        )
        p = tmp_path / "ai_cost.json"
        save_ai_cost(original, str(p))

        restored = load_ai_cost(str(p))
        assert restored.month == original.month
        assert restored.total_input_tokens == original.total_input_tokens
        assert restored.total_output_tokens == original.total_output_tokens
        assert restored.total_cost_usd == pytest.approx(original.total_cost_usd)
        assert restored.call_count == original.call_count

    def test_file_format(self, tmp_path):
        """Saved file uses indent 2 and trailing newline."""
        from pipeline.utils.loader import save_ai_cost

        cost = AICost(month="2026-03", total_cost_usd=0.5, call_count=1)
        p = tmp_path / "ai_cost.json"
        save_ai_cost(cost, str(p))

        text = p.read_text()
        assert text.endswith("\n")
        # Verify it's valid JSON with indentation
        parsed = json.loads(text)
        assert parsed["month"] == "2026-03"
