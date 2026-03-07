"""AI cost tracking with budget gates.

Tracks monthly AI API costs across providers (Claude Haiku, Gemini Flash).
Budget gates enforce warning at $4.00 and degradation at $4.75.
"""

from typing import Literal

from pipeline.schemas.ai_cost_schema import AICost

# Claude Haiku 4.5 pricing (per token)
CLAUDE_HAIKU_INPUT = 1.0 / 1_000_000  # $1.00 per MTok
CLAUDE_HAIKU_OUTPUT = 5.0 / 1_000_000  # $5.00 per MTok

# Gemini 2.5 Flash pricing (per token)
GEMINI_FLASH_INPUT = 0.30 / 1_000_000  # $0.30 per MTok
GEMINI_FLASH_OUTPUT = 2.50 / 1_000_000  # $2.50 per MTok

# Budget thresholds
MONTHLY_BUDGET = 5.00
BUDGET_WARNING_THRESHOLD = 4.00
BUDGET_DEGRADE_THRESHOLD = 4.75


def check_budget(cost: AICost) -> Literal["ok", "warning", "exceeded"]:
    """Check current cost against budget thresholds.

    Returns:
        "ok" — under $4.00
        "warning" — $4.00 to $4.74
        "exceeded" — $4.75 and above
    """
    if cost.total_cost_usd >= BUDGET_DEGRADE_THRESHOLD:
        return "exceeded"
    if cost.total_cost_usd >= BUDGET_WARNING_THRESHOLD:
        return "warning"
    return "ok"


def record_cost(
    cost: AICost,
    input_tokens: int,
    output_tokens: int,
    provider: Literal["claude", "gemini"] = "claude",
) -> AICost:
    """Record an API call's token usage and compute cost.

    Functional style: returns new AICost via model_copy, never mutates input.

    Args:
        cost: Current cost state.
        input_tokens: Number of input tokens used.
        output_tokens: Number of output tokens used.
        provider: "claude" for Claude Haiku 4.5, "gemini" for Gemini 2.5 Flash.

    Returns:
        New AICost with accumulated tokens and computed cost.
    """
    if provider == "gemini":
        call_cost = (input_tokens * GEMINI_FLASH_INPUT) + (output_tokens * GEMINI_FLASH_OUTPUT)
    else:
        call_cost = (input_tokens * CLAUDE_HAIKU_INPUT) + (output_tokens * CLAUDE_HAIKU_OUTPUT)

    return cost.model_copy(
        update={
            "total_input_tokens": cost.total_input_tokens + input_tokens,
            "total_output_tokens": cost.total_output_tokens + output_tokens,
            "total_cost_usd": cost.total_cost_usd + call_cost,
            "call_count": cost.call_count + 1,
        }
    )
