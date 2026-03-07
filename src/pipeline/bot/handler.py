"""Telegram bot command handlers.

Provides /help, /status, and unauthorized catch-all handler callbacks
for the python-telegram-bot Application.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

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


async def unauthorized_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages from unauthorized users."""
    await update.message.reply_text("Unauthorized. Access denied.")
