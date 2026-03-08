# Phase 10: Advanced Bot Controls - Research

**Researched:** 2026-03-08
**Domain:** Telegram bot natural language parsing, pause/resume state management, schedule modification, delivery statistics
**Confidence:** HIGH

## Summary

Phase 10 adds five new capabilities to the existing Telegram bot: (1) /pause and /resume commands with duration parsing, (2) natural language command parsing via Claude Haiku for schedule and keyword intents, (3) event-based scheduling with config.json persistence via GitHub API, (4) schedule modification commands, and (5) a /stats command reading delivery history from state JSON.

The project already has a well-established bot architecture (Phase 8-9): python-telegram-bot v22 with CommandHandler/MessageHandler pattern, auth filtering via `filters.User`, GitHub Contents API for state read/write (github.py), and immutable Pydantic model mutations via `model_copy(update=...)`. Phase 10 follows these patterns exactly. The primary technical challenge is the NL parser (BOT-07), which should use Claude Haiku 4.5 for intent classification with a regex pre-filter to avoid unnecessary AI calls for structured commands.

**Primary recommendation:** Use a two-tier parsing approach: regex catches structured commands first (/pause, /resume, /schedule, /stats), then a Claude Haiku 4.5 NL parser handles free-text messages that don't match any regex. All state changes (pause state, schedule modifications, event schedules) persist to config.json via the existing GitHub Contents API write pattern.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BOT-03 | /pause and /resume with duration support ("pause 3 days") | Duration parsing via regex (no external lib), pause state in config.json, GitHub API write-back pattern from Phase 9 |
| BOT-07 | Natural language commands parsed by AI ("stop evening alerts for a week") | Claude Haiku 4.5 intent classifier, two-tier regex+AI approach, MessageHandler catch-all in group 2 |
| BOT-08 | Event-based scheduling ("Budget on Feb 1, updates every 30 min from 10 AM to 3 PM") | Event schedule schema in config.json, Claude NL parser extracts event params, ISO datetime storage |
| BOT-09 | Schedule modification ("change morning alert to 6:30 AM") | IST-to-UTC cron conversion, config.json schedule field update, deliver.yml note (manual cron update required) |
| BOT-10 | /stats command (last 7 days: article counts, top topics, duplicates prevented) | Read history.json + pipeline_status.json from GitHub, aggregate by date, format summary |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-telegram-bot | >=22.0 | Bot framework, handlers, filters | Already in project deps, v22 async API |
| anthropic | >=0.84.0 | Claude Haiku NL intent parsing | Already in project deps, same client as classifier |
| httpx | >=0.28.1 | GitHub API calls for state persistence | Already in project deps, async client |
| pydantic | >=2.5 | Schema models for pause/schedule/stats state | Already in project deps, immutable model_copy pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| re (stdlib) | - | Duration regex, command pattern matching | All structured command parsing |
| datetime (stdlib) | - | IST/UTC conversion, duration calculation | Pause expiry, schedule times, stats date ranges |
| json (stdlib) | - | Config.json serialization | State persistence via GitHub API |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Regex duration parsing | dateparser/timelength library | Extra dependency for 5 patterns; regex is simpler, no new dep |
| Claude Haiku for NL | Regex-only NL parsing | Regex cannot handle freeform natural language like "stop evening alerts for a week" |
| Claude Haiku for NL | Gemini 2.5 Flash | Project already uses Claude-primary/Gemini-fallback; same pattern applies here |

**Installation:**
No new dependencies needed. All libraries already in pyproject.toml.

## Architecture Patterns

### Recommended Project Structure
```
src/pipeline/bot/
  pause.py          # /pause, /resume handlers + duration parser + pause state checker
  schedule.py       # /schedule, schedule modification handlers + event schema
  stats.py          # /stats handler + history aggregation
  nlp.py            # Natural language intent parser (Claude Haiku + fallback)
  handler.py        # EXISTING -- add /pause, /resume, /stats imports
  entrypoint.py     # EXISTING -- register new handlers
  github.py         # EXISTING -- reuse read/write functions
  status.py         # EXISTING -- reuse read_github_file
```

