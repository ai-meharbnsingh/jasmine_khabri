# Phase 11: Breaking News and Production Hardening - Research

**Researched:** 2026-03-08
**Domain:** GitHub Actions cron workflows, cost tracking, breaking news alerting, production budget compliance
**Confidence:** HIGH

## Summary

Phase 11 completes the Khabri pipeline with two capabilities: (1) a breaking news alerting system that fires between the two scheduled deliveries (7 AM / 4 PM IST) to catch critical HIGH-priority stories, and (2) production hardening with free-tier usage tracking surfaced in the bot's /status command.

The breaking news workflow is a separate GitHub Actions workflow (`breaking.yml`) running on a cron schedule. The critical design constraint is cost: the system must stay within Railway $5/month, GitHub Actions 2000 free minutes/month (for private repos; unlimited for public), and $5/month AI API spend. The breaking news workflow MUST use a keyword-only fast-path for initial filtering, only calling the AI API when the keyword filter scores an article HIGH (relevance_score >= 80). This prevents burning AI budget on the frequent 30-60 minute checks.

The existing codebase provides all building blocks: `score_article()` in `relevance_filter.py` for keyword scoring, `filter_duplicates()` in `dedup_filter.py` for avoiding re-alerts, `send_telegram_message()` in `telegram_sender.py` for sending alerts, and `AICost`/`check_budget()` for cost tracking. The breaking news pipeline is a lightweight subset of `main.py` -- fetch, keyword-filter, dedup, optional AI confirm, send alert. No email delivery for breaking news (Telegram only for speed).

**Primary recommendation:** Build breaking news as a thin `breaking.py` entrypoint reusing existing modules, with a separate `breaking.yml` workflow on `*/30` cron. Track free-tier usage in `pipeline_status.json` (extend schema with Actions run count and estimated minutes). Surface usage percentages in /status.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DLVR-05 | System sends breaking news alerts for critical HIGH-priority stories between scheduled deliveries | Breaking news workflow (`breaking.yml` + `breaking.py`) with keyword-only fast-path, AI confirmation only for keyword-flagged HIGH articles, Telegram-only delivery, dedup against seen.json |
| INFRA-06 | System operates within free tier limits (Railway $5/month credit for bot, $0 GitHub Actions, <$5/month AI API) | Free-tier usage tracker schema, budget calculations showing feasibility, /status integration with usage percentages, breaking workflow designed to minimize AI calls |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | >=0.28.1 | HTTP client for RSS/GNews/Telegram API calls | Already in project, async + sync capable |
| feedparser | >=6.0.12 | RSS feed parsing | Already in project |
| pydantic | >=2.5 | Schema models for usage tracking | Already in project |
| PyYAML | >=6.0 | Config loading | Already in project |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| anthropic | >=0.84.0 | Claude Haiku for AI confirmation of HIGH articles | Only when keyword filter flags article as HIGH |
| google-genai | >=1.66.0 | Gemini fallback for AI confirmation | Only when Claude fails and article is keyword-HIGH |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Separate breaking.yml workflow | Run breaking check inside existing deliver.yml | Separate workflow gives independent cron, cleaner logs, independent failure isolation. Same workflow would couple breaking frequency to delivery schedule. Separate is better. |
| GitHub Actions cron | Railway-hosted polling script | Actions-based is free (public repo) or within free tier (private). Railway script would consume Railway credits. Actions is the right choice. |

**Installation:**
No new dependencies required. All needed libraries are already in `pyproject.toml`.

## Architecture Patterns

### Recommended Project Structure
```
src/pipeline/
  breaking.py          # NEW: Breaking news entrypoint (lightweight main.py subset)
  main.py              # Existing: Full pipeline (unchanged or minor additions)
  schemas/
    pipeline_status_schema.py  # EXTENDED: Add usage tracking fields
  bot/
    handler.py         # EXTENDED: /status shows usage percentages
.github/workflows/
  breaking.yml         # NEW: Breaking news cron workflow
  deliver.yml          # MINOR: Increment run counter in pipeline_status.json
```

