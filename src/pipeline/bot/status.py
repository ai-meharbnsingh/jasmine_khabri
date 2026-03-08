"""GitHub Contents API reader for pipeline status and AI cost.

Reads pipeline_status.json and ai_cost.json from the GitHub repo via the Contents API.
Used by the /status bot command to display pipeline health and usage.
"""

import json
import logging
import os

import httpx

from pipeline.schemas.ai_cost_schema import AICost
from pipeline.schemas.pipeline_status_schema import PipelineStatus

logger = logging.getLogger(__name__)


async def read_github_file(path: str, token: str, owner: str, repo: str) -> str:
    """Read a raw file from a GitHub repository via the Contents API.

    Args:
        path: File path within the repo (e.g. "data/pipeline_status.json").
        token: GitHub fine-grained PAT with Contents read scope.
        owner: Repository owner username.
        repo: Repository name.

    Returns:
        Raw file content as string.

    Raises:
        httpx.HTTPStatusError: On non-2xx responses.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {
        "Accept": "application/vnd.github.raw+json",
        "Authorization": f"Bearer {token}",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.text


async def fetch_pipeline_status() -> PipelineStatus:
    """Fetch pipeline status from GitHub repo.

    Reads GITHUB_PAT, GITHUB_OWNER, GITHUB_REPO from env vars.
    Calls read_github_file for data/pipeline_status.json and parses into PipelineStatus.

    On ANY exception (missing env vars, API error, parse error), logs warning
    and returns default PipelineStatus. Never crashes.

    Returns:
        PipelineStatus with current pipeline health data, or defaults on failure.
    """
    try:
        token = os.environ.get("GITHUB_PAT", "")
        owner = os.environ.get("GITHUB_OWNER", "")
        repo = os.environ.get("GITHUB_REPO", "")

        if not token or not owner or not repo:
            logger.warning("GitHub env vars (GITHUB_PAT, GITHUB_OWNER, GITHUB_REPO) not fully set")
            return PipelineStatus()

        raw = await read_github_file("data/pipeline_status.json", token, owner, repo)
        data = json.loads(raw)
        return PipelineStatus(**data)
    except Exception:
        logger.warning("Failed to fetch pipeline status from GitHub", exc_info=True)
        return PipelineStatus()


async def fetch_ai_cost() -> AICost:
    """Fetch AI cost data from GitHub repo.

    Reads GITHUB_PAT, GITHUB_OWNER, GITHUB_REPO from env vars.
    Calls read_github_file for data/ai_cost.json and parses into AICost.

    On ANY exception (missing env vars, API error, parse error), logs warning
    and returns default AICost. Never crashes.

    Returns:
        AICost with current AI spend data, or defaults on failure.
    """
    try:
        token = os.environ.get("GITHUB_PAT", "")
        owner = os.environ.get("GITHUB_OWNER", "")
        repo = os.environ.get("GITHUB_REPO", "")

        if not token or not owner or not repo:
            return AICost(month="")

        raw = await read_github_file("data/ai_cost.json", token, owner, repo)
        data = json.loads(raw)
        return AICost(**data)
    except Exception:
        logger.warning("Failed to fetch AI cost from GitHub", exc_info=True)
        return AICost(month="")
