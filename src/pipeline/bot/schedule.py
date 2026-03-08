"""Schedule modification and event creation handlers.

Provides:
- parse_ist_time: Parse human-readable IST time strings to (hour, minute)
- ist_to_utc_cron: Convert IST hour/minute to UTC for cron expressions
- schedule_command: /schedule handler for viewing/changing delivery times
- schedule_command_inner: Core logic for schedule modification (used by NL dispatch)
- create_event_schedule: Create EventSchedule entries in bot_state.json
"""

import json
import logging
import os
import re

from pipeline.bot.github import read_github_file_with_sha, write_github_file
from pipeline.schemas.bot_state_schema import BotState, EventSchedule

logger = logging.getLogger(__name__)

# Pattern: "6:30 AM", "16:00", "5 PM", "12 AM"
_TIME_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM|am|pm)?")


def parse_ist_time(text: str) -> tuple[int, int] | None:
    """Parse a human-readable time string into (hour, minute) in 24h format.

    Supports: "6:30 AM", "16:00", "5 PM", "12 AM", "12 PM".
    Returns None if the string cannot be parsed.

    Args:
        text: Time string to parse.

    Returns:
        Tuple of (hour, minute) in 24-hour format, or None.
    """
    if not text or not text.strip():
        return None

    match = _TIME_RE.search(text.strip())
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2)) if match.group(2) else 0
    ampm = match.group(3)

    if ampm:
        ampm = ampm.upper()
        if ampm == "AM":
            if hour == 12:
                hour = 0
        elif ampm == "PM":
            if hour != 12:
                hour += 12

    if not (0 <= hour <= 23) or not (0 <= minute <= 59):
        return None

    return (hour, minute)


def ist_to_utc_cron(hour_ist: int, minute_ist: int) -> tuple[int, int]:
    """Convert IST time to UTC time for cron expressions.

    IST = UTC + 5:30, so subtract 330 minutes from IST total.
    Wraps negative values to previous day.

    Args:
        hour_ist: Hour in IST (0-23).
        minute_ist: Minute in IST (0-59).

    Returns:
        Tuple of (hour_utc, minute_utc).
    """
    total_ist = hour_ist * 60 + minute_ist
    total_utc = total_ist - 330  # IST offset is +5:30 = 330 min
    if total_utc < 0:
        total_utc += 1440  # wrap to previous day
    hour_utc = total_utc // 60
    minute_utc = total_utc % 60
    return (hour_utc, minute_utc)


async def schedule_command_inner(slot: str, time_text: str) -> tuple[bool, str]:
    """Core schedule modification logic, usable from both /schedule and NL.

    Args:
        slot: "morning" or "evening".
        time_text: Time string like "06:30" or "5 PM".

    Returns:
        Tuple of (success, message_to_user).
    """
    token = os.environ.get("GITHUB_PAT", "")
    owner = os.environ.get("GITHUB_OWNER", "")
    repo = os.environ.get("GITHUB_REPO", "")

    if not token or not owner or not repo:
        return False, "Error: GitHub not configured."

    parsed = parse_ist_time(time_text)
    if parsed is None:
        return False, ("Could not parse time. Try: /schedule 6:30 AM or /schedule evening 5 PM")

    hour, minute = parsed
    time_str = f"{hour:02d}:{minute:02d}"

    try:
        raw_json, sha = await read_github_file_with_sha("data/bot_state.json", token, owner, repo)
        state = BotState.model_validate(json.loads(raw_json))

        if slot == "evening":
            new_sched = state.custom_schedule.model_copy(update={"evening_ist": time_str})
        else:
            new_sched = state.custom_schedule.model_copy(update={"morning_ist": time_str})

        updated = state.model_copy(update={"custom_schedule": new_sched})
        new_json = json.dumps(updated.model_dump(), indent=2) + "\n"

        success = await write_github_file(
            path="data/bot_state.json",
            content=new_json,
            message=f"bot: update {slot} schedule to {time_str} IST",
            sha=sha,
            token=token,
            owner=owner,
            repo=repo,
        )

        if not success:
            return False, "Error: failed to save schedule to GitHub."

        utc_h, utc_m = ist_to_utc_cron(hour, minute)
        msg = (
            f"Updated {slot} delivery to {time_str} IST "
            f"({utc_h:02d}:{utc_m:02d} UTC). "
            f"Note: GitHub Actions cron may need manual update "
            f"to {utc_m} {utc_h} * * *"
        )
        return True, msg

    except Exception:
        logger.warning("Schedule update failed", exc_info=True)
        return False, "Error: failed to update schedule."