### Pattern 1: Lightweight Breaking News Pipeline
**What:** A thin entrypoint `breaking.py` that reuses existing modules but skips the full pipeline (no GNews, no email, no full AI batch classification).
**When to use:** Every 30-60 minutes between scheduled deliveries.
**Example:**
```python
# Source: Derived from existing main.py and filter modules
def run_breaking() -> None:
    """Breaking news check -- lightweight subset of full pipeline."""
    # 1. Load state (seen.json, keywords.yaml, config.yaml, ai_cost.json)
    # 2. Check if breaking news is enabled (config.telegram.breaking_news_enabled)
    # 3. Check if deliveries are paused (bot_state.json)
    # 4. Fetch RSS only (no GNews -- save quota for scheduled runs)
    # 5. Keyword-only fast-path filter (score_article with threshold >=80 for HIGH)
    # 6. Dedup against seen.json (skip already-seen articles)
    # 7. If any articles pass: optionally confirm with AI (budget permitting)
    # 8. Send Telegram alert for confirmed HIGH articles
    # 9. Update seen.json with alerted articles
    # 10. Update pipeline_status.json with breaking run metadata
```

### Pattern 2: Two-Stage Breaking News Filter (Keyword Fast-Path + AI Confirm)
**What:** First stage uses keyword scoring (zero cost, instant). Second stage uses AI only for articles that pass keyword HIGH threshold.
**When to use:** Every breaking news check.
**Example:**
```python
# Source: Existing relevance_filter.py score_article function
from pipeline.filters.relevance_filter import score_article

def breaking_filter(articles, keywords, ai_cost):
    """Two-stage filter: keyword fast-path then optional AI confirm."""
    candidates = []
    for article in articles:
        passes_exclusion, score = score_article(article, keywords)
        if passes_exclusion and score >= 80:  # HIGH threshold from Phase 5 keyword fallback
            candidates.append(article.model_copy(update={"relevance_score": score}))

    if not candidates:
        return [], ai_cost

    # Stage 2: AI confirmation (only if budget allows)
    budget_status = check_budget(ai_cost)
    if budget_status == "exceeded":
        # Skip AI, trust keyword score
        return [a.model_copy(update={"priority": "HIGH"}) for a in candidates], ai_cost

    # Classify only candidates (not full batch)
    classified, ai_cost = classify_articles(candidates, ai_cost)
    return [a for a in classified if a.priority == "HIGH"], ai_cost
```

### Pattern 3: Free-Tier Usage Tracking
**What:** Extend PipelineStatus schema with usage tracking fields. Pipeline writes run metadata; bot reads and formats for /status.
**When to use:** Every pipeline run (deliver.yml and breaking.yml) increments counters; /status displays them.
**Example:**
```python
# Extended PipelineStatus schema
class PipelineStatus(BaseModel):
    # ... existing fields ...
    # New usage tracking fields
    monthly_deliver_runs: int = 0      # Full pipeline runs this month
    monthly_breaking_runs: int = 0     # Breaking checks this month
    monthly_actions_minutes_est: float = 0.0  # Estimated minutes used
    usage_month: str = ""              # "YYYY-MM" for monthly reset
```

### Pattern 4: Breaking News Alert Format
**What:** Simpler format than the full delivery brief -- just the critical article(s) with a "BREAKING" header.
**When to use:** When breaking news articles are found and confirmed HIGH.
**Example:**
```python
def format_breaking_alert(articles: list[Article]) -> str:
    """Format breaking news alert for Telegram."""
    lines = [
        "\U0001f6a8 <b>BREAKING NEWS ALERT</b>",
        f"{len(articles)} critical {'story' if len(articles) == 1 else 'stories'}",
        "\u2500" * 24,
    ]
    for i, article in enumerate(articles, 1):
        lines.append(f"\n{i}. <b>{_escape_html(article.title)}</b>")
        lines.append(f"   <i>{_escape_html(article.source)}</i>")
        if article.summary:
            lines.append(f"   {_escape_html(article.summary)}")
        lines.append(f'   <a href="{_escape_html(article.url)}">Read</a>')
    lines.append(f"\n{'='*24}")
    lines.append("Full brief in next scheduled delivery")
    return "\n".join(lines)
```

