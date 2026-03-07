"""GitHub repository_dispatch trigger for on-demand pipeline runs.

Sends a repository_dispatch event to GitHub Actions via the REST API.
Used by the /run bot command to trigger pipeline runs from Telegram.
"""

import logging

import httpx

logger = logging.getLogger(__name__)


async def trigger_pipeline(token: str, owner: str, repo: str) -> bool:
    """Trigger a pipeline run via GitHub repository_dispatch.

    POSTs to the GitHub dispatches endpoint with event_type "run_now".
    The deliver.yml workflow has a repository_dispatch trigger that picks this up.

    Args:
        token: GitHub fine-grained PAT with Contents/Actions write scope.
        owner: Repository owner username.
        repo: Repository name.

    Returns:
        True if GitHub responded with 204 No Content (success), False otherwise.
        Never raises — catches all exceptions and returns False.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/dispatches"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {token}",
    }
    payload = {
        "event_type": "run_now",
        "client_payload": {"triggered_by": "telegram_bot"},
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            return resp.status_code == 204
    except Exception:
        logger.warning("Failed to trigger repository_dispatch", exc_info=True)
        return False
