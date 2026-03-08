"""Natural language intent parser with Gemini/Claude and dispatch.

Provides:
- NLIntent: Pydantic model for parsed intent with parameters
- parse_nl_intent: Calls Gemini Flash (primary) or Claude Haiku (fallback)
- nl_command_handler: Telegram MessageHandler that parses and dispatches NL commands
- _dispatch_* helpers: Route parsed intents to existing bot handlers
"""

import asyncio
import json
import logging
import os
from typing import Literal

import anthropic
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class NLIntent(BaseModel):
    """Parsed intent from natural language command."""

    intent: Literal[
        "pause",
        "resume",
        "schedule_modify",
        "event_schedule",
        "keyword_add",
        "keyword_remove",
        "unknown",
    ] = "unknown"
    confidence: float = 0.0
    slot: str = ""  # morning/evening/all
    duration: str = ""  # "3 days", "a week"
    new_time: str = ""  # "06:30" for schedule_modify
    event_name: str = ""
    event_date: str = ""  # ISO date
    interval_minutes: int = 0
    start_time: str = ""  # HH:MM IST
    end_time: str = ""  # HH:MM IST
    category: str = ""  # for keyword intents
    keyword: str = ""  # for keyword intents


NL_SYSTEM_PROMPT = (  # noqa: E501
    "You are the Khabri news bot's intent classifier. "
    "Given a user message, classify it into one of these intents "
    "and extract parameters. Return ONLY valid JSON.\n\n"
    "Intents:\n"
    '1. "pause" - Stop/pause deliveries. '
    "Extract: slot (morning/evening/all), duration.\n"
    '2. "resume" - Restart/resume deliveries.\n'
    '3. "schedule_modify" - Change delivery time. '
    "Extract: slot (morning/evening), new_time (HH:MM 24h).\n"
    '4. "event_schedule" - Event-based tracking. '
    "Extract: event_name, event_date (ISO), interval_minutes, "
    "start_time (HH:MM), end_time (HH:MM).\n"
    '5. "keyword_add" - Track/follow a topic. '
    "Extract: category (infrastructure/real_estate/celebrity/policy), keyword.\n"
    '6. "keyword_remove" - Stop tracking a topic. '
    "Extract: category, keyword.\n"
    '7. "unknown" - Cannot classify the message.\n\n'
    "Examples:\n"
    '- "stop evening alerts for a week" -> '
    '{"intent":"pause","confidence":0.95,"slot":"evening","duration":"a week"}\n'
    '- "resume deliveries" -> {"intent":"resume","confidence":0.95}\n'
    '- "change morning alert to 6:30 AM" -> '
    '{"intent":"schedule_modify","confidence":0.9,'
    '"slot":"morning","new_time":"06:30"}\n'
    '- "Budget on Feb 1, updates every 30 min from 10 AM to 3 PM" -> '
    '{"intent":"event_schedule","confidence":0.9,"event_name":"Budget",'
    '"event_date":"2026-02-01","interval_minutes":30,'
    '"start_time":"10:00","end_time":"15:00"}\n'
    '- "track Priyanka Chopra" -> '
    '{"intent":"keyword_add","confidence":0.85,'
    '"category":"celebrity","keyword":"Priyanka Chopra"}\n'
    '- "hello" -> {"intent":"unknown","confidence":0.3}\n\n'
    "Return JSON with at minimum: intent, confidence (0.0-1.0). "
    "Include only relevant fields for the intent."
)


def _parse_with_gemini(text: str) -> NLIntent | None:
    """Try parsing intent with Gemini Flash (free tier)."""
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        return None

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{NL_SYSTEM_PROMPT}\n\nUser message: {text}",
            config={"response_mime_type": "application/json"},
        )
        data = json.loads(response.text)
        return NLIntent(**data)
    except Exception:
        logger.warning("Gemini NL parse failed for: %s", text[:50], exc_info=True)
        return None