async def schedule_command(update, context) -> None:
    """Handle /schedule command -- view or modify delivery schedule.

    Usage:
        /schedule - Show current schedule
        /schedule 6:30 AM - Set morning time
        /schedule evening 5 PM - Set evening time
    """
    text = (update.message.text or "").strip()
    if text.lower().startswith("/schedule"):
        text = text[9:].strip()

    # No args: show current schedule
    if not text:
        try:
            token = os.environ.get("GITHUB_PAT", "")
            owner = os.environ.get("GITHUB_OWNER", "")
            repo = os.environ.get("GITHUB_REPO", "")

            if not token or not owner or not repo:
                await update.message.reply_text("Error: GitHub not configured.")
                return

            raw_json, _sha = await read_github_file_with_sha(
                "data/bot_state.json", token, owner, repo
            )
            state = BotState.model_validate(json.loads(raw_json))

            morning = state.custom_schedule.morning_ist or "default"
            evening = state.custom_schedule.evening_ist or "default"

            lines = [
                "Current Schedule",
                f"  Morning: {morning}",
                f"  Evening: {evening}",
            ]

            if state.events:
                lines.append("\nActive Events:")
                for ev in state.events:
                    if ev.active:
                        lines.append(
                            f"  {ev.name} ({ev.date}) "
                            f"{ev.start_time_ist}-{ev.end_time_ist} "
                            f"every {ev.interval_minutes}min"
                        )

            await update.message.reply_text("\n".join(lines))
        except Exception:
            logger.warning("Schedule show failed", exc_info=True)
            await update.message.reply_text("Error: failed to fetch schedule.")
        return

    # Detect slot keyword
    lower = text.lower()
    if lower.startswith("evening") or lower.startswith("ev "):
        slot = "evening"
        text = re.sub(r"^(?:evening|ev)\s*", "", text, flags=re.IGNORECASE)
    else:
        slot = "morning"

    # Parse time
    parsed = parse_ist_time(text)
    if parsed is None:
        await update.message.reply_text(
            "Could not parse time. Try: /schedule 6:30 AM or /schedule evening 5 PM"
        )
        return

    success, msg = await schedule_command_inner(slot, text)
    await update.message.reply_text(msg)


async def create_event_schedule(
    name: str,
    date: str,
    interval_minutes: int,
    start_time_ist: str,
    end_time_ist: str,
    token: str,
    owner: str,
    repo: str,
) -> bool:
    """Create an EventSchedule and append to bot_state.json events list.

    Args:
        name: Event name (e.g. "Budget").
        date: ISO 8601 date string.
        interval_minutes: Update interval in minutes.
        start_time_ist: Start time in IST (HH:MM).
        end_time_ist: End time in IST (HH:MM).
        token: GitHub PAT.
        owner: GitHub repo owner.
        repo: GitHub repo name.

    Returns:
        True on success, False on any failure.
    """
    # Validate params
    if not name or not date or interval_minutes <= 0:
        return False

    try:
        raw_json, sha = await read_github_file_with_sha("data/bot_state.json", token, owner, repo)
        state = BotState.model_validate(json.loads(raw_json))

        event = EventSchedule(
            name=name,
            date=date,
            interval_minutes=interval_minutes,
            start_time_ist=start_time_ist,
            end_time_ist=end_time_ist,
        )
        new_events = list(state.events) + [event]
        updated = state.model_copy(update={"events": new_events})

        new_json = json.dumps(updated.model_dump(), indent=2) + "\n"
        success = await write_github_file(
            path="data/bot_state.json",
            content=new_json,
            message=f"bot: add event schedule '{name}'",
            sha=sha,
            token=token,
            owner=owner,
            repo=repo,
        )
        return success

    except Exception:
        logger.warning("Event schedule creation failed", exc_info=True)
        return False
