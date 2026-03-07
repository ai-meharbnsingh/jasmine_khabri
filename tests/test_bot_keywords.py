"""Tests for keyword management — mutations, display, and command handlers.

TDD Phase 9 Plan 01.
Task 1: Mutation tests (add_keyword, remove_keyword, serialize_keywords).
Task 2: Display and handler tests (format_keywords_display, commands).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import yaml

from pipeline.bot.keywords import (
    ADD_PATTERN,
    REMOVE_PATTERN,
    add_keyword,
    add_keyword_handler,
    format_keywords_display,
    keywords_command,
    remove_keyword,
    remove_keyword_handler,
    serialize_keywords,
)
from pipeline.schemas.keywords_schema import KeywordCategory, KeywordsConfig


def _make_config() -> KeywordsConfig:
    """Create a minimal KeywordsConfig for testing."""
    return KeywordsConfig(
        categories={
            "infrastructure": KeywordCategory(
                active=True, keywords=["metro", "highway", "airport"]
            ),
            "celebrity": KeywordCategory(active=False, keywords=["Salman Khan", "Virat Kohli"]),
        },
        exclusions=["obituary", "scandal"],
    )


class TestAddKeyword:
    """Tests for add_keyword pure mutation function."""

    def test_adds_keyword_to_existing_category(self):
        """add_keyword appends keyword to specified category."""
        config = _make_config()
        result = add_keyword(config, "infrastructure", "bullet train")
        assert "bullet train" in result.categories["infrastructure"].keywords
        assert len(result.categories["infrastructure"].keywords) == 4

    def test_returns_new_config_immutably(self):
        """add_keyword returns new KeywordsConfig, does not mutate original."""
        config = _make_config()
        result = add_keyword(config, "infrastructure", "bullet train")
        assert result is not config
        assert "bullet train" not in config.categories["infrastructure"].keywords

    def test_raises_on_unknown_category(self):
        """add_keyword raises ValueError for non-existent category."""
        config = _make_config()
        import pytest

        with pytest.raises(ValueError, match="Unknown category"):
            add_keyword(config, "nonexistent", "test")

    def test_raises_on_duplicate_case_insensitive(self):
        """add_keyword raises ValueError for duplicate keyword (case-insensitive)."""
        config = _make_config()
        import pytest

        with pytest.raises(ValueError, match="already exists"):
            add_keyword(config, "infrastructure", "Metro")

    def test_case_insensitive_category_lookup(self):
        """add_keyword finds category with different casing."""
        config = _make_config()
        result = add_keyword(config, "Infrastructure", "bullet train")
        assert "bullet train" in result.categories["infrastructure"].keywords


class TestRemoveKeyword:
    """Tests for remove_keyword pure mutation function."""

    def test_removes_keyword_from_category(self):
        """remove_keyword removes the specified keyword."""
        config = _make_config()
        result = remove_keyword(config, "celebrity", "Salman Khan")
        assert "Salman Khan" not in result.categories["celebrity"].keywords
        assert len(result.categories["celebrity"].keywords) == 1

    def test_returns_new_config_immutably(self):
        """remove_keyword returns new KeywordsConfig, does not mutate original."""
        config = _make_config()
        result = remove_keyword(config, "celebrity", "Salman Khan")
        assert result is not config
        assert "Salman Khan" in config.categories["celebrity"].keywords

    def test_raises_on_unknown_category(self):
        """remove_keyword raises ValueError for non-existent category."""
        config = _make_config()
        import pytest

        with pytest.raises(ValueError, match="Unknown category"):
            remove_keyword(config, "nonexistent", "test")

    def test_raises_on_keyword_not_found(self):
        """remove_keyword raises ValueError for keyword not in category."""
        config = _make_config()
        import pytest

        with pytest.raises(ValueError, match="not found"):
            remove_keyword(config, "infrastructure", "nonexistent keyword")

    def test_case_insensitive_category_and_keyword(self):
        """remove_keyword matches category and keyword case-insensitively."""
        config = _make_config()
        result = remove_keyword(config, "Celebrity", "salman khan")
        assert len(result.categories["celebrity"].keywords) == 1


class TestSerializeKeywords:
    """Tests for serialize_keywords — YAML round-trip."""

    def test_produces_valid_yaml(self):
        """serialize_keywords output is valid YAML."""
        config = _make_config()
        result = serialize_keywords(config)
        parsed = yaml.safe_load(result)
        assert "categories" in parsed

    def test_round_trips_through_keywords_config(self):
        """serialize_keywords output can be parsed back into KeywordsConfig."""
        config = _make_config()
        result = serialize_keywords(config)
        parsed = yaml.safe_load(result)
        restored = KeywordsConfig(**parsed)
        assert (
            restored.categories["infrastructure"].keywords
            == config.categories["infrastructure"].keywords
        )
        assert restored.exclusions == config.exclusions

    def test_preserves_active_status(self):
        """serialize_keywords preserves active/inactive boolean per category."""
        config = _make_config()
        result = serialize_keywords(config)
        parsed = yaml.safe_load(result)
        assert parsed["categories"]["infrastructure"]["active"] is True
        assert parsed["categories"]["celebrity"]["active"] is False


# --- Task 2: Display, handlers, and patterns ---

_SAMPLE_YAML = """
categories:
  infrastructure:
    active: true
    keywords:
      - metro
      - highway
  celebrity:
    active: false
    keywords:
      - Salman Khan