### Anti-Patterns to Avoid
- **Running full pipeline for breaking news:** The full pipeline fetches GNews (uses quota), runs full AI batch, sends email. Breaking news must be RSS-only, keyword-first, Telegram-only.
- **Calling AI for every breaking check:** 48 checks/day x 15 articles x AI cost would blow the $5 budget. Keyword filter MUST gate AI calls.
- **Separate seen.json for breaking news:** Must share the same seen.json to avoid re-alerting on articles that were already delivered in scheduled runs.
- **Ignoring pause state:** Breaking news must respect pause/resume state from bot_state.json.
- **Sending breaking alerts during scheduled delivery windows:** The breaking check should skip if it's within the scheduled delivery window (e.g., 6:30-7:30 AM or 3:30-4:30 PM IST) to avoid duplicate alerts.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Article scoring | Custom breaking-specific scorer | Existing `score_article()` from `relevance_filter.py` | Already battle-tested with 120+ tests, handles exclusions and all keyword categories |
| Deduplication | Breaking-specific dedup | Existing `filter_duplicates()` from `dedup_filter.py` | Same seen.json, same hash logic, prevents re-alerts |
| Telegram sending | New send function | Existing `send_telegram_message()` from `telegram_sender.py` | Retry logic, rate limiting, error handling all built |
| AI classification | Stripped-down classifier | Existing `classify_articles()` from `classifier.py` | Budget gates, provider fallback, cost tracking all built |
| Cost tracking | Manual token counting | Existing `record_cost()` and `check_budget()` from `cost_tracker.py` | Handles both providers, monthly reset, budget thresholds |
| GitHub file I/O | Direct API calls | Existing `read_github_file()` from `status.py` and `read_github_file_with_sha`/`write_github_file` from `github.py` | SHA handling, error recovery, auth patterns established |

**Key insight:** The breaking news pipeline is architecturally a *subset* of the existing main.py pipeline with a different filter threshold and different delivery format. Almost all modules can be reused directly.

## Common Pitfalls

### Pitfall 1: GitHub Actions Minutes Budget Overrun
**What goes wrong:** Breaking news running every 30 minutes creates 48 runs/day = ~1,440 runs/month. If each takes 2+ minutes, this exceeds 2,000 free minutes for private repos.
**Why it happens:** Failing to account for setup time (checkout, uv sync) which adds ~45-60 seconds to each run.
**How to avoid:**
- For public repos: unlimited minutes, no concern.
- For private repos: Use `*/60` (every 60 minutes) instead of `*/30` for 720 runs/month. Each run is ~1-2 min total (45s setup + 15-30s pipeline), so ~720-1440 minutes. This fits within 2000 minutes.
- Alternative: Enable uv cache (`enable-cache: true` in setup-uv) to reduce install time.
- Track estimated minutes in pipeline_status.json and log warnings at 80% threshold.
**Warning signs:** Estimated monthly minutes exceeding 1500 in /status output.

### Pitfall 2: AI Budget Depletion from Breaking Checks
**What goes wrong:** Each breaking check that finds keyword-HIGH articles calls the AI, burning $0.01-0.05 per call. Over a month, this can consume the entire $5 budget, leaving nothing for scheduled runs.
**Why it happens:** Not aggressively gating AI calls in the breaking path.
**How to avoid:**
- ALWAYS check `check_budget()` before AI calls in breaking path.
- Set a lower AI budget threshold for breaking (e.g., skip AI if cost > $3.00, reserving $1.75 for scheduled runs).
- When AI is skipped, trust the keyword score (relevance_score >= 80 = HIGH per existing fallback logic).
- Log AI calls in breaking path separately for monitoring.
**Warning signs:** AI cost climbing quickly in ai_cost.json; breaking_ai_calls field in pipeline_status.

### Pitfall 3: Duplicate Breaking Alerts
**What goes wrong:** Same HIGH article gets sent as a breaking alert multiple times because seen.json was not updated after the alert.
**Why it happens:** Breaking workflow must read seen.json, check, send alert, AND write seen.json back. If the write-back fails or is not committed, the next breaking run re-alerts.
**How to avoid:**
- Breaking workflow MUST use EndBug/add-and-commit to persist seen.json after each run.
- Use the existing `add_to_seen()` function immediately after sending an alert.
- The dedup check at the start of each breaking run will then skip already-alerted articles.
**Warning signs:** Users receiving the same breaking alert twice within an hour.

