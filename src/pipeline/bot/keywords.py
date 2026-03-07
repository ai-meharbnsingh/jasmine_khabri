"""Keyword display formatter, mutation functions, and command handlers.

Provides:
- Pure mutation functions: add_keyword, remove_keyword, serialize_keywords
- Display formatter: format_keywords_display
- Bot command handlers: keywords_command, add_keyword_handler, remove_keyword_handler
- Regex patterns: ADD_PATTERN, REMOVE_PATTERN
"""

import logging
import os
import re

import yaml

from pipeline.bot.github import read_github_file_with_sha, write_github_file
from pipeline.bot.status import read_github_file
from pipeline.schemas.keywords_schema import KeywordCategory, KeywordsConfig

logger = logging.getLogger(__name__)

# --- Regex patterns for text command matching ---

ADD_PATTERN = re.compile(r"add\s+(?:keyword|(\w+)):\s*(.+)", re.IGNORECASE)
REMOVE_PATTERN = re.compile(r"remove\s+(\w+):\s*(.+)", re.IGNORECASE)


# --- Pure mutation functions ---


def add_keyword(config: KeywordsConfig, category: str, keyword: str) -> KeywordsConfig:
    """Add a keyword to a category, returning a new KeywordsConfig.

    Case-insensitive category lookup and duplicate check.
    Uses model_copy immutable pattern (same as GNewsQuota/AICost).

    Args:
        config: Current keyword configuration.
        category: Category name (case-insensitive).
        keyword: Keyword to add.

    Returns:
        New KeywordsConfig with the keyword appended.

    Raises:
        ValueError: If category not found or keyword already exists.
    """
    # Case-insensitive category lookup
    actual_category = None
    for cat_name in config.categories:
        if cat_name.lower() == category.lower():
            actual_category = cat_name
            break

    if actual_category is None:
        raise ValueError(f"Unknown category: '{category}'")

    # Case-insensitive duplicate check
    existing_lower = [kw.lower() for kw in config.categories[actual_category].keywords]
    if keyword.lower() in existing_lower:
        raise ValueError(f"Keyword '{keyword}' already exists in '{actual_category}'")

    # Build new categories dict with the keyword appended
    new_categories = {}
    for cat_name, cat_data in config.categories.items():
        if cat_name == actual_category:
            new_keywords = list(cat_data.keywords) + [keyword]
            new_categories[cat_name] = KeywordCategory(
                active=cat_data.active, keywords=new_keywords
            )
        else:
            new_categories[cat_name] = cat_data.model_copy()

    return config.model_copy(update={"categories": new_categories})


def remove_keyword(config: KeywordsConfig, category: str, keyword: str) -> KeywordsConfig:
    """Remove a keyword from a category, returning a new KeywordsConfig.

    Case-insensitive match for both category and keyword.

    Args:
        config: Current keyword configuration.
        category: Category name (case-insensitive).
        keyword: Keyword to remove (case-insensitive).

    Returns:
        New KeywordsConfig with the keyword removed.

    Raises:
        ValueError: If category not found or keyword not in category.
    """
    # Case-insensitive category lookup
    actual_category = None
    for cat_name in config.categories:
        if cat_name.lower() == category.lower():
            actual_category = cat_name
            break

    if actual_category is None:
        raise ValueError(f"Unknown category: '{category}'")

    # Case-insensitive keyword lookup
    cat_data = config.categories[actual_category]
    found_keyword = None
    for kw in cat_data.keywords:
        if kw.lower() == keyword.lower():
            found_keyword = kw
            break

    if found_keyword is None:
        raise ValueError(f"Keyword '{keyword}' not found in '{actual_category}'")

    # Build new categories dict without the keyword
    new_categories = {}
    for cat_name, cat in config.categories.items():
        if cat_name == actual_category:
            new_keywords = [kw for kw in cat.keywords if kw != found_keyword]
            new_categories[cat_name] = KeywordCategory(active=cat.active, keywords=new_keywords)
        else:
            new_categories[cat_name] = cat.model_copy()

    return config.model_copy(update={"categories": new_categories})


def serialize_keywords(config: KeywordsConfig) -> str:
    """Serialize a KeywordsConfig to YAML string.

    Uses default_flow_style=False for readable block format,
    allow_unicode=True for Hindi/special chars, sort_keys=False
    to preserve insertion order.

    Args:
        config: Keyword configuration to serialize.

    Returns:
        YAML string suitable for writing to keywords.yaml.
    """
    data = config.model_dump()
    return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)


# --- Display formatter ---


