"""Pause/resume command handlers and duration parser.

Provides:
- parse_duration: Convert human duration strings to timedelta
- pause_command: /pause handler (sets pause in bot_state.json via GitHub)
- resume_command: /resume handler (clears pause state)
"""

import re
from datetime import timedelta

# Pattern: "3 days", "a week", "an hour", "1 month", "30 minutes"
_DURATION_RE = re.compile(r"(\d+|a|an)\s*(minute|hour|day|week|month)s?", re.IGNORECASE)

_UNIT_MAP: dict[str, timedelta] = {
    "minute": timedelta(minutes=1),
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
    "week": timedelta(weeks=1),
    "month": timedelta(days=30),
}


def parse_duration(text: str) -> timedelta | None:
    """Parse a human-readable duration string into a timedelta.

    Supports: "3 days", "a week", "an hour", "2 hours", "1 month", "30 minutes".
    Returns None if the string cannot be parsed.
    """
    if not text or not text.strip():
        return None

    match = _DURATION_RE.search(text)
    if not match:
        return None

    amount_str = match.group(1).lower()
    unit = match.group(2).lower()

    amount = 1 if amount_str in ("a", "an") else int(amount_str)
    base = _UNIT_MAP.get(unit)
    if base is None:
        return None

    return base * amount
