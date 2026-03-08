"""Pause/resume command handlers and duration parser.

Provides:
- parse_duration: Convert human duration strings to timedelta
- pause_command: /pause handler (sets pause in bot_state.json via GitHub)
- resume_command: /resume handler (clears pause state)
"""

import json
import logging
import os
import re
from datetime import UTC, datetime, timedelta, timezone

from pipeline.bot.github import read_github_file_with_sha, write_github_file
from pipeline.schemas.bot_state_schema import BotState, PauseState

logger = logging.getLogger(__name__)

_IST = timezone(timedelta(hours=5, minutes=30))

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


async def pause_command(update, context) -> None:
    """Handle /pause command -- pause deliveries with optional duration.

    Usage: /pause 3 days | /pause a week | /pause (indefinite)
    Reads/writes bot_state.json via GitHub Contents API.
    """
    try:
        token = os.environ.get("GITHUB_PAT", "")
        owner = os.environ.get("GITHUB_OWNER", "")
        repo = os.environ.get("GITHUB_REPO", "")

        if not token or not owner or not repo:
            await update.message.reply_text(
                "Error: GitHub not configured. Set GITHUB_PAT, GITHUB_OWNER, GITHUB_REPO."
            )
            return

        # Extract text after /pause
        text = (update.message.text or "").strip()
        if text.lower().startswith("/pause"):
            text = text[6:].strip()

        # Parse duration if provided
        if text:
            duration = parse_duration(text)
            if duration is None:
                await update.message.reply_text("Could not parse duration. Try: /pause 3 days")
                return
        else:
            duration = None

        # Read current state
        raw_json, sha = await read_github_file_with_sha("data/bot_state.json", token, owner, repo)
        state = BotState.model_validate(json.loads(raw_json))

        # Compute pause
        if duration is not None:
            expiry = datetime.now(UTC) + duration
            paused_until = expiry.isoformat()
        else:
            paused_until = ""  # indefinite

        new_pause = PauseState(paused_until=paused_until, paused_slots=["all"])
        updated = state.model_copy(update={"pause": new_pause})

        # Write back
        new_json = json.dumps(updated.model_dump(), indent=2) + "\n"
        success = await write_github_file(
            path="data/bot_state.json",
            content=new_json,
            message="bot: pause deliveries",
            sha=sha,
            token=token,
            owner=owner,
            repo=repo,
        )

        if not success:
            await update.message.reply_text("Error: failed to save pause state to GitHub.")
            return

        # Reply
        if duration is not None:
            expiry_ist = expiry.astimezone(_IST).strftime("%d %b %Y %I:%M %p IST")
            await update.message.reply_text(f"Deliveries paused until {expiry_ist}.")
        else:
            await update.message.reply_text(
                "Deliveries paused indefinitely. Send /resume to restart."
            )

    except Exception:
        logger.warning("Error in pause_command", exc_info=True)
        await update.message.reply_text("Error: failed to pause deliveries.")


async def resume_command(update, context) -> None:
    """Handle /resume command -- clear pause state and resume deliveries.

    Reads/writes bot_state.json via GitHub Contents API.
    """
    try:
        token = os.environ.get("GITHUB_PAT", "")
        owner = os.environ.get("GITHUB_OWNER", "")
        repo = os.environ.get("GITHUB_REPO", "")

        if not token or not owner or not repo:
            await update.message.reply_text(
                "Error: GitHub not configured. Set GITHUB_PAT, GITHUB_OWNER, GITHUB_REPO."
            )
            return

        # Read current state
        raw_json, sha = await read_github_file_with_sha("data/bot_state.json", token, owner, repo)
        state = BotState.model_validate(json.loads(raw_json))

        # Check if actually paused
        if state.pause.paused_until == "" and not state.pause.paused_slots:
            await update.message.reply_text("Deliveries are not paused.")
            return

        # Clear pause
        updated = state.model_copy(update={"pause": PauseState()})

        # Write back
        new_json = json.dumps(updated.model_dump(), indent=2) + "\n"
        success = await write_github_file(
            path="data/bot_state.json",
            content=new_json,
            message="bot: resume deliveries",
            sha=sha,
            token=token,
            owner=owner,
            repo=repo,
        )

        if not success:
            await update.message.reply_text("Error: failed to save resume state to GitHub.")
            return

        await update.message.reply_text("Deliveries resumed.")

    except Exception:
        logger.warning("Error in resume_command", exc_info=True)
        await update.message.reply_text("Error: failed to resume deliveries.")
