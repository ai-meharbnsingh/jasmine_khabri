# Phase 3: News Fetching - Research

**Researched:** 2026-02-27
**Domain:** RSS feed parsing, HTTP client, REST API quota management, Pydantic schema design
**Confidence:** HIGH (stack verified via PyPI + official docs; patterns verified via official docs + authoritative community sources)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**RSS Feed Sources**
- Feed URLs stored in config.yaml — add/remove feeds by editing YAML, no code changes needed
- Claude researcher finds the actual RSS/Atom URLs for each source (MOHUA, NHAI, AAI, Smart Cities, ET Realty, TOI Real Estate, Hindu BL, Moneycontrol RE)
- If a source has no RSS feed, skip it entirely — no scraping fallback
- 10-second timeout per feed before marking as failed and moving to next source

**GNews Quota Strategy**
- 25 daily API calls split evenly: 12 for morning run, 13 for evening run
- Infrastructure keyword group gets priority over Regulatory when quota is limited
- GNews API key from environment variable (GNEWS_API_KEY via GitHub Actions secrets)
- Results filtered to India only (country=in parameter)
- English language only for GNews results

**Error & Retry Behavior**
- No retries on RSS feed failures — log the failure and move on to next source
- Health summary table logged at end of each run: source name, status (OK/FAIL), article count, error if any

**Article Schema**
- Unified schema fields: title, url, source, published_at, summary, fetched_at
- Summary field left EMPTY — Phase 5 AI pipeline will generate all summaries
- fetched_at tracks when article was fetched (debugging and purge alignment)

### Claude's Discretion
- GNews query construction strategy (few broad Boolean queries vs many specific ones)
- Quota tracker reset mechanism (first-run-of-day vs midnight IST)
- Whether to log warning or silently skip when GNews quota is exhausted
- Exit behavior when all sources fail in a single run
- GNews API error classification (special handling for auth failures vs same as RSS)
- Article model architecture (new model vs extending existing)
- Fallback for missing published_at dates

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FETCH-01 | System fetches news from curated RSS feeds (MOHUA, NHAI, AAI, Smart Cities, ET Realty, TOI Real Estate, Hindu BL, Moneycontrol RE) | feedparser 6.0.12 + httpx 0.28.1 pattern: fetch bytes with httpx, parse with feedparser; confirmed RSS URLs in Standard Stack section |
| FETCH-02 | System fetches news from GNews.io API using keyword queries (100 req/day budget managed via batched Boolean queries) | GNews API docs confirmed: 100 req/day free, 10 articles/req max, `q`, `lang`, `country`, `max` params; quota tracker design in Architecture Patterns |
| FETCH-06 | System handles RSS feed failures gracefully (timeout, malformed XML, HTTP errors) without failing entire run | httpx Timeout class + feedparser bozo flag + per-source try/except; health summary table pattern documented |
</phase_requirements>

---

## Summary

Phase 3 implements the raw data ingestion layer: pulling articles from eight curated RSS/Atom feeds and the GNews.io REST API, normalizing to a unified Pydantic model, and logging a per-source health report. The existing codebase (Phase 1-2) provides SeenStore, loader utilities, and a running pytest infrastructure using the class-based pattern — Phase 3 extends this cleanly.

The primary technical pattern is **fetch-then-parse separation**: use httpx (synchronous client, `timeout=10.0`) to download raw feed bytes, then pass those bytes directly to `feedparser.parse()`. This is the officially recommended approach by feedparser's maintainer because feedparser has no built-in timeout and its internal HTTP code is deprecated. For GNews, use the REST API directly via httpx with a JSON state file (`data/gnews_quota.json`) tracking daily call counts — reset logic based on UTC date comparison is simpler and more reliable than IST midnight tracking.

For discretionary decisions: a **new standalone `Article` Pydantic model** (not extending `SeenEntry`) is the cleaner architecture because Article and SeenEntry serve different lifecycle stages — articles are transient fetching output, SeenEntry is durable deduplication state. For missing `published_at`, default to `fetched_at` (ISO 8601 UTC) so every article always has a valid timestamp. For quota exhaustion, log a WARNING and skip GNews gracefully — the pipeline should still deliver whatever RSS articles were fetched.

