"""Bot entrypoint — Application builder with polling for Railway deployment.

Builds a python-telegram-bot Application with auth-filtered command handlers
and starts long polling. Intended to run as a persistent process on Railway.

Usage:
    TELEGRAM_BOT_TOKEN=... uv run python -m pipeline.bot.entrypoint
"""

import logging
import os

from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from pipeline.bot.auth import load_authorized_users
from pipeline.bot.handler import (
    help_command,
    run_now_command,
    status_command,
    unauthorized_handler,
)
from pipeline.bot.keywords import (
    ADD_PATTERN,
    REMOVE_PATTERN,
    add_keyword_handler,
    keywords_command,
    remove_keyword_handler,
)
from pipeline.bot.menu import menu_callback, menu_command
from pipeline.bot.nlp import nl_command_handler
from pipeline.bot.pause import pause_command, resume_command
from pipeline.bot.schedule import schedule_command
from pipeline.bot.stats import stats_command

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Build and run the Telegram bot Application with polling.

    Reads TELEGRAM_BOT_TOKEN from env (required).
    Loads authorized user IDs from AUTHORIZED_USER_IDS env var.
    Registers /help, /status, /start, /run, /keywords, /menu handlers with auth filter.
    Registers add/remove keyword message handlers and inline keyboard callback handler.
    Registers unauthorized catch-all in group 1.
    Starts polling with drop_pending_updates=True, allowed_updates includes callback_query.

    Raises:
        RuntimeError: If TELEGRAM_BOT_TOKEN is not set or empty.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN env var is required")

    authorized = load_authorized_users()

    if authorized:
        auth_filter = filters.User(user_id=authorized)
        logger.info("Bot authorized for user IDs: %s", authorized)
    else:
        auth_filter = filters.ALL
        logger.warning("AUTHORIZED_USER_IDS not set — allowing all users")

    app = ApplicationBuilder().token(token).build()

    # Authorized command handlers (Phase 8)
    app.add_handler(CommandHandler("help", help_command, filters=auth_filter))
    app.add_handler(CommandHandler("status", status_command, filters=auth_filter))
    app.add_handler(CommandHandler("start", help_command, filters=auth_filter))
    app.add_handler(CommandHandler("run", run_now_command, filters=auth_filter))

    # Phase 9: keyword and menu handlers
    app.add_handler(CommandHandler("keywords", keywords_command, filters=auth_filter))
    app.add_handler(CommandHandler("menu", menu_command, filters=auth_filter))
    app.add_handler(MessageHandler(auth_filter & filters.Regex(ADD_PATTERN), add_keyword_handler))
    app.add_handler(
        MessageHandler(auth_filter & filters.Regex(REMOVE_PATTERN), remove_keyword_handler)
    )
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu_"))

    # Phase 10: Advanced bot controls
    app.add_handler(CommandHandler("pause", pause_command, filters=auth_filter))
    app.add_handler(CommandHandler("resume", resume_command, filters=auth_filter))
    app.add_handler(CommandHandler("stats", stats_command, filters=auth_filter))
    app.add_handler(CommandHandler("schedule", schedule_command, filters=auth_filter))

    # Unauthorized catch-all (lower priority group)
    app.add_handler(
        MessageHandler(filters.COMMAND & ~auth_filter, unauthorized_handler),
        group=1,
    )

    # Group 2: NL catch-all for non-command text (lowest priority)
    app.add_handler(
        MessageHandler(
            auth_filter & filters.TEXT & ~filters.COMMAND,
            nl_command_handler,
        ),
        group=2,
    )

    logger.info("Starting bot polling...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"],
    )


if __name__ == "__main__":
    main()
