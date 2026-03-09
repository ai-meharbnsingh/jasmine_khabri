"""Article priority classifier using Gemini/Claude.

Classifies batched articles as HIGH/MEDIUM/LOW priority using Gemini 2.5 Flash
as primary AI provider (free tier), with automatic Claude Haiku 4.5 fallback.
Includes writer-focused impact summaries and structured entity extraction.

Budget gate at $4.75/month degrades to keyword-only scoring.
"""

import logging
import os
from typing import Literal

import anthropic
from google import genai

from pipeline.analyzers.cost_tracker import check_budget, record_cost
from pipeline.schemas.ai_cost_schema import AICost
from pipeline.schemas.ai_response_schema import (
    ArticleAnalysis,
    BatchClassificationResponse,
)
from pipeline.schemas.article_schema import Article

logger = logging.getLogger(__name__)

# Model constants
CLAUDE_MODEL = "claude-haiku-4-5"
GEMINI_MODEL = "gemini-2.5-flash"

# Truncation limits
TITLE_MAX_CHARS = 200
SUMMARY_MAX_CHARS = 500

SYSTEM_PROMPT = """\
You are an expert Indian infrastructure and real estate news classifier \
for Magic Bricks content writers.

Your task: classify each article as HIGH, MEDIUM, or LOW priority, write a \
2-line writer-focused impact summary, and extract key entities.

## Classification Criteria

HIGH priority — articles with ANY of:
- Policy/regulatory impact: RERA changes, PMAY updates, metro approvals, \
highway sanctions, stamp duty revisions, interest rate changes
- Major project milestones: metro line approvals, airport expansions, \
smart city awards, large land deals, new SEZ announcements
- Market-moving events: celebrity real estate transactions, large builder \
announcements, major FDI in real estate, IPO filings by real estate companies

MEDIUM priority — articles with:
- Progress updates on known projects: construction milestones, tender awards, \
deadline extensions, phase completion announcements
- Regional/Tier 2-3 developments: new industrial corridors, smart city \
progress updates, local RERA actions, state-level policy changes
- Infrastructure connectivity: new highway stretches, railway station \
upgrades, bus rapid transit updates

LOW priority — catch-all:
- Industry commentary, expert opinions, market forecasts
- Routine operational news, standard compliance updates
- General real estate trends without specific project or policy impact
- Listicles, opinion pieces, sponsored content

## Summary Style

Write exactly 2 lines per article. Summaries must be writer-focused impact \
briefs for Magic Bricks content writers — answer "why this matters for your \
next article", NOT generic news summaries.

Good example: "Delhi Metro Phase 4 approval unlocks 3 new corridor stories \
for NCR real estate coverage. Budget: Rs 46,000 crore."

Bad example: "The cabinet has approved Phase 4 of Delhi Metro."

## Entity Extraction

Extract these four entities from each article:
- location: city, state, or region mentioned (e.g., "Delhi", "Maharashtra", \
"NCR"). Empty string if not found.
- project_name: specific project or government scheme name (e.g., \
"Delhi Metro Phase 4", "PMAY-Urban"). Empty string if not found.
- budget: monetary figure with currency (e.g., "Rs 46,000 crore", \
"$2.5 billion"). Empty string if not found.
- authority: government body or organization driving the action (e.g., \
"Cabinet Committee", "Maharashtra RERA", "NHAI"). Empty string if not found.

## Output Format

Return a JSON object with an "articles" array. Each article object must have:
- index: integer matching the article number (0-based)
- priority: "HIGH", "MEDIUM", or "LOW"
- summary: exactly 2-line writer-focused impact summary
- location: extracted location or empty string
- project_name: extracted project name or empty string
- budget: extracted budget figure or empty string
- authority: extracted authority or empty string
"""


def build_articles_text(articles: list[Article]) -> str:
    """Format articles as numbered text for the AI prompt.

    Truncates title at 200 chars and summary at 500 chars to optimize
    input token usage.
    """
    parts: list[str] = []
    truncated_count = 0

    for i, article in enumerate(articles):
        title = article.title[:TITLE_MAX_CHARS]
        summary = article.summary[:SUMMARY_MAX_CHARS]

        if len(article.title) > TITLE_MAX_CHARS or len(article.summary) > SUMMARY_MAX_CHARS:
            truncated_count += 1

        parts.append(
            f"Article {i}:\nTitle: {title}\nSource: {article.source}\nSummary: {summary}\n"
        )

    if truncated_count > 0:
        logger.info(
            "Truncated %d article(s) for AI prompt (title>%d or summary>%d chars)",
            truncated_count,
            TITLE_MAX_CHARS,
            SUMMARY_MAX_CHARS,
        )

    return "\n".join(parts)


def _classify_with_claude(
    articles_text: str,
) -> tuple[BatchClassificationResponse | None, dict]:
    """Classify articles using Claude Haiku with structured output.

    Returns (parsed_output, usage_dict) or (None, {}) on any failure.
    """
    try:
        client = anthropic.Anthropic()

        response = client.messages.parse(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": articles_text}],
            output_format=BatchClassificationResponse,
        )

        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cache_creation_input_tokens": getattr(
                response.usage, "cache_creation_input_tokens", 0
            ),
            "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0),
        }

        # Per Research Pitfall 4: check stop_reason and parsed_output
        if response.stop_reason != "end_turn" or response.parsed_output is None:
            logger.warning(
                "Claude response invalid: stop_reason=%s, parsed_output=%s",
                response.stop_reason,
                "None" if response.parsed_output is None else "present",
            )
            return (None, {})

        return (response.parsed_output, usage)

    except Exception:
        logger.exception("Claude classification failed")
        return (None, {})