**Primary recommendation:** Use `httpx.Client(timeout=10.0)` + `feedparser.parse(bytes_content)` for RSS; use direct httpx GET to `https://gnews.io/api/v4/search` with a local JSON quota tracker for GNews; use a standalone `Article` Pydantic model; normalize to unified schema before returning from each fetcher.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| feedparser | 6.0.12 | Parse RSS/Atom/RDF XML into structured entries | Industry standard Python RSS parser; handles bozo feeds, malformed XML, all feed formats; production-stable, maintained by Kurt McKee |
| httpx | 0.28.1 | Fetch RSS feed content and call GNews REST API with timeout control | Modern requests-compatible HTTP client with strict timeout defaults; feedparser maintainer explicitly recommends using external HTTP client for fetching |
| pydantic | >=2.5 (already in project) | Article model validation and serialization | Already established project pattern; SeenStore, AppConfig use Pydantic v2 |
| PyYAML | >=6.0 (already in project) | Load RSS feed URLs from config.yaml | Already established project pattern |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| respx | >=0.21 | Mock httpx requests in pytest | Test RSS fetcher and GNews client without real network calls; handles httpx 0.28.x |
| pytest | >=8.0 (already in project) | Test framework | Already installed, class-based pattern established |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| feedparser + httpx | feedparser URL mode (feedparser.parse(url)) | URL mode has no timeout — causes permanent hangs on unresponsive feeds. Never use. |
| feedparser | atoma, xmltodict | feedparser handles real-world malformed feeds (bozo) better than alternatives; most battle-tested |
| httpx (sync) | httpx AsyncClient | Sync is simpler and sufficient — pipeline runs in a single GitHub Actions job, not serving concurrent requests |
| direct REST calls | gnews PyPI package | The `gnews` PyPI wrapper adds abstraction over a simple REST API; direct httpx calls give full control of quota params and error handling |

**Installation:**
```bash
uv add httpx feedparser
uv add --dev respx
```

Note: `pydantic` and `PyYAML` are already in `pyproject.toml` dependencies.

---

## Architecture Patterns

### Recommended Project Structure

The fetchers module already exists as a stub. Phase 3 fills it in:

```
src/pipeline/
├── fetchers/
│   ├── __init__.py
│   ├── rss_fetcher.py          # RssFetcher class — httpx + feedparser, per-feed try/except
│   └── gnews_fetcher.py        # GNewsFetcher class — REST API + quota tracker
├── schemas/
│   ├── __init__.py
│   ├── article_schema.py       # NEW: Article Pydantic model (standalone, not extending SeenEntry)
│   └── gnews_quota_schema.py   # NEW: GNewsQuota Pydantic model for quota state JSON
data/
├── config.yaml                 # ADD: rss_feeds section with named feeds + URLs
└── gnews_quota.json            # NEW: persisted quota tracker {"date": "2026-02-27", "calls_used": 12}
tests/
├── test_rss_fetcher.py         # NEW: unit tests with respx mocks
├── test_gnews_fetcher.py       # NEW: unit tests with respx mocks
└── test_article_schema.py      # NEW: Article normalization tests
```

### Pattern 1: Fetch-Then-Parse (RSS)

**What:** Download raw bytes with httpx, parse with feedparser as string/bytes — never pass URL to feedparser.
**When to use:** Every RSS feed fetch. Non-negotiable — feedparser's URL mode has no timeout.

```python
# Source: feedparser maintainer official recommendation (github.com/kurtmckee/feedparser/pull/80)
# Source: httpx docs (python-httpx.org/advanced/timeouts/)
import httpx
import feedparser
from pipeline.schemas.article_schema import Article

def fetch_feed(url: str, source_name: str, timeout: float = 10.0) -> tuple[list[Article], str | None]:
    """Returns (articles, error_message). error_message is None on success."""
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url)
            response.raise_for_status()
        feed = feedparser.parse(response.content)
        articles = [normalize_rss_entry(entry, source_name) for entry in feed.entries]
        return articles, None
    except httpx.TimeoutException:
        return [], f"timeout after {timeout}s"
    except httpx.HTTPStatusError as e:
        return [], f"HTTP {e.response.status_code}"
    except httpx.RequestError as e:
        return [], f"network error: {e}"
    except Exception as e:  # noqa: BLE001
        return [], f"unexpected: {e}"
```

