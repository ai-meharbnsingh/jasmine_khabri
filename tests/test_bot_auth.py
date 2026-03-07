"""Authorization guard tests for Telegram bot.

TDD Phase 8 Plan 02 — tests for load_authorized_users from AUTHORIZED_USER_IDS env var.
"""

from pipeline.bot.auth import load_authorized_users


class TestLoadAuthorizedUsersUnset:
    """Tests when AUTHORIZED_USER_IDS env var is not set."""

    def test_returns_empty_set_when_unset(self, monkeypatch):
        """Returns empty set when AUTHORIZED_USER_IDS is not in environment."""
        monkeypatch.delenv("AUTHORIZED_USER_IDS", raising=False)
        result = load_authorized_users()
        assert result == set()
        assert isinstance(result, set)


class TestLoadAuthorizedUsersEmpty:
    """Tests when AUTHORIZED_USER_IDS env var is empty string."""

    def test_returns_empty_set_when_empty(self, monkeypatch):
        """Returns empty set when AUTHORIZED_USER_IDS is empty string."""
        monkeypatch.setenv("AUTHORIZED_USER_IDS", "")
        result = load_authorized_users()
        assert result == set()


class TestLoadAuthorizedUsersParsing:
    """Tests for parsing comma-separated user IDs."""

    def test_parses_two_ids(self, monkeypatch):
        """Parses '123,456' into {123, 456}."""
        monkeypatch.setenv("AUTHORIZED_USER_IDS", "123,456")
        result = load_authorized_users()
        assert result == {123, 456}

    def test_strips_whitespace(self, monkeypatch):
        """Strips whitespace from segments: ' 123 , 456 ' -> {123, 456}."""
        monkeypatch.setenv("AUTHORIZED_USER_IDS", " 123 , 456 ")
        result = load_authorized_users()
        assert result == {123, 456}

    def test_ignores_empty_segments(self, monkeypatch):
        """Ignores empty segments from consecutive commas: '123,,456' -> {123, 456}."""
        monkeypatch.setenv("AUTHORIZED_USER_IDS", "123,,456")
        result = load_authorized_users()
        assert result == {123, 456}

    def test_single_id(self, monkeypatch):
        """Parses single ID without comma."""
        monkeypatch.setenv("AUTHORIZED_USER_IDS", "789")
        result = load_authorized_users()
        assert result == {789}