def _classify_with_gemini(
    articles_text: str,
) -> tuple[BatchClassificationResponse | None, dict]:
    """Classify articles using Gemini Flash as fallback.

    Uses GOOGLE_API_KEY env var (not GEMINI_API_KEY) per project convention.
    Returns (parsed_output, usage_dict) or (None, {}) on any failure.
    """
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        logger.warning("GOOGLE_API_KEY not set -- Gemini fallback unavailable")
        return (None, {})

    try:
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=f"{SYSTEM_PROMPT}\n\n{articles_text}",
            config={
                "response_mime_type": "application/json",
                "response_json_schema": (BatchClassificationResponse.model_json_schema()),
            },
        )

        result = BatchClassificationResponse.model_validate_json(response.text)

        usage = {
            "input_tokens": getattr(response.usage_metadata, "prompt_token_count", 0),
            "output_tokens": getattr(response.usage_metadata, "candidates_token_count", 0),
        }

        return (result, usage)

    except Exception:
        logger.exception("Gemini classification failed")
        return (None, {})


def _apply_keyword_fallback(articles: list[Article]) -> list[Article]:
    """Map relevance_score to priority when AI is unavailable.

    Uses dynamic curve grading — divides the batch's score range into
    3 equal bands so articles always get distributed across priorities
    regardless of absolute score levels.

    No summary or entities populated.
    """
    if not articles:
        return []

    scores = [a.relevance_score for a in articles]
    max_score = max(scores)
    min_score = min(scores)
    score_range = max_score - min_score

    if score_range == 0:
        # All identical scores — treat as MEDIUM
        return [a.model_copy(update={"priority": "MEDIUM"}) for a in articles]

    band = score_range / 3
    high_threshold = max_score - band  # top 1/3
    medium_threshold = max_score - 2 * band  # top 2/3

    logger.info(
        "Keyword fallback dynamic bands: HIGH>=%.1f, MEDIUM>=%.1f (scores %d-%d)",
        high_threshold,
        medium_threshold,
        min_score,
        max_score,
    )

    results: list[Article] = []
    for article in articles:
        if article.relevance_score >= high_threshold:
            priority: Literal["HIGH", "MEDIUM", "LOW"] = "HIGH"
        elif article.relevance_score >= medium_threshold:
            priority = "MEDIUM"
        else:
            priority = "LOW"
        results.append(article.model_copy(update={"priority": priority}))

    return results


def _apply_medium_fallback(article: Article) -> Article:
    """Apply MEDIUM default when both AI providers fail."""
    return article.model_copy(
        update={
            "priority": "MEDIUM",
            "summary": "",
            "location": "",
            "project_name": "",
            "budget_amount": "",
            "authority": "",
        }
    )


def classify_articles(articles: list[Article], ai_cost: AICost) -> tuple[list[Article], AICost]:
    """Classify articles using Claude (primary) with Gemini fallback.

    Budget gate at $4.75 degrades to keyword-only scoring.
    Both-fail fallback assigns priority='MEDIUM' with empty summary/entities.

    Args:
        articles: List of articles to classify.
        ai_cost: Current month's AI cost state.

    Returns:
        Tuple of (classified_articles, updated_ai_cost).
    """
    if not articles:
        return ([], ai_cost)

    # Budget gate
    budget_status = check_budget(ai_cost)
    if budget_status == "exceeded":
        logger.warning(
            "AI budget exceeded ($%.2f >= $4.75) -- using keyword-only scoring",
            ai_cost.total_cost_usd,
        )
        degraded = _apply_keyword_fallback(articles)
        return (degraded, ai_cost)

    if budget_status == "warning":
        logger.warning(
            "AI budget warning ($%.2f >= $4.00) -- proceeding with AI call",
            ai_cost.total_cost_usd,
        )

    # Build prompt text
    articles_text = build_articles_text(articles)

    # Try Gemini first (free tier)
    provider = "gemini"
    result, usage = _classify_with_gemini(articles_text)

    # Fallback to Claude if Gemini failed
    if result is None:
        logger.info("Gemini failed -- attempting Claude fallback")
        provider = "claude"
        result, usage = _classify_with_claude(articles_text)

    # Both failed: apply MEDIUM default
    if result is None:
        logger.warning(
            "Both Claude and Gemini failed -- applying MEDIUM default to %d articles",
            len(articles),
        )
        fallback = [_apply_medium_fallback(a) for a in articles]
        return (fallback, ai_cost)

    # Map AI response back to articles
    analysis_by_index: dict[int, ArticleAnalysis] = {a.index: a for a in result.articles}

    classified: list[Article] = []
    for i, article in enumerate(articles):
        analysis = analysis_by_index.get(i)
        if analysis is None:
            # Index mismatch: unmatched articles get MEDIUM
            classified.append(article.model_copy(update={"priority": "MEDIUM"}))
        else:
            classified.append(
                article.model_copy(
                    update={
                        "priority": analysis.priority,
                        "summary": analysis.summary,
                        "location": analysis.location,
                        "project_name": analysis.project_name,
                        "budget_amount": analysis.budget,
                        "authority": analysis.authority,
                    }
                )
            )

    # Record cost
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    ai_cost = record_cost(ai_cost, input_tokens, output_tokens, provider)

    # Log classification summary
    counts: dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for a in classified:
        if a.priority in counts:
            counts[a.priority] += 1
    logger.info(
        "Classification complete: %d HIGH, %d MEDIUM, %d LOW",
        counts["HIGH"],
        counts["MEDIUM"],
        counts["LOW"],
    )

    return (classified, ai_cost)