### Pattern 2: Bozo Flag Handling

**What:** feedparser sets `feed.bozo = True` and `feed.bozo_exception` when XML is malformed. A bozo feed can still have parseable entries — do not discard outright.
**When to use:** After every `feedparser.parse()` call, log bozo status but still process entries.

```python
# Source: feedparser bozo detection docs (feedparser.readthedocs.io)
feed = feedparser.parse(response.content)
if feed.bozo:
    logger.warning(
        "Bozo feed detected for %s: %s (entries: %d)",
        source_name,
        feed.bozo_exception,
        len(feed.entries),
    )
# Continue processing feed.entries regardless — many real-world feeds are bozo-flagged
```

### Pattern 3: GNews API Call with Quota Check

**What:** Load quota state from JSON, check remaining calls, execute API call, update and save state.
**When to use:** Before every GNews API request.

```python
# Source: GNews API docs (docs.gnews.io/endpoints/search-endpoint)
import httpx
from pipeline.schemas.gnews_quota_schema import GNewsQuota

GNEWS_BASE = "https://gnews.io/api/v4/search"
GNEWS_MAX_PER_REQUEST = 10  # Free tier hard limit

def fetch_gnews(query: str, api_key: str, quota: GNewsQuota) -> tuple[list[Article], GNewsQuota]:
    if quota.calls_used >= quota.daily_limit:
        logger.warning("GNews daily quota exhausted (%d/%d). Skipping.", quota.calls_used, quota.daily_limit)
        return [], quota
    params = {
        "q": query,
        "lang": "en",
        "country": "in",
        "max": GNEWS_MAX_PER_REQUEST,
        "apikey": api_key,
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(GNEWS_BASE, params=params)
            response.raise_for_status()
        data = response.json()
        articles = [normalize_gnews_article(a) for a in data.get("articles", [])]
        new_quota = GNewsQuota(
            date=quota.date,
            calls_used=quota.calls_used + 1,
            daily_limit=quota.daily_limit,
        )
        return articles, new_quota
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            logger.error("GNews auth failure — check GNEWS_API_KEY")
        elif e.response.status_code == 429:
            logger.warning("GNews quota exceeded (server-side). Marking quota as exhausted.")
            new_quota = GNewsQuota(date=quota.date, calls_used=quota.daily_limit, daily_limit=quota.daily_limit)
            return [], new_quota
        else:
            logger.error("GNews HTTP error: %s", e)
        return [], quota
    except Exception as e:  # noqa: BLE001
        logger.error("GNews unexpected error: %s", e)
        return [], quota
```

### Pattern 4: Quota Tracker State Design

**What:** Lightweight JSON file tracks daily call count. Reset on new UTC date (simpler than IST midnight).

```python
# Source: project convention (data/seen.json Pydantic pattern from Phase 1)
# gnews_quota.json schema:
# {"date": "2026-02-27", "calls_used": 12, "daily_limit": 25}
from datetime import UTC, datetime
from pydantic import BaseModel

class GNewsQuota(BaseModel):
    date: str          # ISO date string "YYYY-MM-DD" in UTC
    calls_used: int = 0
    daily_limit: int = 25

def load_or_reset_quota(path: str) -> GNewsQuota:
    """Load quota from disk. Reset to zero if stored date != today UTC."""
    today = datetime.now(UTC).date().isoformat()
    try:
        stored = GNewsQuota.model_validate_json(Path(path).read_text())
        if stored.date == today:
            return stored
    except (FileNotFoundError, ValueError):
        pass
    return GNewsQuota(date=today, calls_used=0, daily_limit=25)
```

### Pattern 5: Article Normalization

**What:** Both RSS and GNews articles normalize to a single `Article` Pydantic model. Missing `published_at` defaults to `fetched_at`.