### Pitfall 4: Breaking Alerts Colliding with Scheduled Delivery
**What goes wrong:** A breaking alert at 6:55 AM sends an article, then the 7:00 AM scheduled delivery also includes it.
**Why it happens:** The article is added to seen.json by breaking, but the scheduled delivery runs before the breaking commit is pushed. Git concurrency.
**How to avoid:**
- Use `concurrency: { group: deliver, cancel-in-progress: false }` for BOTH workflows to prevent simultaneous runs.
- OR: Skip breaking checks within a window around scheduled delivery times (e.g., skip if IST hour:minute is within 30 min of scheduled delivery).
- The shared concurrency group is simpler and more reliable -- it queues the breaking run until the deliver run finishes (or vice versa).
**Warning signs:** Both deliver.yml and breaking.yml running simultaneously in GitHub Actions.

### Pitfall 5: GNews Quota Exhaustion by Breaking Runs
**What goes wrong:** Breaking runs consume GNews API quota, leaving none for scheduled runs.
**Why it happens:** Including GNews in the breaking pipeline.
**How to avoid:** Breaking news MUST fetch RSS only, never GNews. GNews quota is reserved for the 2x daily scheduled runs (12 morning + 13 evening calls).
**Warning signs:** gnews_quota.json showing calls_used > 0 outside of scheduled delivery times.

### Pitfall 6: Usage Tracking Month Reset Race Condition
**What goes wrong:** Monthly usage counters don't reset, showing accumulated lifetime values.
**Why it happens:** PipelineStatus doesn't have a month field for reset logic.
**How to avoid:** Add `usage_month: str` field to PipelineStatus. On each run, check if current month matches; if not, reset monthly counters to 0.
**Warning signs:** Monthly counters growing indefinitely.

### Pitfall 7: GitHub Actions Workflow Timing Endpoints Deprecated
**What goes wrong:** Attempting to use `GET /repos/{owner}/{repo}/actions/runs/{run_id}/timing` API to get billable minutes fails because the endpoint is closing down.
**Why it happens:** GitHub deprecated Get workflow usage and Get workflow run usage endpoints as of Feb 2025.
**How to avoid:** Do NOT depend on the timing API. Instead, estimate minutes by counting runs and assuming a fixed per-run duration (e.g., 1.5 minutes for breaking, 3 minutes for deliver). This is approximate but sufficient for budget tracking.
**Warning signs:** API calls returning 404 or 410 errors.

## Code Examples

### Breaking News Entrypoint Pattern
```python
# Source: Derived from existing main.py architecture
"""Breaking news check — invoked by GitHub Actions via breaking.yml."""

import logging
import os
from datetime import UTC, datetime, timedelta, timezone

from pipeline.analyzers.classifier import classify_articles
from pipeline.analyzers.cost_tracker import check_budget
from pipeline.fetchers.rss_fetcher import fetch_all_rss
from pipeline.filters.dedup_filter import filter_duplicates
from pipeline.filters.relevance_filter import score_article
from pipeline.utils.loader import (
    load_ai_cost, load_config, load_keywords, load_seen,
    save_ai_cost, save_seen, load_pipeline_status, save_pipeline_status,
    load_bot_state,
)

_IST = timezone(timedelta(hours=5, minutes=30))
_BREAKING_HIGH_THRESHOLD = 80  # Same as keyword fallback HIGH
_BREAKING_AI_BUDGET_RESERVE = 3.00  # Reserve $2 for scheduled runs

def run_breaking() -> None:
    config = load_config("data/config.yaml")

    # Guard: breaking news disabled
    if not config.telegram.breaking_news_enabled:
        return

    # Guard: deliveries paused
    bot_state = load_bot_state("data/bot_state.json")
    if bot_state.pause.paused_slots:
        # Check if pause is still active
        if bot_state.pause.paused_until:
            expiry = datetime.fromisoformat(bot_state.pause.paused_until)
            if datetime.now(UTC) < expiry:
                return
        else:
            return  # Indefinite pause

    # Guard: skip during scheduled delivery windows
    now_ist = datetime.now(tz=_IST)
    # Skip 30 min before/after scheduled times
    # ... time window check ...

    # Fetch RSS only (no GNews)
    rss_articles, _ = fetch_all_rss(config.rss_feeds)

    # Keyword-only fast-path
    keywords = load_keywords("data/keywords.yaml")
    candidates = []
    for article in rss_articles:
        passes, score = score_article(article, keywords)
        if passes and score >= _BREAKING_HIGH_THRESHOLD:
            candidates.append(article.model_copy(update={"relevance_score": score}))

    if not candidates:
        return

    # Dedup against seen.json
    seen = load_seen("data/seen.json")
    deduped, seen = filter_duplicates(candidates, seen)
    new_articles = [a for a in deduped if a.dedup_status == "NEW"]

    if not new_articles:
        save_seen(seen, "data/seen.json")
        return

    # Optional AI confirmation (budget permitting)
    ai_cost = load_ai_cost("data/ai_cost.json")
    if ai_cost.total_cost_usd < _BREAKING_AI_BUDGET_RESERVE:
        classified, ai_cost = classify_articles(new_articles, ai_cost)
        save_ai_cost(ai_cost, "data/ai_cost.json")
        high_articles = [a for a in classified if a.priority == "HIGH"]
    else:
        # Trust keyword score
        high_articles = [a.model_copy(update={"priority": "HIGH"}) for a in new_articles]

    if not high_articles:
        save_seen(seen, "data/seen.json")
        return

    # Send breaking alert (Telegram only)
    # ... format and send ...

    save_seen(seen, "data/seen.json")
```

