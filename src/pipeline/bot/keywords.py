"""Keyword display formatter, mutation functions, and command handlers.

Provides:
- Pure mutation functions: add_keyword, remove_keyword, serialize_keywords
- Display formatter: format_keywords_display
- Bot command handlers: keywords_command, add_keyword_handler, remove_keyword_handler
- Regex patterns: ADD_PATTERN, REMOVE_PATTERN
"""

import logging
import re

import yaml

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