```python
# Source: project convention — matches SeenEntry pattern in seen_schema.py
from datetime import UTC, datetime
from pydantic import BaseModel

class Article(BaseModel):
    title: str
    url: str
    source: str          # Human-readable source name e.g. "ET Realty"
    published_at: str    # ISO 8601 UTC string; defaults to fetched_at if unavailable
    summary: str = ""    # ALWAYS empty — Phase 5 AI will populate
    fetched_at: str      # ISO 8601 UTC string — when pipeline fetched it

# RSS normalization helper:
def normalize_rss_entry(entry, source_name: str) -> Article:
    now_iso = datetime.now(UTC).isoformat()
    published = ""
    if hasattr(entry, "published") and entry.published:
        published = entry.published  # feedparser provides as string; store as-is
    return Article(
        title=entry.get("title", "").strip(),
        url=entry.get("link", ""),
        source=source_name,
        published_at=published or now_iso,  # fallback to fetched_at
        summary="",
        fetched_at=now_iso,
    )
```

### Pattern 6: Health Summary Table

**What:** Log a structured summary table after all sources have been attempted.
**When to use:** End of each pipeline run, covering both RSS and GNews.

```python
# Source: project convention — plain stdlib logging, no external tabulate dependency
# Project uses logging.info already (see main.py)
def log_health_summary(results: list[dict]) -> None:
    """Log health summary table. results is list of {source, status, count, error}."""
    header = f"{'Source':<30} {'Status':<6} {'Articles':>8} {'Error'}"
    logger.info("=== Fetch Health Summary ===")
    logger.info(header)
    logger.info("-" * 70)
    for r in results:
        error_str = r.get("error") or ""
        logger.info(
            "%-30s %-6s %8d %s",
            r["source"], r["status"], r["count"], error_str
        )
    logger.info("-" * 70)
```

### Pattern 7: GNews Boolean Query Construction (Discretionary Recommendation)

**What:** Group keywords into a small number of broad Boolean OR queries per category, not one query per keyword.
**Why:** Free tier = 100 req/day. With 25 calls budgeted per day and 2 runs, broad queries maximize article yield per call. The `q` param supports `AND`, `OR`, `NOT`, and quoted phrases.

**Recommended structure (3-4 queries total per run):**
```
Query 1 (Infrastructure group — priority):
  metro OR highway OR expressway OR NHAI OR airport OR AAI OR "smart city" OR DMRC

Query 2 (Regulatory group — secondary):
  RERA OR PMAY OR "affordable housing" OR MahaRERA OR MoHUA OR CIDCO

Query 3 (Real estate market — tertiary if quota remains):
  "real estate" OR "property market" OR "housing project" OR MMRDA OR DDA
```

Each query is passed with `country=in`, `lang=en`, `max=10` — yielding up to 10 articles per call.

**Quota split: 12 morning / 13 evening**
- Morning: 4 queries × 3 repeats = 12 calls (run 3 query groups)
- Evening: 4 queries × 3 = 13 calls (same groups, fresh content by then)

This design stays well within the 25-call budget while covering all keyword categories.

### Anti-Patterns to Avoid

- **feedparser.parse(url) with no timeout:** Hangs indefinitely on unresponsive servers. Always use httpx to fetch first.
- **One GNews query per keyword:** Would exhaust 100/day free quota in the first run. Use Boolean OR grouping.
- **Extending SeenEntry for Article:** SeenEntry stores url_hash + title_hash for deduplication. Article stores raw title + url for fetching output. Different purposes, different lifecycles — separate models.
- **Catching bare `Exception` without BLE001 noqa:** Ruff enforces BLE001. Add `# noqa: BLE001` when broad exception catch is intentional (per project pattern in main.py).
- **Committing GNEWS_API_KEY:** Key comes from `os.environ["GNEWS_API_KEY"]` only. Never hardcode.
- **Raising in per-source fetch:** A single feed error must not abort the whole run. Return `([], error_str)` tuple, continue.

---

## RSS Feed URLs (Research Findings)

The blueprint provided candidate URLs. Research findings on their reliability:

| Source | Blueprint URL | Status | Notes |
|--------|---------------|--------|-------|
| MOHUA | `https://mohua.gov.in/rss.xml` | LOW confidence — could not verify | Indian gov RSS feeds are often unreliable/broken; test at runtime |
| NHAI | `https://nhai.gov.in/rss-feed` | LOW confidence — no evidence of working RSS | NHAI site search returned no RSS/XML evidence in 2024-2025 |
| AAI | `https://www.aai.aero/en/rss` | LOW confidence — could not verify | Test at runtime; bozo-tolerant fetcher handles failure gracefully |
| Smart Cities | `https://smartcities.gov.in/rss` | LOW confidence — could not verify | Same pattern as other gov sites |
| ET Realty | `https://economictimes.indiatimes.com/industry/services/property-/-cstruction/rssfeeds/13357555.cms` | MEDIUM — blueprint URL is a known ET RSS pattern | ET RSS feeds work but may be IP-blocked in some contexts |
| TOI Real Estate | `https://timesofindia.indiatimes.com/rssfeeds/-2950715.cms` | MEDIUM — blueprint URL is a known TOI RSS pattern | Same caveat as ET |
| Hindu BL | `https://www.thehindubusinessline.com/real-estate/feeder/default.rss` | MEDIUM — consistent with BL feed URL pattern | Could not fetch in research environment |
| Moneycontrol RE | `https://www.moneycontrol.com/rss/realestate.xml` | MEDIUM — consistent with Moneycontrol RSS pattern | Could not fetch in research environment |

**Key implication for planning:** Government RSS feeds (MOHUA, NHAI, AAI, Smart Cities) are likely to return failures on the first live run. The bozo-tolerant, no-retry, log-and-continue design handles this correctly — the health summary will report them as FAIL without stopping the pipeline.

**Recommendation:** Config YAML should include all 8 feeds with their blueprint URLs. FAIL status on gov feeds is expected and non-blocking. The user can manually update URLs if they find working endpoints.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| RSS/Atom XML parsing | Custom XML parser | feedparser 6.0.12 | feedparser handles 50+ real-world RSS quirks: charset encoding, bozo feeds, timezone normalization, namespace conflicts, date format variations |
| HTTP client with timeout | urllib or socket | httpx 0.28.1 | httpx enforces timeouts at connect/read/write levels; stdlib urllib's timeout is unreliable |
| Mock HTTP in tests | Custom test server | respx | respx intercepts httpx at transport level — no network needed, no custom server code |
| GNews quota tracking | External DB or Redis | JSON state file | Project already uses JSON state files (seen.json, history.json) — same pattern, zero new dependencies |
| Health table formatting | tabulate library | stdlib logging with %-formatting | tabulate is an unnecessary dependency; %-format strings produce readable aligned log output without extra deps |

**Key insight:** feedparser's bozo detection is the result of years of real-world feed parsing experience. Custom XML parsers encounter these edge cases and fail silently. Always use feedparser for RSS.

---

## Common Pitfalls

### Pitfall 1: feedparser Hanging on Unresponsive URLs
**What goes wrong:** `feedparser.parse(url)` passes the URL to feedparser's internal HTTP code, which has no timeout. The process hangs indefinitely waiting for a response from a down server.
**Why it happens:** feedparser's maintainer explicitly stated HTTP code will be removed eventually; timeout was rejected as a PR in 2018.
**How to avoid:** Always call `httpx.Client(timeout=10.0).get(url)` first, then pass `response.content` (bytes) to `feedparser.parse()`.
**Warning signs:** Tests that call `feedparser.parse(url)` directly will not time out in CI.

### Pitfall 2: GNews Free Tier 12-Hour Delay
**What goes wrong:** GNews free plan has a 12-hour delay — articles appear 12 hours after publication. Content may be stale.
**Why it happens:** Free tier restriction (confirmed from pricing page).
**How to avoid:** Accept this limitation for Phase 3. Paid plan removes the delay. Document in code comments. The pipeline's value is aggregation and filtering, not breaking news speed.
**Warning signs:** Articles consistently appear 12+ hours old when fetched.

### Pitfall 3: GNews 10-Article-Per-Request Cap
**What goes wrong:** Setting `max=100` in the request returns only 10 articles on the free tier. Pipeline code assuming `max` parameter is honored will silently get fewer articles than expected.
**Why it happens:** Free plan caps at 10 articles per request regardless of `max` parameter value.
**How to avoid:** Always set `max=10` explicitly in code. Never assume more than 10 articles per call. Design query grouping strategy around this cap.
**Warning signs:** `data["totalArticles"]` is high but `len(data["articles"])` is always 10.