def _parse_with_claude(text: str) -> NLIntent | None:
    """Try parsing intent with Claude Haiku (fallback)."""
    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        response = client.messages.create(
            model="claude-haiku-4-5-20250315",
            max_tokens=256,
            system=NL_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        raw = response.content[0].text
        data = json.loads(raw)
        return NLIntent(**data)
    except Exception:
        logger.warning("Claude NL parse failed for: %s", text[:50], exc_info=True)
        return None


def parse_nl_intent(text: str) -> NLIntent:
    """Parse freeform text into a structured NLIntent.

    Tries Gemini Flash first (free tier), falls back to Claude Haiku.
    Returns NLIntent with intent="unknown" if both fail.

    Args:
        text: User's freeform message text.

    Returns:
        NLIntent with classified intent and extracted parameters.
    """
    # Try Gemini first (free)
    result = _parse_with_gemini(text)
    if result is not None:
        return result

    # Fallback to Claude
    logger.info("Gemini failed -- attempting Claude fallback for NL parse")
    result = _parse_with_claude(text)
    if result is not None:
        return result

    return NLIntent(intent="unknown")


async def _dispatch_pause(update, intent: NLIntent) -> None:
    """Dispatch pause intent — pause deliveries with slot-specific logic."""
    from pipeline.bot.pause import parse_duration

    slot = intent.slot or "all"
    duration_text = intent.duration

    try:
        token = os.environ.get("GITHUB_PAT", "")
        owner = os.environ.get("GITHUB_OWNER", "")
        repo = os.environ.get("GITHUB_REPO", "")

        if not token or not owner or not repo:
            await update.message.reply_text("Error: GitHub not configured.")
            return

        from datetime import UTC, datetime

        from pipeline.bot.github import read_github_file_with_sha, write_github_file
        from pipeline.schemas.bot_state_schema import BotState, PauseState

        raw_json, sha = await read_github_file_with_sha("data/bot_state.json", token, owner, repo)
        state = BotState.model_validate(json.loads(raw_json))

        if duration_text:
            duration = parse_duration(duration_text)
            if duration is not None:
                expiry = datetime.now(UTC) + duration
                paused_until = expiry.isoformat()
            else:
                paused_until = ""
        else:
            paused_until = ""

        paused_slots = [slot] if slot != "all" else ["all"]
        new_pause = PauseState(paused_until=paused_until, paused_slots=paused_slots)
        updated = state.model_copy(update={"pause": new_pause})

        new_json = json.dumps(updated.model_dump(), indent=2) + "\n"
        success = await write_github_file(
            path="data/bot_state.json",
            content=new_json,
            message="bot: NL pause deliveries",
            sha=sha,
            token=token,
            owner=owner,
            repo=repo,
        )

        if success:
            msg = f"Understood: pausing {slot} deliveries"
            if duration_text:
                msg += f" for {duration_text}"
            msg += "."
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text("Error: failed to save pause state.")
    except Exception:
        logger.warning("NL pause dispatch failed", exc_info=True)
        await update.message.reply_text("Error: failed to pause deliveries.")


async def _dispatch_resume(update, intent: NLIntent) -> None:
    """Dispatch resume intent — clear pause state."""
    try:
        token = os.environ.get("GITHUB_PAT", "")
        owner = os.environ.get("GITHUB_OWNER", "")
        repo = os.environ.get("GITHUB_REPO", "")

        if not token or not owner or not repo:
            await update.message.reply_text("Error: GitHub not configured.")
            return

        from pipeline.bot.github import read_github_file_with_sha, write_github_file
        from pipeline.schemas.bot_state_schema import BotState, PauseState

        raw_json, sha = await read_github_file_with_sha("data/bot_state.json", token, owner, repo)
        state = BotState.model_validate(json.loads(raw_json))

        updated = state.model_copy(update={"pause": PauseState()})
        new_json = json.dumps(updated.model_dump(), indent=2) + "\n"
        success = await write_github_file(
            path="data/bot_state.json",
            content=new_json,
            message="bot: NL resume deliveries",
            sha=sha,
            token=token,
            owner=owner,
            repo=repo,
        )

        if success:
            await update.message.reply_text("Understood: resuming deliveries.")
        else:
            await update.message.reply_text("Error: failed to resume deliveries.")
    except Exception:
        logger.warning("NL resume dispatch failed", exc_info=True)
        await update.message.reply_text("Error: failed to resume deliveries.")


async def _dispatch_schedule_modify(update, intent: NLIntent) -> None:
    """Dispatch schedule_modify intent — update custom schedule time."""
    try:
        from pipeline.bot.schedule import schedule_command_inner

        slot = intent.slot or "morning"
        new_time = intent.new_time
        success, msg = await schedule_command_inner(slot, new_time)
        await update.message.reply_text(msg)
    except Exception:
        logger.warning("NL schedule_modify dispatch failed", exc_info=True)
        await update.message.reply_text("Error: failed to update schedule.")


async def _dispatch_event_schedule(update, intent: NLIntent) -> None:
    """Dispatch event_schedule intent — create event schedule entry."""
    try:
        token = os.environ.get("GITHUB_PAT", "")
        owner = os.environ.get("GITHUB_OWNER", "")
        repo = os.environ.get("GITHUB_REPO", "")

        from pipeline.bot.schedule import create_event_schedule

        success = await create_event_schedule(
            name=intent.event_name,
            date=intent.event_date,
            interval_minutes=intent.interval_minutes,
            start_time_ist=intent.start_time,
            end_time_ist=intent.end_time,
            token=token,
            owner=owner,
            repo=repo,
        )

        if success:
            await update.message.reply_text(
                f"Event '{intent.event_name}' scheduled for {intent.event_date} "
                f"({intent.start_time}-{intent.end_time} IST, every {intent.interval_minutes} min)."
            )
        else:
            await update.message.reply_text("Error: failed to create event schedule.")
    except Exception:
        logger.warning("NL event_schedule dispatch failed", exc_info=True)
        await update.message.reply_text("Error: failed to create event schedule.")


async def _dispatch_keyword_add(update, intent: NLIntent) -> None:
    """Dispatch keyword_add intent — add keyword to category."""
    cat, kw = intent.category, intent.keyword
    # TODO: Implement actual keyword modification via GitHub Contents API
    await update.message.reply_text(
        f"Keyword management via NL is not yet implemented.\n"
        f"To add '{kw}' to {cat}, use: add {cat}: {kw}"
    )


async def _dispatch_keyword_remove(update, intent: NLIntent) -> None:
    """Dispatch keyword_remove intent — remove keyword from category."""
    cat, kw = intent.category, intent.keyword
    # TODO: Implement actual keyword modification via GitHub Contents API
    await update.message.reply_text(
        f"Keyword management via NL is not yet implemented.\n"
        f"To remove '{kw}' from {cat}, use: remove {cat}: {kw}"
    )


async def nl_command_handler(update, context) -> None:
    """Handle non-command text messages via NL intent parsing.

    1. Ignores messages shorter than 6 characters.
    2. Sends 'Processing...' feedback before AI call.
    3. Calls parse_nl_intent in executor to avoid blocking event loop.
    4. Dispatches to appropriate handler based on intent.
    """
    text = (update.message.text or "").strip()
    if len(text) < 6:
        return

    await update.message.reply_text("Processing...")

    # Run sync Anthropic call in executor to avoid blocking
    loop = asyncio.get_event_loop()
    intent = await loop.run_in_executor(None, parse_nl_intent, text)

    if intent.confidence < 0.6 or intent.intent == "unknown":
        await update.message.reply_text(
            "I didn't understand that. Try /help for available commands."
        )
        return

    dispatch_map = {
        "pause": _dispatch_pause,
        "resume": _dispatch_resume,
        "schedule_modify": _dispatch_schedule_modify,
        "event_schedule": _dispatch_event_schedule,
        "keyword_add": _dispatch_keyword_add,
        "keyword_remove": _dispatch_keyword_remove,
    }

    handler = dispatch_map.get(intent.intent)
    if handler:
        await handler(update, intent)
    else:
        await update.message.reply_text(
            "I didn't understand that. Try /help for available commands."
        )