### Pattern 1: Two-Tier Command Parsing (Regex + AI)
**What:** Structured commands (/pause, /resume, /schedule, /stats) use regex via CommandHandler/MessageHandler. Unmatched text messages go to an NL catch-all handler that calls Claude Haiku for intent classification.
**When to use:** Always -- this prevents wasting AI calls on commands that have clear structure.
**Example:**
```python
# Entrypoint handler registration order:
# Group 0 (default): All CommandHandlers + Regex MessageHandlers
app.add_handler(CommandHandler("pause", pause_command, filters=auth_filter))
app.add_handler(CommandHandler("resume", resume_command, filters=auth_filter))
app.add_handler(CommandHandler("schedule", schedule_command, filters=auth_filter))
app.add_handler(CommandHandler("stats", stats_command, filters=auth_filter))

# Group 2 (lowest priority): NL catch-all for non-command text
# Uses filters.TEXT & ~filters.COMMAND to skip slash commands
app.add_handler(
    MessageHandler(
        auth_filter & filters.TEXT & ~filters.COMMAND,
        nl_command_handler
    ),
    group=2,
)
```

### Pattern 2: Pause State in config.json
**What:** Add a `pause` section to config.json storing pause state per delivery slot (morning/evening/all).
**When to use:** For /pause and /resume commands -- state must persist across bot restarts and be readable by the delivery pipeline.
**Example:**
```python
# New schema addition to config_schema.py
class PauseConfig(BaseModel):
    paused_until: str = ""        # ISO 8601 UTC datetime or empty (not paused)
    paused_slots: list[str] = Field(default_factory=list)  # ["morning", "evening"] or ["all"]
    paused_by: str = ""           # "user" or "system"

class AppConfig(BaseModel):
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    pause: PauseConfig = Field(default_factory=PauseConfig)
    # ... rest unchanged
```

### Pattern 3: Duration Parsing via Regex (No External Deps)
**What:** Simple regex to parse "3 days", "a week", "2 hours", "1 month" into timedelta.
**When to use:** For /pause duration arguments and NL-parsed durations.
**Example:**
```python
import re
from datetime import timedelta

_DURATION_PATTERN = re.compile(
    r"(\d+|a|an)\s*(minute|hour|day|week|month)s?",
    re.IGNORECASE,
)

_UNIT_MAP = {
    "minute": timedelta(minutes=1),
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
    "week": timedelta(weeks=1),
    "month": timedelta(days=30),
}

def parse_duration(text: str) -> timedelta | None:
    """Parse a human duration string into timedelta. Returns None if unparseable."""
    match = _DURATION_PATTERN.search(text)
    if not match:
        return None
    amount_str, unit = match.group(1), match.group(2).lower()
    amount = 1 if amount_str.lower() in ("a", "an") else int(amount_str)
    base = _UNIT_MAP.get(unit)
    if base is None:
        return None
    return base * amount
```

### Pattern 4: Claude Haiku NL Intent Parser
**What:** Send free-text user message to Claude Haiku with structured output schema for intent classification.
**When to use:** For BOT-07 -- parsing "stop evening alerts for a week", "track Priyanka Chopra", "change morning alert to 6:30 AM".
**Example:**
```python
NL_SYSTEM_PROMPT = """\
You parse Telegram bot commands for a news delivery system.

Given a user message, classify the intent and extract parameters.

Intents:
- pause: User wants to pause deliveries. Extract: slot (morning/evening/all), duration.
- resume: User wants to resume deliveries. Extract: slot (morning/evening/all).
- schedule_modify: User wants to change delivery time. Extract: slot, new_time (HH:MM IST).
- event_schedule: User wants event-based tracking. Extract: event_name, date, interval_minutes, start_time, end_time.
- keyword_add: User wants to add a tracking keyword. Extract: category, keyword.
- keyword_remove: User wants to remove a keyword. Extract: category, keyword.
- unknown: Cannot determine intent.

Return JSON with: intent, confidence (0-1), and extracted parameters.
"""

class NLIntent(BaseModel):
    intent: Literal["pause", "resume", "schedule_modify", "event_schedule",
                     "keyword_add", "keyword_remove", "unknown"]
    confidence: float = 0.0
    slot: str = ""           # morning/evening/all
    duration: str = ""       # "3 days", "a week"
    new_time: str = ""       # "06:30" for schedule_modify
    event_name: str = ""
    event_date: str = ""     # ISO date
    interval_minutes: int = 0
    start_time: str = ""     # HH:MM IST
    end_time: str = ""       # HH:MM IST
    category: str = ""       # for keyword intents
    keyword: str = ""        # for keyword intents
```