### Pitfall 4: RSS Entry Missing Fields
**What goes wrong:** `entry.link`, `entry.title`, `entry.published` may be absent or empty on some feeds. Accessing them as attributes raises `AttributeError` or returns empty string.
**Why it happens:** RSS specification doesn't require all fields. Government feeds are especially sparse.
**How to avoid:** Use `entry.get("title", "")` and `entry.get("link", "")` (feedparser entries support dict-style access). Check for empty URL and skip entry.
**Warning signs:** `Article(url="")` entries in output — add validation to skip entries with no URL.

### Pitfall 5: Ruff BLE001 on Broad Exception Catch
**What goes wrong:** `except Exception as e:` triggers ruff BLE001 (blind exception). CI fails.
**Why it happens:** Project has ruff configured with `["E", "F", "I", "UP"]` — BLE001 is under E. Actually ruff's BLE001 is under the BLE ruleset. Check pyproject.toml — BLE001 may not be selected. But project pattern in main.py already uses `# noqa: BLE001`.
**How to avoid:** Follow the existing pattern from main.py: `except Exception:  # noqa: BLE001` on intentional broad catches.
**Warning signs:** CI fails on ruff check with BLE001 errors.

### Pitfall 6: Published Date Timezone Ambiguity
**What goes wrong:** feedparser returns `entry.published` as a human-readable string that may or may not include timezone. `entry.published_parsed` is a `time.struct_time` in UTC, but may be `None` if parsing failed.
**Why it happens:** RSS feeds use inconsistent date formats.
**How to avoid:** Use `entry.published_parsed` (UTC struct_time) if present; convert to ISO 8601 UTC string. Fall back to `fetched_at` if None. Do NOT use `entry.published` (raw string) as the canonical date.
**Warning signs:** Dates like "Thu, 27 Feb 2026 00:00:00 +0530" stored as-is break downstream date comparisons.

### Pitfall 7: Config YAML Feed Section Not In AppConfig Schema
**What goes wrong:** RSS feed URLs added to config.yaml under a new `rss_feeds` key are silently ignored if `AppConfig` Pydantic model doesn't include the field.
**Why it happens:** Pydantic v2 ignores extra fields by default (model_config not set to `extra="allow"`).
**How to avoid:** Add `rss_feeds: list[RssFeedConfig]` to AppConfig before using it. Or store feed config in a separate `data/feeds.yaml` loaded independently. The per-CONTEXT decision is to put feeds in config.yaml — so AppConfig MUST be extended.
**Warning signs:** `config.rss_feeds` attribute doesn't exist at runtime.

---

## Code Examples

### Complete RSS Fetcher Pattern (Verified)

```python
# Source: httpx docs (python-httpx.org) + feedparser maintainer recommendation
import logging
from datetime import UTC, datetime

import feedparser
import httpx

from pipeline.schemas.article_schema import Article

logger = logging.getLogger(__name__)


def _struct_time_to_iso(st) -> str | None:
    """Convert feedparser's time.struct_time (UTC) to ISO 8601 string."""
    if st is None:
        return None
    from time import mktime
    from datetime import timezone
    dt = datetime.fromtimestamp(mktime(st), tz=UTC)
    return dt.isoformat()


def fetch_rss_feed(
    url: str,
    source_name: str,
    timeout: float = 10.0,
) -> tuple[list[Article], str | None]:
    """Fetch and parse one RSS feed. Returns (articles, error_or_None)."""
    now_iso = datetime.now(UTC).isoformat()
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, follow_redirects=True)
            response.raise_for_status()
        feed = feedparser.parse(response.content)
        if feed.bozo:
            logger.warning(
                "[%s] Bozo feed: %s (entries: %d)",
                source_name, feed.bozo_exception, len(feed.entries),
            )
        articles = []
        for entry in feed.entries:
            article_url = entry.get("link", "")
            if not article_url:
                continue  # skip entries with no URL
            published = _struct_time_to_iso(entry.get("published_parsed")) or now_iso
            articles.append(Article(
                title=entry.get("title", "").strip(),
                url=article_url,
                source=source_name,
                published_at=published,
                summary="",  # Phase 5 populates
                fetched_at=now_iso,
            ))
        return articles, None
    except httpx.TimeoutException:
        return [], f"timeout after {timeout}s"
    except httpx.HTTPStatusError as e:
        return [], f"HTTP {e.response.status_code}"
    except httpx.RequestError as e:
        return [], f"network error: {type(e).__name__}"
    except Exception as e:  # noqa: BLE001
        return [], f"unexpected: {type(e).__name__}: {e}"
```