def format_keywords_display(raw_yaml: str) -> str:
    """Format keywords YAML into a readable display string.

    Parses YAML into KeywordsConfig, formats each category with
    ACTIVE/INACTIVE status and bullet-listed keywords. Includes
    exclusions section at end.

    Pure function (no I/O) for easy testing.

    Args:
        raw_yaml: Raw YAML string from keywords.yaml.

    Returns:
        Formatted multi-line string for Telegram display.
    """
    data = yaml.safe_load(raw_yaml)
    config = KeywordsConfig(**data)

    lines: list[str] = ["Keyword Library\n"]

    for name, cat in config.categories.items():
        status = "ACTIVE" if cat.active else "INACTIVE"
        lines.append(f"{name.title()} [{status}]")
        for kw in cat.keywords:
            lines.append(f"  - {kw}")
        lines.append("")

    if config.exclusions:
        lines.append("Exclusions")
        for exc in config.exclusions:
            lines.append(f"  - {exc}")

    return "\n".join(lines)


# --- Bot command handlers ---


async def keywords_command(update, context) -> None:
    """Handle /keywords command -- fetch and display keyword library.

    Reads GITHUB_PAT, GITHUB_OWNER, GITHUB_REPO from env vars.
    Calls read_github_file (raw mode from status.py) for keywords.yaml.
    Formats via format_keywords_display and replies.

    On any exception: replies with error message (never crashes).
    """
    try:
        token = os.environ.get("GITHUB_PAT", "")
        owner = os.environ.get("GITHUB_OWNER", "")
        repo = os.environ.get("GITHUB_REPO", "")

        raw = await read_github_file("data/keywords.yaml", token, owner, repo)
        text = format_keywords_display(raw)
        await update.message.reply_text(text)
    except Exception:
        logger.warning("Failed to fetch keywords from GitHub", exc_info=True)
        await update.message.reply_text("Failed to fetch keywords. Please try again later.")


async def add_keyword_handler(update, context) -> None:
    """Handle 'add keyword: X' or 'add category: X' text command.

    Extracts category and keyword from regex capture groups.
    Defaults category to 'infrastructure' when user says 'add keyword: X'.
    Reads keywords.yaml with SHA, mutates, serializes, and writes back.
    """
    try:
        match = context.match
        category = match.group(1) or "infrastructure"
        keyword = match.group(2).strip()

        token = os.environ.get("GITHUB_PAT", "")
        owner = os.environ.get("GITHUB_OWNER", "")
        repo = os.environ.get("GITHUB_REPO", "")

        raw_yaml, sha = await read_github_file_with_sha("data/keywords.yaml", token, owner, repo)
        data = yaml.safe_load(raw_yaml)
        config = KeywordsConfig(**data)

        updated = add_keyword(config, category, keyword)
        new_yaml = serialize_keywords(updated)

        success = await write_github_file(
            "data/keywords.yaml",
            new_yaml,
            f"bot: add '{keyword}' to {category}",
            sha,
            token,
            owner,
            repo,
        )

        if success:
            await update.message.reply_text(f"Added '{keyword}' to {category.lower()}.")
        else:
            await update.message.reply_text(
                "Error: keyword added locally but failed to save to GitHub."
            )
    except ValueError as e:
        await update.message.reply_text(f"Error: {e}")
    except Exception:
        logger.warning("Failed to add keyword", exc_info=True)
        await update.message.reply_text("Error: failed to add keyword. Please try again later.")


async def remove_keyword_handler(update, context) -> None:
    """Handle 'remove category: X' text command.

    Extracts category and keyword from regex capture groups.
    Reads keywords.yaml with SHA, mutates, serializes, and writes back.
    """
    try:
        match = context.match
        category = match.group(1).strip()
        keyword = match.group(2).strip()

        token = os.environ.get("GITHUB_PAT", "")
        owner = os.environ.get("GITHUB_OWNER", "")
        repo = os.environ.get("GITHUB_REPO", "")

        raw_yaml, sha = await read_github_file_with_sha("data/keywords.yaml", token, owner, repo)
        data = yaml.safe_load(raw_yaml)
        config = KeywordsConfig(**data)

        updated = remove_keyword(config, category, keyword)
        new_yaml = serialize_keywords(updated)

        success = await write_github_file(
            "data/keywords.yaml",
            new_yaml,
            f"bot: remove '{keyword}' from {category}",
            sha,
            token,
            owner,
            repo,
        )

        if success:
            await update.message.reply_text(f"Removed '{keyword}' from {category.lower()}.")
        else:
            await update.message.reply_text(
                "Error: keyword removed locally but failed to save to GitHub."
            )
    except ValueError as e:
        await update.message.reply_text(f"Error: {e}")
    except Exception:
        logger.warning("Failed to remove keyword", exc_info=True)
        await update.message.reply_text("Error: failed to remove keyword. Please try again later.")