### Pattern 5: GitHub State Write-Back (Existing Pattern)
**What:** Read config.json with SHA, modify Pydantic model, serialize to JSON, write back via GitHub Contents API PUT.
**When to use:** All state-mutating commands (pause, resume, schedule modify, event schedule).
**Example:**
```python
# Reuse existing pattern from keywords.py
raw_json, sha = await read_github_file_with_sha("data/config.json", token, owner, repo)
config = AppConfig.model_validate_json(raw_json)
updated = config.model_copy(update={"pause": new_pause_state})
new_json = updated.model_dump_json(indent=2)
success = await write_github_file("data/config.json", new_json, "bot: pause deliveries", sha, ...)
```

**IMPORTANT:** The project currently uses `config.yaml` (YAML format). But the requirements say "config.json" for pause/schedule state. Two approaches:
1. Add a new `data/bot_state.json` file for bot-specific state (pause, events, custom schedules) -- **RECOMMENDED**
2. Switch config.yaml to config.json -- would break existing loader.py and all references

**Recommendation:** Create a new `data/bot_state.json` for bot-managed state. Keep config.yaml for pipeline config. This separation is cleaner: config.yaml is pipeline infrastructure, bot_state.json is user-facing bot state.

### Pattern 6: Stats Aggregation from History
**What:** Read history.json (SeenStore) from GitHub, aggregate articles by date for last 7 days.
**When to use:** For /stats command (BOT-10).
**Example:**
```python
# history.json has SeenStore with entries: [{url_hash, title_hash, seen_at, source, title}]
# pipeline_status.json has per-run stats
# Aggregate: count by date, count by source (top topics proxy), count duplicates

def compute_stats(history: SeenStore, days: int = 7) -> dict:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    recent = [e for e in history.entries if e.seen_at >= cutoff.isoformat()]
    by_date = Counter(e.seen_at[:10] for e in recent)
    by_source = Counter(e.source for e in recent)
    return {
        "total_articles": len(recent),
        "by_date": dict(by_date.most_common()),
        "top_sources": dict(by_source.most_common(5)),
        "days_covered": days,
    }
```

### Anti-Patterns to Avoid
- **Storing pause state only in bot memory:** Bot restarts on Railway would lose state. Must persist to GitHub.
- **Using Claude for every text message:** Most commands are structured (/pause 3 days). Only use AI for genuinely ambiguous natural language.
- **Modifying deliver.yml cron from the bot:** The bot runs on Railway, not in GitHub Actions. Schedule modification should update config.json/bot_state.json only. The actual cron times in deliver.yml must be manually updated or the pipeline should read config at runtime to decide whether to deliver.
- **Blocking on AI calls in the handler:** Claude API calls take 1-3 seconds. Send immediate "Processing..." feedback before the AI call.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Duration parsing | Complex NLP parser | Simple regex with unit map | Only 5-6 patterns needed (minutes, hours, days, weeks, months) |
| NL intent classification | Rule-based NLP engine | Claude Haiku 4.5 structured output | Free-form text like "stop evening alerts for a week" needs semantic understanding |
| GitHub file read/write | New API client | Existing `github.py` functions | read_github_file_with_sha + write_github_file already battle-tested |
| IST/UTC conversion | Manual offset math | datetime timezone with IST offset constant | _IST = timezone(timedelta(hours=5, minutes=30)) already defined in project |
| Auth filtering | Custom auth check | Existing filters.User pattern | auth_filter already wired in entrypoint.py |

**Key insight:** Phase 10 is almost entirely a wiring exercise -- the hard infrastructure (GitHub API, auth, bot framework, AI client) is all built. The new code is thin handlers connecting to existing utilities.

## Common Pitfalls

### Pitfall 1: Config.yaml vs Config.json Confusion
**What goes wrong:** The requirements mention "config.json" but the project uses config.yaml for pipeline config. Trying to store bot state in config.yaml requires YAML serialization and risks overwriting pipeline settings.
**Why it happens:** Requirements were written before implementation details were finalized.
**How to avoid:** Create a separate `data/bot_state.json` for bot-managed state (pause, events, custom schedules). Keep config.yaml for pipeline config only.
**Warning signs:** Merge conflicts between pipeline and bot writing to the same file.