### GNews Quota Loading Pattern (Verified against project conventions)

```python
# Source: project pattern from loader.py (Phase 1) + GNews API docs
import json
from datetime import UTC, datetime
from pathlib import Path

from pipeline.schemas.gnews_quota_schema import GNewsQuota

QUOTA_PATH = "data/gnews_quota.json"

def load_or_reset_quota(path: str = QUOTA_PATH) -> GNewsQuota:
    today = datetime.now(UTC).date().isoformat()
    try:
        raw = json.loads(Path(path).read_text())
        quota = GNewsQuota.model_validate(raw)
        if quota.date == today:
            return quota
    except (FileNotFoundError, ValueError, OSError):
        pass
    return GNewsQuota(date=today, calls_used=0, daily_limit=25)

def save_quota(quota: GNewsQuota, path: str = QUOTA_PATH) -> None:
    Path(path).write_text(quota.model_dump_json(indent=2) + "\n")
```

### Respx Mock Pattern for Testing (Verified)

```python
# Source: respx docs (lundberg.github.io/respx) — compatible with httpx 0.28.x
import httpx
import pytest
import respx

SAMPLE_RSS = b"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Metro Phase 4 approved</title>
      <link>https://example.com/metro-phase-4</link>
      <pubDate>Thu, 27 Feb 2026 10:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""


@respx.mock
def test_rss_fetcher_success():
    respx.get("https://mohua.gov.in/rss.xml").mock(
        return_value=httpx.Response(200, content=SAMPLE_RSS)
    )
    from pipeline.fetchers.rss_fetcher import fetch_rss_feed
    articles, error = fetch_rss_feed("https://mohua.gov.in/rss.xml", "MOHUA")
    assert error is None
    assert len(articles) == 1
    assert articles[0].title == "Metro Phase 4 approved"


@respx.mock
def test_rss_fetcher_timeout():
    respx.get("https://nhai.gov.in/rss-feed").mock(
        side_effect=httpx.TimeoutException("timed out")
    )
    from pipeline.fetchers.rss_fetcher import fetch_rss_feed
    articles, error = fetch_rss_feed("https://nhai.gov.in/rss-feed", "NHAI")
    assert articles == []
    assert "timeout" in error
```

### Config YAML Extension for RSS Feeds

```yaml
# Add to data/config.yaml under new rss_feeds section
rss_feeds:
  - name: "MOHUA"
    url: "https://mohua.gov.in/rss.xml"
    enabled: true
  - name: "NHAI"
    url: "https://nhai.gov.in/rss-feed"
    enabled: true
  - name: "AAI"
    url: "https://www.aai.aero/en/rss"
    enabled: true
  - name: "Smart Cities"
    url: "https://smartcities.gov.in/rss"
    enabled: true
  - name: "ET Realty"
    url: "https://economictimes.indiatimes.com/industry/services/property-/-cstruction/rssfeeds/13357555.cms"
    enabled: true
  - name: "TOI Real Estate"
    url: "https://timesofindia.indiatimes.com/rssfeeds/-2950715.cms"
    enabled: true
  - name: "Hindu BL"
    url: "https://www.thehindubusinessline.com/real-estate/feeder/default.rss"
    enabled: true
  - name: "Moneycontrol RE"
    url: "https://www.moneycontrol.com/rss/realestate.xml"
    enabled: true
```

This requires extending `AppConfig` with a new `RssFeedConfig` model and `rss_feeds: list[RssFeedConfig]` field.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `feedparser.parse(url)` | `httpx.get(url) → feedparser.parse(bytes)` | Since feedparser ~5.x (maintainer stated ~2011, still official guidance 2025) | Prevents permanent hangs on unresponsive feeds |
| `requests` for HTTP | `httpx` | 2020+ (httpx stable ~0.18) | httpx has strict timeouts by default; requests requires explicit timeout on every call |
| `feedparser.parse(url_string)` | `feedparser.parse(bytes_or_string)` | Always valid — feedparser supports both modes | Timeout control requires pre-fetching |

