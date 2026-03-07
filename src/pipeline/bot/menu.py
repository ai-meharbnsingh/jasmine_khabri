"""Inline keyboard menu command and callback handlers.

Provides /menu command (inline keyboard with Keywords, Status, Help buttons)
and menu_callback handler that routes button taps to the correct content.

Exports: menu_command, menu_callback
"""

import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from pipeline.bot.auth import load_authorized_users
from pipeline.bot.keywords import format_keywords_display
from pipeline.bot.status import fetch_pipeline_status, read_github_file

logger = logging.getLogger(__name__)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /menu command -- reply with an inline keyboard menu.

    Builds InlineKeyboardMarkup with 2 rows:
      Row 1: [Keywords, Status]
      Row 2: [Help]
    """
    keyboard = [
        [
            InlineKeyboardButton("Keywords", callback_data="menu_keywords"),
            InlineKeyboardButton("Status", callback_data="menu_status"),
        ],
        [
            InlineKeyboardButton("Help", callback_data="menu_help"),
        ],
    ]
    markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Khabri Menu:", reply_markup=markup)


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button taps from /menu.

    Always calls query.answer() first to dismiss the loading indicator.
    Checks query.from_user.id against authorized users (defense-in-depth).
    Routes by query.data: menu_keywords, menu_status, menu_help.
    Wraps each branch in try/except for graceful error handling.
    """
    query = update.callback_query
    await query.answer()

    # Defense-in-depth auth check
    authorized = load_authorized_users()
    if authorized and query.from_user.id not in authorized:
        await query.edit_message_text("Unauthorized. Access denied.")
        return

    data = query.data

    if data == "menu_keywords":
        try:
            token = os.environ.get("GITHUB_PAT", "")
            owner = os.environ.get("GITHUB_OWNER", "")
            repo = os.environ.get("GITHUB_REPO", "")
            raw = await read_github_file("data/keywords.yaml", token, owner, repo)
            text = format_keywords_display(raw)
            await query.edit_message_text(text)
        except Exception:
            logger.warning("Failed to load keywords for menu", exc_info=True)
            await query.edit_message_text("Failed to load keywords. Try again.")

    elif data == "menu_status":
        try:
            status = await fetch_pipeline_status()
            last_run = status.last_run_utc if status.last_run_utc else "Never"
            text = (
                f"Pipeline Status\n"
                f"\n"
                f"Last run: {last_run}\n"
                f"Articles fetched: {status.articles_fetched}\n"
                f"Articles delivered: {status.articles_delivered}\n"
                f"Telegram: {status.telegram_success} sent, "
                f"{status.telegram_failures} failed\n"
                f"Email: {status.email_success} sent\n"
                f"Active sources: {status.sources_active}\n"
                f"Run duration: {status.run_duration_seconds:.1f}s\n"
            )
            await query.edit_message_text(text)
        except Exception:
            logger.warning("Failed to load status for menu", exc_info=True)
            await query.edit_message_text("Failed to load status. Try again.")

    elif data == "menu_help":
        text = (
            "Khabri Bot Commands:\n"
            "\n"
            "/help - Show this command list\n"
            "/status - Pipeline health summary\n"
            "/run - Trigger a pipeline run now\n"
            "/keywords - View keywords by category\n"
            "/menu - Interactive settings menu\n"
            "\n"
            "Keyword management:\n"
            "  add keyword: <term> - Add to Infrastructure\n"
            "  add <category>: <term> - Add to specific category\n"
            "  remove <category>: <term> - Remove from category\n"
        )
        await query.edit_message_text(text)