### Pitfall 2: Pause State Not Checked by Delivery Pipeline
**What goes wrong:** Bot sets pause state in bot_state.json but deliver.yml pipeline ignores it and delivers anyway.
**Why it happens:** Pause state only exists on GitHub, and main.py doesn't read it.
**How to avoid:** Add a pause check at the top of main.py's delivery section: read bot_state.json, check if current time is before paused_until, check if current delivery slot is in paused_slots. Skip delivery if paused.
**Warning signs:** User pauses but still gets messages.

### Pitfall 3: NL Parser Costs Spiraling
**What goes wrong:** Every non-command text message triggers a Claude Haiku API call, even "ok", "thanks", "lol".
**Why it happens:** Catch-all MessageHandler without confidence threshold.
**How to avoid:** (1) Only route to NL parser if message length > 5 chars and contains schedule/pause/keyword-related words. (2) Set a confidence threshold (>0.7) below which the bot replies "I didn't understand that. Try /help." (3) Track NL parse costs separately from article classification costs.
**Warning signs:** AI cost spikes from bot usage.

### Pitfall 4: Handler Group Priority Conflicts
**What goes wrong:** NL catch-all handler intercepts messages before regex handlers.
**Why it happens:** All handlers in the same group -- first match wins.
**How to avoid:** Register NL catch-all in group 2 (higher number = lower priority). Existing handlers in group 0. Unauthorized handler in group 1 (already there).
**Warning signs:** Regex patterns for "add keyword:" stop working after adding NL handler.

### Pitfall 5: Schedule Modification Cannot Update Cron
**What goes wrong:** User says "change morning alert to 6:30 AM" -- bot updates config but GitHub Actions cron still runs at 01:30 UTC (7 AM IST).
**Why it happens:** Bot on Railway cannot modify deliver.yml in the repo (well, it can via GitHub API, but editing YAML in a workflow file is fragile and risky).
**How to avoid:** Two-part approach: (1) Bot updates the schedule times in bot_state.json. (2) The pipeline's main.py reads bot_state.json at runtime and decides whether to actually deliver based on the configured time vs current time. The cron triggers the pipeline at multiple possible times (or at the earliest possible time), and the pipeline itself decides whether to deliver.
**Warning signs:** User changes time but delivery happens at the old time.

### Pitfall 6: Event Schedule Timezone Issues
**What goes wrong:** User says "updates every 30 min from 10 AM to 3 PM" -- bot stores as UTC, but "10 AM" means IST.
**Why it happens:** Missing timezone context in parsing.
**How to avoid:** Always assume user times are IST. Store both IST (for display) and UTC (for computation) in the event schema. Convert at storage time, not at read time.
**Warning signs:** Event triggers 5.5 hours off from expected time.

## Code Examples

### Duration Parser (Verified pattern from stdlib)
```python
# Source: Python stdlib re + datetime
import re
from datetime import timedelta

_DURATION_PATTERN = re.compile(
    r"(\d+|a|an)\s*(minute|hour|day|week|month)s?",
    re.IGNORECASE,
)

_UNIT_MAP = {
    "minute": timedelta(minutes=1),
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
    "week": timedelta(weeks=1),
    "month": timedelta(days=30),
}

def parse_duration(text: str) -> timedelta | None:
    match = _DURATION_PATTERN.search(text)
    if not match:
        return None
    amount_str = match.group(1).lower()
    unit = match.group(2).lower()
    amount = 1 if amount_str in ("a", "an") else int(amount_str)
    base = _UNIT_MAP.get(unit)
    return base * amount if base else None
```

### IST Time Parser (for schedule modification)
```python
# Source: Python stdlib datetime
import re
from datetime import timedelta, timezone

_IST = timezone(timedelta(hours=5, minutes=30))

_TIME_PATTERN = re.compile(
    r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM|am|pm)?",
)

def parse_ist_time(text: str) -> tuple[int, int] | None:
    """Parse a time like '6:30 AM', '16:00', '6:30' into (hour, minute) in 24h IST."""
    match = _TIME_PATTERN.search(text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or "0")
    ampm = (match.group(3) or "").upper()
    if ampm == "PM" and hour != 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return (hour, minute)

def ist_to_utc_cron(hour_ist: int, minute_ist: int) -> tuple[int, int]:
    """Convert IST HH:MM to UTC HH:MM for cron."""
    # IST = UTC + 5:30
    total_minutes = hour_ist * 60 + minute_ist - 330  # subtract 5h30m
    if total_minutes < 0:
        total_minutes += 1440  # wrap to previous day
    return (total_minutes // 60, total_minutes % 60)
```

