"""Tests for GitHub Contents API writer — read-with-SHA and write-file.

TDD Phase 9 Plan 01 — Task 1 RED phase.
Uses respx for HTTP mocking, asyncio.run() for async tests.
"""

import asyncio
import base64

import httpx
import pytest
import respx

from pipeline.bot.github import read_github_file_with_sha, write_github_file

CONTENTS_URL = "https://api.github.com/repos/owner/repo/contents/data/keywords.yaml"


class TestReadGithubFileWithSha:
    """Tests for read_github_file_with_sha — JSON mode to get content + SHA."""

    def test_returns_content_and_sha_on_200(self):
        """Returns (decoded_content, sha) tuple on successful 200."""
        raw_content = "categories:\n  infrastructure:\n    active: true\n"
        encoded = base64.b64encode(raw_content.encode()).decode()
        payload = {"content": encoded, "sha": "abc123def456", "encoding": "base64"}

        with respx.mock:
            respx.get(CONTENTS_URL).respond(200, json=payload)
            content, sha = asyncio.run(
                read_github_file_with_sha("data/keywords.yaml", "tok", "owner", "repo")
            )

        assert content == raw_content
        assert sha == "abc123def456"

    def test_raises_on_404(self):
        """Raises httpx.HTTPStatusError on 404 Not Found."""
        with respx.mock:
            respx.get(CONTENTS_URL).respond(404, json={"message": "Not Found"})
            with pytest.raises(httpx.HTTPStatusError):
                asyncio.run(read_github_file_with_sha("data/keywords.yaml", "tok", "owner", "repo"))

    def test_raises_on_500(self):
        """Raises httpx.HTTPStatusError on 500 Internal Server Error."""
        with respx.mock:
            respx.get(CONTENTS_URL).respond(500, json={"message": "Server Error"})
            with pytest.raises(httpx.HTTPStatusError):
                asyncio.run(read_github_file_with_sha("data/keywords.yaml", "tok", "owner", "repo"))


class TestWriteGithubFile:
    """Tests for write_github_file — PUT to Contents API."""

    def test_returns_true_on_200(self):
        """Returns True when GitHub responds with 200 (update)."""
        with respx.mock:
            respx.put(CONTENTS_URL).respond(200, json={"content": {}})
            result = asyncio.run(
                write_github_file(
                    "data/keywords.yaml",
                    "new content",
                    "bot: update",
                    "sha123",
                    "tok",
                    "owner",
                    "repo",
                )
            )
        assert result is True

    def test_returns_true_on_201(self):
        """Returns True when GitHub responds with 201 (create)."""
        with respx.mock:
            respx.put(CONTENTS_URL).respond(201, json={"content": {}})
            result = asyncio.run(
                write_github_file(
                    "data/keywords.yaml",
                    "new content",
                    "bot: create",
                    "sha123",
                    "tok",
                    "owner",
                    "repo",
                )
            )
        assert result is True

    def test_returns_false_on_api_error(self):
        """Returns False (not raises) when API returns 422."""
        with respx.mock:
            respx.put(CONTENTS_URL).respond(422, json={"message": "Validation failed"})
            result = asyncio.run(
                write_github_file(
                    "data/keywords.yaml", "content", "msg", "sha123", "tok", "owner", "repo"
                )
            )
        assert result is False

    def test_returns_false_on_network_error(self):
        """Returns False on network-level exception."""
        with respx.mock:
            respx.put(CONTENTS_URL).mock(side_effect=httpx.ConnectError("timeout"))
            result = asyncio.run(
                write_github_file(
                    "data/keywords.yaml", "content", "msg", "sha123", "tok", "owner", "repo"
                )
            )
        assert result is False

    def test_sends_base64_encoded_content(self):
        """PUT body contains base64-encoded content, sha, and message."""
        with respx.mock:
            route = respx.put(CONTENTS_URL).respond(200, json={"content": {}})
            asyncio.run(
                write_github_file(
                    "data/keywords.yaml",
                    "hello world",
                    "bot: test",
                    "sha789",
                    "tok",
                    "owner",
                    "repo",
                )
            )
            request = route.calls[0].request
            import json

            body = json.loads(request.content)
            assert body["message"] == "bot: test"
            assert body["sha"] == "sha789"
            decoded = base64.b64decode(body["content"]).decode()
            assert decoded == "hello world"