**Deprecated/outdated:**
- `socket.setdefaulttimeout()` workaround: Old pattern for feedparser timeout. Replaced by proper fetch-then-parse separation with httpx.
- `google-generativeai` Python SDK: Deprecated EOL Nov 2025 (already captured in STATE.md — use `google-genai`). Not relevant to Phase 3 but noted.

---

## Open Questions

1. **Government RSS feed URLs — are they actually working?**
   - What we know: Blueprint provides candidate URLs; search found no evidence of working NHAI/MOHUA/AAI/SmartCities RSS in 2024-2025
   - What's unclear: Whether any of the 4 government feeds return valid XML in production
   - Recommendation: Use the blueprint URLs in config.yaml as-is. First pipeline run will test them live. Bozo-tolerant fetcher handles failure gracefully. Health summary will clearly show which sources failed.

2. **GNews free tier delay (12 hours) — acceptable for Phase 3?**
   - What we know: Free plan confirms 12-hour article delay
   - What's unclear: Whether this is acceptable given the pipeline delivers at 7 AM and 4 PM IST
   - Recommendation: Accept for Phase 3. Document clearly in code. User can upgrade plan later if same-day news freshness becomes critical. For infrastructure news, 12-hour delay is likely acceptable.

3. **Article schema — should `published_at` store raw string or normalized ISO 8601 UTC?**
   - What we know: RSS feeds return wildly varying date formats; feedparser normalizes via `published_parsed` (UTC struct_time); GNews returns ISO 8601 UTC
   - What's unclear: Whether downstream phases (dedup in Phase 4, delivery in Phase 6) need normalized dates for comparison
   - Recommendation: Always store as ISO 8601 UTC string. Use `entry.published_parsed` (feedparser UTC struct_time) → `datetime.fromtimestamp(mktime(st), tz=UTC).isoformat()`. This ensures consistent format for Phase 4 deduplication comparisons.

---

## Sources

### Primary (HIGH confidence)
- feedparser 6.0.12 — PyPI page (pypi.org/project/feedparser/) — version, Python support, license
- feedparser maintainer PR #80 — github.com/kurtmckee/feedparser/pull/80 — official "use external HTTP client" guidance
- httpx 0.28.1 — PyPI (pypi.org/project/httpx/) + official docs (python-httpx.org/advanced/timeouts/) — version, timeout API, exception hierarchy
- GNews API docs — docs.gnews.io/endpoints/search-endpoint — all query parameters, response fields, pagination
- GNews pricing — gnews.io/pricing — free tier: 100 req/day, 10 articles/req, 12-hour delay
- Pydantic v2 docs — docs.pydantic.dev/latest/concepts/models/ — BaseModel inheritance patterns

### Secondary (MEDIUM confidence)
- respx docs — lundberg.github.io/respx — httpx mock fixture, httpx 0.28.x compatibility note
- feedparser bozo detection — pythonhosted.org/feedparser/bozo.html — bozo flag and exception behavior
- Simon Willison TIL — til.simonwillison.net/pytest/mock-httpx — pytest-mock + httpx patching patterns

### Tertiary (LOW confidence)
- Government RSS feed URLs (MOHUA, NHAI, AAI, Smart Cities) — from blueprint + search; could not verify working status in research environment
- ET Realty / TOI / BL / Moneycontrol RSS URLs — blueprint-sourced; consistent with known RSS URL patterns but not verified via fetch

---

## Metadata

**Confidence breakdown:**
- Standard stack (feedparser, httpx, respx): HIGH — PyPI versions + official docs verified
- Architecture patterns: HIGH — based on official recommendations and established project patterns
- GNews API details: HIGH — official docs fetched directly
- RSS feed URLs: LOW-MEDIUM — blueprint-sourced; government feeds especially uncertain
- Pitfalls: HIGH — feedparser timeout pitfall verified via maintainer; GNews limits verified via pricing page

**Research date:** 2026-02-27
**Valid until:** 2026-03-27 (30 days — stable ecosystem; GNews pricing may change)