### Bot State Schema (New)
```python
# Source: Project Pydantic pattern (ai_cost_schema.py, pipeline_status_schema.py)
from pydantic import BaseModel, Field

class PauseState(BaseModel):
    paused_until: str = ""        # ISO 8601 UTC or empty
    paused_slots: list[str] = Field(default_factory=list)  # ["morning"], ["evening"], or ["all"]

class EventSchedule(BaseModel):
    name: str                     # e.g. "Union Budget 2026"
    date: str                     # ISO 8601 date "2026-02-01"
    interval_minutes: int = 30
    start_time_ist: str = ""      # "10:00"
    end_time_ist: str = ""        # "15:00"
    active: bool = True

class CustomSchedule(BaseModel):
    morning_ist: str = ""         # Override for morning time (empty = use config.yaml default)
    evening_ist: str = ""         # Override for evening time

class BotState(BaseModel):
    pause: PauseState = Field(default_factory=PauseState)
    events: list[EventSchedule] = Field(default_factory=list)
    custom_schedule: CustomSchedule = Field(default_factory=CustomSchedule)
```

### NL Handler Registration (python-telegram-bot v22)
```python
# Source: python-telegram-bot v22 docs
# In entrypoint.py, AFTER all specific handlers:

from pipeline.bot.nlp import nl_command_handler

# Group 2: NL catch-all (lower priority than commands and unauthorized handler)
app.add_handler(
    MessageHandler(
        auth_filter & filters.TEXT & ~filters.COMMAND,
        nl_command_handler,
    ),
    group=2,
)
```

### Stats Formatter
```python
# Source: Project pattern (telegram_sender.py format functions)
def format_stats_message(stats: dict) -> str:
    lines = [
        "Delivery Statistics (Last 7 Days)\n",
        f"Total articles processed: {stats['total_articles']}",
        f"Duplicates prevented: {stats['duplicates_prevented']}",
        "",
        "Articles by date:",
    ]
    for date, count in sorted(stats["by_date"].items()):
        lines.append(f"  {date}: {count}")
    lines.append("")
    lines.append("Top sources:")
    for source, count in stats["top_sources"]:
        lines.append(f"  {source}: {count}")
    return "\n".join(lines)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| python-telegram-bot v13 synchronous | v22 fully async (asyncio) | v20.0 (2023) | All handlers must be async def |
| Telegram Bot API parse_mode string | parse_mode="HTML" | Stable | Project already uses this |
| Claude Sonnet for classification | Claude Haiku 4.5 ($1/$5 MTok) | 2025 | 3x cheaper, fast enough for intent parsing |
| Complex NLP libraries for command parsing | LLM-based intent classification | 2024-2025 | More accurate on freeform text, no training data needed |

**Deprecated/outdated:**
- python-telegram-bot v13 synchronous handlers -- v22 is fully async
- parsedatetime library -- largely unmaintained, regex + LLM is simpler for this use case

## Open Questions

1. **Config.yaml vs bot_state.json:**
   - What we know: Requirements say "config.json" but project uses config.yaml
   - What's unclear: Whether to add fields to config.yaml or create a new file
   - Recommendation: Create `data/bot_state.json` (new file). Cleaner separation. Add to deliver.yml EndBug commit-back list.

2. **Pipeline pause enforcement:**
   - What we know: Bot can set pause state, but pipeline (main.py) must respect it
   - What's unclear: Whether main.py should read bot_state.json from disk or from GitHub API
   - Recommendation: Read from disk (main.py runs in GitHub Actions where the file is checked out). Simple `load_bot_state("data/bot_state.json")` in loader.py.

3. **Schedule modification and GitHub Actions cron:**
   - What we know: deliver.yml has fixed cron "30 1 * * *" and "30 10 * * *"
   - What's unclear: How to make the pipeline respect custom schedule times
   - Recommendation: Keep the cron at the earliest possible time. Add a "should I deliver now?" check at the start of main.py that compares current UTC time against the configured IST schedule. If not within a delivery window, exit early. This avoids editing workflow YAML from the bot.

4. **NL parser cost tracking:**
   - What we know: Article classification costs tracked in ai_cost.json
   - What's unclear: Whether NL command parsing costs should be separate
   - Recommendation: Track separately in bot_state.json or under a "bot_ai_cost" field. Bot AI usage is sporadic (user commands) vs pipeline AI usage (scheduled runs).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.0 |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -v --tb=short` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BOT-03 | /pause sets paused_until in bot_state.json via GitHub API; /resume clears it | unit | `uv run pytest tests/test_bot_pause.py -x` | Wave 0 |
