"""Telegram bot command handlers.

Provides /help, /status, /run, and unauthorized catch-all handler callbacks
for the python-telegram-bot Application.
"""

import logging
import os

from telegram import Update
from telegram.ext import ContextTypes

from pipeline.bot.dispatcher import trigger_pipeline
from pipeline.bot.status import fetch_pipeline_status

logger = logging.getLogger(__name__)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command — reply with a list of available commands."""
    text = (
        "Khabri Bot Commands:\n"
        "\n"
        "/help - Show this command list\n"
        "/status - Pipeline health summary\n"
        "/run - Trigger a pipeline run now\n"
        "/keywords - View keywords by category\n"
        "/menu - Interactive settings menu\n"
        "/pause [duration] - Pause deliveries (e.g. /pause 3 days)\n"
        "/resume - Resume paused deliveries\n"
        "/stats - View 7-day delivery statistics\n"
        "/schedule [time] - View or change delivery schedule\n"
        "\n"
        "Keyword management:\n"
        "  add keyword: <term> - Add to Infrastructure\n"
        "  add <category>: <term> - Add to specific category\n"
        "  remove <category>: <term> - Remove from category\n"
        "\n"
        "Natural language:\n"
        '  Just type naturally! e.g. "stop evening alerts for a week"\n'
    )
    await update.message.reply_text(text)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command — fetch and display pipeline health."""
    try:
        status = await fetch_pipeline_status()
    except Exception:
        logger.warning("Failed to fetch pipeline status", exc_info=True)
        await update.message.reply_text("Failed to fetch pipeline status. Please try again later.")
        return

    last_run = status.last_run_utc if status.last_run_utc else "Never"
    text = (
        f"Pipeline Status\n"
        f"\n"
        f"Last run: {last_run}\n"
        f"Articles fetched: {status.articles_fetched}\n"
        f"Articles delivered: {status.articles_delivered}\n"
        f"Telegram: {status.telegram_success} sent, {status.telegram_failures} failed\n"
        f"Email: {status.email_success} sent\n"
        f"Active sources: {status.sources_active}\n"
        f"Run duration: {status.run_duration_seconds:.1f}s\n"
    )
    await update.message.reply_text(text)


async def run_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /run command -- trigger an on-demand pipeline run via GitHub Actions.

    Reads GITHUB_PAT, GITHUB_OWNER, GITHUB_REPO from env vars.
    Sends immediate feedback, dispatches the run, and reports result.
    """
    token = os.environ.get("GITHUB_PAT", "")
    owner = os.environ.get("GITHUB_OWNER", "")
    repo = os.environ.get("GITHUB_REPO", "")

    if not token or not owner or not repo:
        await update.message.reply_text(
            "GitHub integration not configured. Set GITHUB_PAT, GITHUB_OWNER, GITHUB_REPO env vars."
        )
        return

    await update.message.reply_text("Triggering pipeline run...")

    success = await trigger_pipeline(token, owner, repo)
    if success:
        await update.message.reply_text(
            "Pipeline run dispatched. Check GitHub Actions for progress."
        )
    else:
        await update.message.reply_text("Failed to dispatch pipeline run. Check bot logs.")


async def unauthorized_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages from unauthorized users."""
    await update.message.reply_text("Unauthorized. Access denied.")
