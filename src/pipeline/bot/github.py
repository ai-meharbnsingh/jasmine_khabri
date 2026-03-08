"""GitHub Contents API read-with-SHA and write-file functions.

Provides the write capability for keyword management commands.
The existing read_github_file in status.py uses raw mode (no SHA).
These functions use JSON mode to access the SHA needed for PUT updates.
"""

import base64
import logging

import httpx

logger = logging.getLogger(__name__)


async def read_github_file_with_sha(
    path: str, token: str, owner: str, repo: str
) -> tuple[str, str]:
    """Read a file from GitHub via Contents API, returning content and SHA.

    Uses JSON mode (not raw) to get both the file content and its SHA,
    which is required for subsequent PUT (update) operations.

    Args:
        path: File path within the repo (e.g. "data/keywords.yaml").
        token: GitHub fine-grained PAT with Contents read scope.
        owner: Repository owner username.
        repo: Repository name.

    Returns:
        Tuple of (decoded_content, sha).

    Raises:
        httpx.HTTPStatusError: On non-2xx responses.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {token}",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        content = base64.b64decode(data["content"]).decode()
        sha = data["sha"]
        return content, sha


async def write_github_file(
    path: str,
    content: str,
    message: str,
    sha: str,
    token: str,
    owner: str,
    repo: str,
) -> bool:
    """Write (create or update) a file in a GitHub repository via Contents API.

    Encodes content as base64 and PUTs to the Contents endpoint.
    Requires the current SHA of the file for update operations.

    Args:
        path: File path within the repo (e.g. "data/keywords.yaml").
        content: New file content as string.
        message: Git commit message.
        sha: Current SHA of the file (from read_github_file_with_sha).
        token: GitHub fine-grained PAT with Contents write scope.
        owner: Repository owner username.
        repo: Repository name.

    Returns:
        True on 200/201 (success), False on any error.
        Never raises — catches all exceptions and logs warning.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {token}",
    }
    encoded = base64.b64encode(content.encode()).decode()
    payload = {
        "message": message,
        "content": encoded,
        "sha": sha,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.put(url, headers=headers, json=payload)
            return resp.status_code in (200, 201)
    except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError):
        logger.warning("Failed to write file to GitHub: %s", path, exc_info=True)
        return False