| BOT-03 | Duration parsing for "3 days", "a week", "2 hours" | unit | `uv run pytest tests/test_bot_pause.py::TestParseDuration -x` | Wave 0 |
| BOT-07 | NL parser classifies "stop evening alerts for a week" as pause intent | unit | `uv run pytest tests/test_bot_nlp.py -x` | Wave 0 |
| BOT-07 | NL parser classifies "track Priyanka Chopra" as keyword_add intent | unit | `uv run pytest tests/test_bot_nlp.py::TestNLIntentKeyword -x` | Wave 0 |
| BOT-08 | Event schedule creation from parsed params | unit | `uv run pytest tests/test_bot_schedule.py::TestEventSchedule -x` | Wave 0 |
| BOT-09 | Schedule modification updates custom_schedule in bot_state.json | unit | `uv run pytest tests/test_bot_schedule.py::TestScheduleModify -x` | Wave 0 |
| BOT-09 | IST to UTC cron conversion (06:30 IST = 01:00 UTC) | unit | `uv run pytest tests/test_bot_schedule.py::TestISTToUTC -x` | Wave 0 |
| BOT-10 | /stats aggregates history.json entries by date and source | unit | `uv run pytest tests/test_bot_stats.py -x` | Wave 0 |
| BOT-10 | Stats message formatted with article counts and top sources | unit | `uv run pytest tests/test_bot_stats.py::TestFormatStats -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -v --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_bot_pause.py` -- covers BOT-03 (pause/resume handlers, duration parsing)
- [ ] `tests/test_bot_nlp.py` -- covers BOT-07 (NL intent classification)
- [ ] `tests/test_bot_schedule.py` -- covers BOT-08, BOT-09 (event scheduling, schedule modification)
- [ ] `tests/test_bot_stats.py` -- covers BOT-10 (stats aggregation and formatting)

## Sources

### Primary (HIGH confidence)
- Project codebase: `src/pipeline/bot/` (handler.py, entrypoint.py, github.py, keywords.py, menu.py, status.py, auth.py)
- Project schemas: `src/pipeline/schemas/config_schema.py`, `pipeline_status_schema.py`, `seen_schema.py`
- python-telegram-bot v22 docs: MessageHandler, filters.TEXT, filters.COMMAND, handler groups
- Python stdlib: `re`, `datetime`, `timedelta` for duration parsing and timezone conversion
- Anthropic Claude Haiku 4.5: $1/$5 per MTok, structured output support, intent classification use case

### Secondary (MEDIUM confidence)
- [python-telegram-bot v22 MessageHandler docs](https://docs.python-telegram-bot.org/en/stable/telegram.ext.messagehandler.html) - handler registration, filter combining
- [python-telegram-bot v22 filters docs](https://docs.python-telegram-bot.org/en/stable/telegram.ext.filters.html) - TEXT, COMMAND, Regex filter details
- [Claude Haiku 4.5 pricing](https://www.anthropic.com/claude/haiku) - $1 input / $5 output per MTok

### Tertiary (LOW confidence)
- Schedule modification enforced at pipeline runtime (approach needs validation with actual delivery behavior)
- Event-based scheduling trigger mechanism (may need deliver.yml cron adjustment for sub-hourly events)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in project, no new dependencies
- Architecture: HIGH - follows established bot patterns from Phase 8-9 exactly
- Duration parsing: HIGH - simple regex, well-understood problem
- NL parsing: MEDIUM - Claude Haiku intent classification is proven but prompt needs tuning
- Schedule modification: MEDIUM - runtime enforcement approach needs validation
- Pitfalls: HIGH - identified from direct codebase analysis

**Research date:** 2026-03-08
**Valid until:** 2026-04-07 (30 days -- stable stack, no fast-moving dependencies)
