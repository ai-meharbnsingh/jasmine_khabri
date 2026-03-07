"""Authorization guard for Telegram bot.

Loads authorized user IDs from AUTHORIZED_USER_IDS env var (comma-separated).
Used with python-telegram-bot filters.User for command access control.
"""

import os


def load_authorized_users() -> set[int]:
    """Load authorized user IDs from AUTHORIZED_USER_IDS env var.

    Format: comma-separated integers, e.g. "123,456,789".
    Strips whitespace and ignores empty segments.

    Returns:
        Set of authorized Telegram user IDs. Empty set if env var unset/empty.
    """
    raw = os.environ.get("AUTHORIZED_USER_IDS", "")
    if not raw:
        return set()
    return {int(uid.strip()) for uid in raw.split(",") if uid.strip()}