### Breaking News Workflow (breaking.yml)
```yaml
# Source: Derived from existing deliver.yml pattern
name: Breaking News

on:
  schedule:
    - cron: "*/30 * * * *"  # Every 30 minutes
  workflow_dispatch: {}

permissions:
  contents: write

concurrency:
  group: deliver           # SAME group as deliver.yml — prevents simultaneous runs
  cancel-in-progress: false

jobs:
  check:
    runs-on: ubuntu-latest
    timeout-minutes: 5     # Breaking check should be fast

    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
      - name: Install dependencies
        run: uv sync --locked
      - name: Run breaking news check
        run: uv run python -m pipeline.breaking
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_IDS: ${{ secrets.TELEGRAM_CHAT_IDS }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
      - name: Commit state
        uses: EndBug/add-and-commit@v9
        with:
          add: '["data/seen.json", "data/ai_cost.json", "data/pipeline_status.json"]'
          message: "chore(state): update after breaking news check [skip ci]"
          default_author: github_actions
```

### Extended PipelineStatus Schema
```python
# Source: Extending existing pipeline_status_schema.py
class PipelineStatus(BaseModel):
    last_run_utc: str = ""
    articles_fetched: int = 0
    articles_delivered: int = 0
    telegram_success: int = 0
    telegram_failures: int = 0
    email_success: int = 0
    sources_active: int = 0
    run_duration_seconds: float = 0.0
    # New: free-tier usage tracking
    usage_month: str = ""                  # "YYYY-MM" for monthly reset
    monthly_deliver_runs: int = 0          # Full pipeline runs
    monthly_breaking_runs: int = 0         # Breaking checks
    monthly_breaking_alerts: int = 0       # Breaking alerts sent
    monthly_ai_cost_usd: float = 0.0       # Mirror from ai_cost.json for /status
    est_actions_minutes: float = 0.0       # Estimated total Actions minutes
```