exclusions:
  - obituary
  - scandal
""".strip()


def _make_update_context():
    """Create mock Update and context objects for handler testing."""
    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    return update, context


class TestFormatKeywordsDisplay:
    """Tests for format_keywords_display pure function."""

    def test_shows_category_names(self):
        """Display includes category names."""
        result = format_keywords_display(_SAMPLE_YAML)
        assert "infrastructure" in result.lower()
        assert "celebrity" in result.lower()

    def test_shows_active_inactive_status(self):
        """Display shows ACTIVE/INACTIVE status per category."""
        result = format_keywords_display(_SAMPLE_YAML)
        assert "ACTIVE" in result
        assert "INACTIVE" in result

    def test_shows_keywords(self):
        """Display includes actual keywords."""
        result = format_keywords_display(_SAMPLE_YAML)
        assert "metro" in result
        assert "highway" in result
        assert "Salman Khan" in result

    def test_includes_exclusions(self):
        """Display includes exclusions section."""
        result = format_keywords_display(_SAMPLE_YAML)
        assert "obituary" in result
        assert "scandal" in result


class TestKeywordsCommand:
    """Tests for /keywords command handler."""

    def test_replies_with_formatted_keywords(self, monkeypatch):
        """/keywords reads from GitHub and replies with formatted text."""
        monkeypatch.setenv("GITHUB_PAT", "tok")
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.setenv("GITHUB_REPO", "repo")
        update, context = _make_update_context()

        with patch(
            "pipeline.bot.keywords.read_github_file",
            new_callable=AsyncMock,
        ) as mock_read:
            mock_read.return_value = _SAMPLE_YAML
            asyncio.run(keywords_command(update, context))

        reply = update.message.reply_text.call_args[0][0]
        assert "infrastructure" in reply.lower()
        assert "metro" in reply

    def test_replies_error_on_github_failure(self, monkeypatch):
        """/keywords replies with error when GitHub API fails."""
        monkeypatch.setenv("GITHUB_PAT", "tok")
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.setenv("GITHUB_REPO", "repo")
        update, context = _make_update_context()

        with patch(
            "pipeline.bot.keywords.read_github_file",
            new_callable=AsyncMock,
        ) as mock_read:
            mock_read.side_effect = Exception("API error")
            asyncio.run(keywords_command(update, context))

        reply = update.message.reply_text.call_args[0][0]
        assert "failed" in reply.lower() or "error" in reply.lower()


class TestAddKeywordHandler:
    """Tests for add_keyword_handler text command."""

    def _make_context_with_match(self, text):
        """Create context with regex match for add pattern."""
        update, context = _make_update_context()
        update.message.text = text
        match = ADD_PATTERN.search(text)
        context.match = match
        return update, context

    def test_adds_keyword_to_default_infrastructure(self, monkeypatch):
        """'add keyword: bullet train' adds to infrastructure."""
        monkeypatch.setenv("GITHUB_PAT", "tok")
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.setenv("GITHUB_REPO", "repo")
        update, context = self._make_context_with_match("add keyword: bullet train")

        with (
            patch(
                "pipeline.bot.keywords.read_github_file_with_sha",
                new_callable=AsyncMock,
            ) as mock_read,
            patch(
                "pipeline.bot.keywords.write_github_file",
                new_callable=AsyncMock,
            ) as mock_write,
        ):
            mock_read.return_value = (_SAMPLE_YAML, "sha123")
            mock_write.return_value = True
            asyncio.run(add_keyword_handler(update, context))

        reply = update.message.reply_text.call_args[0][0]
        assert "bullet train" in reply.lower()
        assert "infrastructure" in reply.lower()

    def test_adds_keyword_to_named_category(self, monkeypatch):
        """'add celebrity: Priyanka Chopra' adds to celebrity category."""
        monkeypatch.setenv("GITHUB_PAT", "tok")
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.setenv("GITHUB_REPO", "repo")
        update, context = self._make_context_with_match("add celebrity: Priyanka Chopra")

        with (
            patch(
                "pipeline.bot.keywords.read_github_file_with_sha",
                new_callable=AsyncMock,
            ) as mock_read,
            patch(
                "pipeline.bot.keywords.write_github_file",
                new_callable=AsyncMock,
            ) as mock_write,
        ):
            mock_read.return_value = (_SAMPLE_YAML, "sha123")
            mock_write.return_value = True
            asyncio.run(add_keyword_handler(update, context))

        reply = update.message.reply_text.call_args[0][0]
        assert "priyanka chopra" in reply.lower()
        assert "celebrity" in reply.lower()

    def test_replies_error_on_unknown_category(self, monkeypatch):
        """add_keyword_handler replies with error for unknown category."""
        monkeypatch.setenv("GITHUB_PAT", "tok")
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.setenv("GITHUB_REPO", "repo")
        update, context = self._make_context_with_match("add nonexistent: test keyword")

        with patch(
            "pipeline.bot.keywords.read_github_file_with_sha",
            new_callable=AsyncMock,
        ) as mock_read:
            mock_read.return_value = (_SAMPLE_YAML, "sha123")
            asyncio.run(add_keyword_handler(update, context))

        reply = update.message.reply_text.call_args[0][0]
        assert "error" in reply.lower() or "unknown" in reply.lower()

    def test_replies_error_on_duplicate(self, monkeypatch):
        """add_keyword_handler replies with error for duplicate keyword."""
        monkeypatch.setenv("GITHUB_PAT", "tok")
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.setenv("GITHUB_REPO", "repo")
        update, context = self._make_context_with_match("add infrastructure: metro")

        with patch(
            "pipeline.bot.keywords.read_github_file_with_sha",
            new_callable=AsyncMock,
        ) as mock_read:
            mock_read.return_value = (_SAMPLE_YAML, "sha123")
            asyncio.run(add_keyword_handler(update, context))

        reply = update.message.reply_text.call_args[0][0]
        assert "error" in reply.lower() or "already" in reply.lower()


class TestRemoveKeywordHandler:
    """Tests for remove_keyword_handler text command."""

    def _make_context_with_match(self, text):
        """Create context with regex match for remove pattern."""
        update, context = _make_update_context()
        update.message.text = text
        match = REMOVE_PATTERN.search(text)
        context.match = match
        return update, context

    def test_removes_keyword_from_category(self, monkeypatch):
        """'remove celebrity: Salman Khan' removes keyword."""
        monkeypatch.setenv("GITHUB_PAT", "tok")
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.setenv("GITHUB_REPO", "repo")
        update, context = self._make_context_with_match("remove celebrity: Salman Khan")

        with (
            patch(
                "pipeline.bot.keywords.read_github_file_with_sha",
                new_callable=AsyncMock,
            ) as mock_read,
            patch(
                "pipeline.bot.keywords.write_github_file",
                new_callable=AsyncMock,
            ) as mock_write,
        ):
            mock_read.return_value = (_SAMPLE_YAML, "sha123")
            mock_write.return_value = True
            asyncio.run(remove_keyword_handler(update, context))

        reply = update.message.reply_text.call_args[0][0]
        assert "salman khan" in reply.lower()
        assert "removed" in reply.lower()

    def test_replies_error_on_not_found(self, monkeypatch):
        """remove_keyword_handler replies with error when keyword not found."""
        monkeypatch.setenv("GITHUB_PAT", "tok")
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.setenv("GITHUB_REPO", "repo")
        update, context = self._make_context_with_match("remove infrastructure: nonexistent")

        with patch(
            "pipeline.bot.keywords.read_github_file_with_sha",
            new_callable=AsyncMock,
        ) as mock_read:
            mock_read.return_value = (_SAMPLE_YAML, "sha123")
            asyncio.run(remove_keyword_handler(update, context))

        reply = update.message.reply_text.call_args[0][0]
        assert "error" in reply.lower() or "not found" in reply.lower()


class TestPatterns:
    """Tests for ADD_PATTERN and REMOVE_PATTERN regex matching."""

    def test_add_pattern_matches_add_keyword(self):
        """ADD_PATTERN matches 'add keyword: X'."""
        m = ADD_PATTERN.search("add keyword: bullet train")
        assert m is not None
        assert m.group(2).strip() == "bullet train"
        # group(1) is None when 'keyword' is the word used
        assert m.group(1) is None

    def test_add_pattern_matches_add_category(self):
        """ADD_PATTERN matches 'add infrastructure: X'."""
        m = ADD_PATTERN.search("add infrastructure: bullet train")
        assert m is not None
        assert m.group(1) == "infrastructure"
        assert m.group(2).strip() == "bullet train"

    def test_add_pattern_case_insensitive(self):
        """ADD_PATTERN matches 'Add Celebrity: X'."""
        m = ADD_PATTERN.search("Add Celebrity: Priyanka Chopra")
        assert m is not None
        assert m.group(1) == "Celebrity"

    def test_remove_pattern_matches(self):
        """REMOVE_PATTERN matches 'remove celebrity: X'."""
        m = REMOVE_PATTERN.search("remove celebrity: Salman Khan")
        assert m is not None
        assert m.group(1) == "celebrity"
        assert m.group(2).strip() == "Salman Khan"

    def test_remove_pattern_case_insensitive(self):
        """REMOVE_PATTERN matches 'Remove Regulatory: X'."""
        m = REMOVE_PATTERN.search("Remove Regulatory: RERA")
        assert m is not None
        assert m.group(1) == "Regulatory"