### Enhanced /status Display
```python
# Source: Extending existing handler.py status_command
async def status_command(update, context) -> None:
    status = await fetch_pipeline_status()
    ai_cost_raw = await read_github_file("data/ai_cost.json", ...)
    ai_cost = AICost(**json.loads(ai_cost_raw))

    # Usage percentages
    actions_pct = (status.est_actions_minutes / 2000) * 100  # 2000 min free tier
    ai_pct = (ai_cost.total_cost_usd / 5.0) * 100           # $5 budget

    text = (
        f"Pipeline Status\n\n"
        f"Last run: {status.last_run_utc or 'Never'}\n"
        f"Articles: {status.articles_fetched} fetched, {status.articles_delivered} delivered\n"
        f"Sources: {status.sources_active} active\n\n"
        f"Free Tier Usage ({status.usage_month})\n"
        f"Actions: ~{status.est_actions_minutes:.0f}/2000 min ({actions_pct:.0f}%)\n"
        f"AI spend: ${ai_cost.total_cost_usd:.2f}/$5.00 ({ai_pct:.0f}%)\n"
        f"Runs: {status.monthly_deliver_runs} delivers, {status.monthly_breaking_runs} checks\n"
        f"Breaking alerts: {status.monthly_breaking_alerts}\n"
    )
    await update.message.reply_text(text)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| GitHub Actions timing API (`/runs/{id}/timing`) | Deprecated -- use estimation-based tracking | Feb 2025 | Cannot query exact billable minutes via API; must estimate from run counts |
| Public repos unlimited Actions | Still unlimited for public repos | Ongoing | If repo is public, Actions minutes are not a constraint at all |
| Railway Hobby free $5 credit | Still $5/month included usage credit | Ongoing | Bot process stays within $5 if memory/CPU usage is minimal (polling bot is lightweight) |

**Deprecated/outdated:**
- `GET /repos/{owner}/{repo}/actions/runs/{run_id}/timing` endpoint: closing down (announced Feb 2025). Do NOT use for tracking.
- `GET /repos/{owner}/{repo}/actions/workflows/{id}/usage` endpoint: same deprecation.

## Budget Feasibility Analysis

### GitHub Actions Minutes (Private Repo)

**Deliver workflow:** 2 runs/day x 30 days = 60 runs/month
- Estimated per-run: ~2-3 minutes (checkout + uv sync cached + pipeline)
- Monthly: ~120-180 minutes

**Breaking workflow (every 30 min):** 48 runs/day x 30 days = 1,440 runs/month
- Estimated per-run: ~1-1.5 minutes (checkout + uv sync cached + RSS-only pipeline)
- Monthly: ~1,440-2,160 minutes

**RISK:** At 30-minute intervals with a private repo, breaking news could exceed 2,000 minutes/month.

**Mitigations:**
1. **If public repo:** Unlimited minutes, no issue.
2. **If private repo, use 60-minute intervals:** 720 runs/month x 1.5 min = ~1,080 minutes. Total with deliver: ~1,200 minutes. Safe margin.
3. **Skip breaking checks during scheduled windows:** Reduces ~4 runs/day, minor savings.
4. **Use uv cache aggressively:** Reduces install time from ~45s to ~5-10s.

**Recommendation:** Default to `*/60` (hourly), document that `*/30` is safe for public repos only.

### AI API Budget ($5/month)

**Scheduled runs:** 60 runs/month, ~15 articles each, ~1 AI call per run
- Claude Haiku: ~2000 input + ~1500 output tokens per call
- Cost: ~$0.0095 per call x 60 = ~$0.57/month

**Breaking checks:** Only calls AI when keyword-HIGH articles found
- Estimate ~5-10 keyword-HIGH detections per day that need AI confirmation
- Cost: ~5-10 x $0.01 x 30 = ~$1.50-3.00/month

**Total estimated:** $2.07-3.57/month. Within $5 budget.

**Safety:** Reserve threshold at $3.00 for breaking AI calls. Above $3.00, breaking trusts keyword scores only.

### Railway ($5/month)

Bot is a lightweight Python polling process. Typical Railway usage for a polling bot: $1-2/month for CPU+memory. Well within $5 credit.

## Open Questions

1. **Public or private repository?**
   - What we know: GitHub Actions free tier is 2000 min/month for private repos, unlimited for public repos.
   - What's unclear: Whether the Khabri repo is public or private.
   - Recommendation: Default to 60-minute breaking interval (safe for both). Document that 30-minute interval works for public repos. Check at production validation time.

2. **Breaking news during overnight hours?**
   - What we know: 48 runs/day is 24/7. Breaking news at 2 AM IST is unlikely useful.
   - What's unclear: Whether users want overnight alerts.
   - Recommendation: Restrict breaking checks to waking hours only (6 AM - 10 PM IST) to save Actions minutes. This reduces from 48 to ~32 runs/day for 30-min, or 16 for 60-min intervals. However, this adds complexity. Simpler approach: run 24/7 but at 60-min intervals.

3. **How many HIGH articles per breaking check in practice?**
   - What we know: Keyword threshold of 80 is quite selective. Most RSS fetch cycles return 0-2 articles scoring that high.
   - What's unclear: Exact production frequency of keyword-HIGH articles.
   - Recommendation: Build it, monitor in first week. If too noisy, raise threshold to 100.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/ -x --tb=short` |
| Full suite command | `uv run pytest tests/ -v --tb=short` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DLVR-05-a | Breaking news keyword fast-path filters correctly | unit | `uv run pytest tests/test_breaking.py::TestBreakingFilter -x` | Wave 0 |
| DLVR-05-b | Breaking news dedup prevents re-alerts | unit | `uv run pytest tests/test_breaking.py::TestBreakingDedup -x` | Wave 0 |
| DLVR-05-c | Breaking news AI confirmation gated by budget | unit | `uv run pytest tests/test_breaking.py::TestBreakingAIGate -x` | Wave 0 |
| DLVR-05-d | Breaking alert format is correct Telegram HTML | unit | `uv run pytest tests/test_breaking.py::TestBreakingFormat -x` | Wave 0 |
| DLVR-05-e | Breaking news respects pause state | unit | `uv run pytest tests/test_breaking.py::TestBreakingPause -x` | Wave 0 |
| DLVR-05-f | Breaking news skips during delivery windows | unit | `uv run pytest tests/test_breaking.py::TestBreakingTimeWindow -x` | Wave 0 |
| INFRA-06-a | PipelineStatus schema includes usage tracking fields | unit | `uv run pytest tests/test_pipeline_status.py::TestUsageTracking -x` | Wave 0 |
| INFRA-06-b | Usage monthly reset works correctly | unit | `uv run pytest tests/test_pipeline_status.py::TestUsageReset -x` | Wave 0 |
| INFRA-06-c | /status displays usage percentages | unit | `uv run pytest tests/test_bot_handler.py::TestStatusUsage -x` | Wave 0 |
| INFRA-06-d | Pipeline increments run counters | unit | `uv run pytest tests/test_main.py::TestRunCounter -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x --tb=short`
- **Per wave merge:** `uv run pytest tests/ -v --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_breaking.py` -- covers DLVR-05 (all breaking news tests)
- [ ] Extended tests in `tests/test_pipeline_status.py` -- covers INFRA-06 usage tracking
- [ ] Extended tests in `tests/test_bot_handler.py` -- covers INFRA-06 /status usage display

*(No new framework or config needed -- existing pytest infrastructure covers all requirements)*

## Sources

### Primary (HIGH confidence)
- Existing codebase analysis: `src/pipeline/main.py`, `src/pipeline/filters/relevance_filter.py`, `src/pipeline/analyzers/classifier.py`, `src/pipeline/deliverers/telegram_sender.py` -- verified all reusable modules
- Existing schema analysis: `src/pipeline/schemas/pipeline_status_schema.py`, `src/pipeline/schemas/ai_cost_schema.py`, `src/pipeline/schemas/bot_state_schema.py` -- verified extension points
- Existing workflow analysis: `.github/workflows/deliver.yml` -- verified concurrency pattern and state commit-back
- GitHub docs on Actions billing: https://docs.github.com/billing/managing-billing-for-github-actions/about-billing-for-github-actions -- 2000 minutes/month free for private repos

### Secondary (MEDIUM confidence)
- GitHub Actions workflow timing API deprecation: https://github.blog/changelog/2025-02-02-actions-get-workflow-usage-and-get-workflow-run-usage-endpoints-closing-down/ -- confirmed endpoint closing down
- Railway pricing: https://docs.railway.com/reference/pricing/plans -- $5/month hobby plan with $5 usage credit
- GitHub Actions cron scheduling: https://docs.github.com/en/actions/concepts/billing-and-usage -- verified */30 and */60 cron syntax

### Tertiary (LOW confidence)
- Per-run duration estimates (1.5 min for breaking, 2-3 min for deliver): based on observed `run_duration_seconds: 1.2` in pipeline_status.json plus estimated checkout/install overhead. Actual production times may vary.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in project, no new dependencies
- Architecture: HIGH - breaking news is a subset of existing pipeline, all modules exist
- Pitfalls: HIGH - budget calculations based on concrete numbers (2000 min, $5 AI, GNews quota)
- Free-tier compliance: MEDIUM - per-run duration estimates need production validation

**Research date:** 2026-03-08
**Valid until:** 2026-04-08 (30 days -- stable domain, no fast-moving dependencies)
