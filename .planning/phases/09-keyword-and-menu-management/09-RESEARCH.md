# Phase 9: Keyword and Menu Management - Research

**Researched:** 2026-03-08
**Domain:** Telegram bot inline keyboards, keyword CRUD via GitHub Contents API, ConversationHandler navigation
**Confidence:** HIGH

## Summary

Phase 9 adds three capabilities to the existing Railway-hosted Telegram bot: (1) a `/keywords` command that displays all keywords organized by category, (2) text-based commands for adding/removing keywords that persist changes to the GitHub repo via the Contents API, and (3) an interactive inline keyboard menu accessed via `/menu` that lets users navigate to settings, keywords, and stats sections by tapping buttons instead of typing commands.

The bot already uses `python-telegram-bot` v22.6 with `Application.run_polling()`, has auth filtering via `filters.User`, and communicates with GitHub via httpx for both reading state files (Contents API) and triggering workflows (repository_dispatch). Phase 9 extends this with three new python-telegram-bot constructs: `MessageHandler` with `filters.Regex` for add/remove text commands, `InlineKeyboardMarkup` + `CallbackQueryHandler` for the menu, and optionally `ConversationHandler` for multi-step menu navigation. The keyword file mutation requires a GitHub Contents API PUT (read SHA, then write base64-encoded YAML with commit message) -- the same API already used for reading, now with write operations added.

A critical discovery: the current `entrypoint.py` sets `allowed_updates=["message"]`, which filters out callback queries. This must be updated to `allowed_updates=["message", "callback_query"]` for inline keyboard buttons to work. Additionally, the roadmap references `keywords.json` but the actual file is `data/keywords.yaml` (YAML format). The implementation must use the real YAML file, not a hypothetical JSON file.

**Primary recommendation:** Add keyword display/add/remove handlers as simple async functions in a new `bot/keywords.py` module, add GitHub file write capability to `bot/status.py` (or a new `bot/github.py`), and implement the inline menu with `CallbackQueryHandler` in a new `bot/menu.py` module. Use simple `CallbackQueryHandler` with pattern matching rather than `ConversationHandler` -- the menu is stateless navigation, not a multi-step conversation.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BOT-04 | User can send /menu to access interactive inline keyboard settings menu | `InlineKeyboardMarkup` + `InlineKeyboardButton` + `CallbackQueryHandler` in python-telegram-bot v22.6. Pattern-based routing via `CallbackQueryHandler(callback, pattern="^keyword_")`. Must add `"callback_query"` to `allowed_updates` in entrypoint. |
| BOT-05 | User can add/remove keywords via commands ("add keyword: bullet train", "remove celebrity: Salman Khan") | `MessageHandler` with `filters.Regex` for text pattern matching. GitHub Contents API PUT for persisting changes to `data/keywords.yaml`. Requires reading file SHA first (GET), then writing base64-encoded updated YAML (PUT). |
| BOT-06 | User can view current keywords organized by category (/keywords) | `CommandHandler("keywords", callback)` reading keywords from GitHub via existing `read_github_file()` pattern. Format as categorized text with active/inactive indicators. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-telegram-bot | 22.6 (installed) | InlineKeyboardMarkup, CallbackQueryHandler, MessageHandler, filters.Regex | Already in project. Provides all inline keyboard and callback infrastructure needed. |
| httpx | 0.28.1 (installed) | GitHub Contents API read (GET) and write (PUT) for keyword file persistence | Already in project. Used by bot for all GitHub API calls. |
| pyyaml | 6.0+ (installed) | Serialize updated KeywordsConfig back to YAML format | Already in project. Used by loader.py for all YAML operations. |
| pydantic | 2.5+ (installed) | KeywordsConfig model for keyword data validation | Already in project. KeywordsConfig schema already exists. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| base64 (stdlib) | -- | Encode YAML content for GitHub Contents API PUT | When writing keyword file changes to GitHub |
| re (stdlib) | -- | Compile regex patterns for MessageHandler filters | For "add keyword:" and "remove category:" text matching |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Simple CallbackQueryHandler | ConversationHandler for menu | ConversationHandler adds state management complexity. The menu is stateless navigation (tap button, get response). Simple pattern-matched CallbackQueryHandlers are sufficient and testable. |
| GitHub Contents API PUT | repository_dispatch + workflow | Would require a separate GitHub Actions workflow just to commit keyword changes. Direct Contents API PUT is simpler, faster (immediate commit), and reuses the existing PAT. |
| YAML file persistence | Switch to JSON | Would require migrating data/keywords.yaml to data/keywords.json, changing loader.py, and breaking existing config. Keep YAML -- it is the current format. |

**Installation:**
```bash
# No new dependencies needed -- all libraries already installed
```

## Architecture Patterns

### Recommended Project Structure
```
src/pipeline/
  bot/
    __init__.py          # (exists)
    auth.py              # (exists) authorization guard
    dispatcher.py        # (exists) repository_dispatch trigger
    entrypoint.py        # MODIFY: add new handlers, update allowed_updates
    handler.py           # (exists) /help, /status, /run handlers
    status.py            # (exists) GitHub Contents API reader
    github.py            # NEW: GitHub Contents API writer (commit file changes)
    keywords.py          # NEW: /keywords command, add/remove handlers, keyword formatting
    menu.py              # NEW: /menu command, inline keyboard builder, callback handlers
  schemas/
    keywords_schema.py   # (exists, may need minor extension)
```

### Pattern 1: Keyword Display Formatter
**What:** Read keywords from GitHub via Contents API, parse YAML, format as categorized readable text.
**When to use:** For /keywords command (BOT-06).
**Example:**
```python
# Source: project patterns (status.py + keywords_schema.py)
from pipeline.bot.status import read_github_file
from pipeline.schemas.keywords_schema import KeywordsConfig
import yaml

async def format_keywords_display(token: str, owner: str, repo: str) -> str:
    """Read keywords from GitHub and format as categorized display text."""
    raw = await read_github_file("data/keywords.yaml", token, owner, repo)
    data = yaml.safe_load(raw)
    kw_config = KeywordsConfig.model_validate(data)

    lines = ["Current Keywords:\n"]
    for name, cat in kw_config.categories.items():
        status = "ACTIVE" if cat.active else "INACTIVE"
        lines.append(f"\n{name.title()} [{status}]")
        for kw in cat.keywords:
            lines.append(f"  - {kw}")

    if kw_config.exclusions:
        lines.append(f"\nExclusions:")
        for exc in kw_config.exclusions:
            lines.append(f"  - {exc}")

    return "\n".join(lines)
```

### Pattern 2: GitHub Contents API Write (Commit File)
**What:** Read current file SHA via GET, then PUT updated content with base64 encoding and commit message.
**When to use:** For keyword add/remove persistence (BOT-05).
**Example:**
```python
# Source: GitHub REST API docs + project's read_github_file pattern
import base64
import httpx

async def write_github_file(
    path: str, content: str, message: str,
    token: str, owner: str, repo: str,
) -> bool:
    """Write a file to the GitHub repo via Contents API.

    Steps:
    1. GET current file to obtain its SHA (required for update).
    2. PUT with base64-encoded content, SHA, and commit message.

    Returns True on success (200/201), False on failure.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {token}",
    }

    # Step 1: Get current SHA
    async with httpx.AsyncClient(timeout=10.0) as client:
        get_resp = await client.get(url, headers=headers)
        get_resp.raise_for_status()
        sha = get_resp.json()["sha"]

        # Step 2: PUT updated content
        encoded = base64.b64encode(content.encode()).decode()
        payload = {
            "message": message,
            "content": encoded,
            "sha": sha,
        }
        put_resp = await client.put(url, headers=headers, json=payload)
        return put_resp.status_code in (200, 201)
```

### Pattern 3: Keyword Add/Remove via Regex MessageHandler
**What:** Match "add keyword: ..." and "remove category: ..." text patterns using `filters.Regex`.
**When to use:** For BOT-05 keyword mutation commands.
**Example:**
```python
# Source: python-telegram-bot v22 filters docs
import re
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

# Pattern: "add keyword: <keyword>" or "add <category>: <keyword>"
ADD_PATTERN = re.compile(r"add\s+(?:keyword|(\w+)):\s*(.+)", re.IGNORECASE)
REMOVE_PATTERN = re.compile(r"remove\s+(\w+):\s*(.+)", re.IGNORECASE)

async def add_keyword_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'add keyword: ...' or 'add category: ...' messages."""
    match = context.matches[0]  # First regex match from filters.Regex
    category = match.group(1) or "infrastructure"  # Default category
    keyword = match.group(2).strip()

    # Read current keywords from GitHub, add keyword, write back
    # ... (see Pattern 2 for write logic)
    await update.message.reply_text(f"Added '{keyword}' to {category}")

# Registration in entrypoint:
# app.add_handler(MessageHandler(
#     auth_filter & filters.Regex(ADD_PATTERN),
#     add_keyword_handler,
# ))
```

### Pattern 4: Inline Keyboard Menu
**What:** Build an inline keyboard with buttons for Settings, Keywords, Stats. Handle button taps via CallbackQueryHandler.
**When to use:** For /menu command (BOT-04).
**Example:**
```python
# Source: python-telegram-bot v22 inlinekeyboard.py example
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /menu command -- show inline keyboard with navigation options."""
    keyboard = [
        [
            InlineKeyboardButton("Keywords", callback_data="menu_keywords"),
            InlineKeyboardButton("Stats", callback_data="menu_stats"),
        ],
        [
            InlineKeyboardButton("Settings", callback_data="menu_settings"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Khabri Menu:", reply_markup=reply_markup)

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button taps from /menu."""
    query = update.callback_query
    await query.answer()  # MUST answer to dismiss loading indicator

    if query.data == "menu_keywords":
        # Fetch and display keywords (reuse /keywords logic)
        text = await format_keywords_display(...)
        await query.edit_message_text(text)
    elif query.data == "menu_stats":
        # Fetch and display stats (reuse /status logic)
        ...
    elif query.data == "menu_settings":
        # Show settings submenu or info
        ...

# Registration:
# app.add_handler(CommandHandler("menu", menu_command, filters=auth_filter))
# app.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu_"))
```

### Pattern 5: YAML Round-Trip Serialization
**What:** Deserialize keywords YAML from GitHub, mutate via Pydantic model, serialize back to YAML for commit.
**When to use:** When adding/removing keywords -- must produce clean YAML output.
**Example:**
```python
import yaml
from pipeline.schemas.keywords_schema import KeywordsConfig

def add_keyword_to_config(config: KeywordsConfig, category: str, keyword: str) -> KeywordsConfig:
    """Add a keyword to a category. Returns new config (immutable pattern)."""
    if category not in config.categories:
        raise ValueError(f"Unknown category: {category}")
    cat = config.categories[category]
    if keyword in cat.keywords:
        raise ValueError(f"Keyword '{keyword}' already exists in {category}")
    new_keywords = [*cat.keywords, keyword]
    new_cat = cat.model_copy(update={"keywords": new_keywords})
    new_categories = {**config.categories, category: new_cat}
    return config.model_copy(update={"categories": new_categories})

def serialize_keywords_yaml(config: KeywordsConfig) -> str:
    """Serialize KeywordsConfig to YAML string for GitHub commit."""
    data = config.model_dump()
    return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
```

### Anti-Patterns to Avoid
- **ConversationHandler for simple menu:** The /menu is stateless navigation. Each button tap produces a response. No multi-step state needed. ConversationHandler adds per_message tracking, timeout handling, and conversation key management that is unnecessary overhead.
- **Storing keyword changes only in memory:** The bot runs on Railway, which restarts on failures. All keyword changes MUST be committed to GitHub. The pipeline reads keywords from disk (GitHub Actions checkout), so changes must be in the repo.
- **Using `update.message.reply_text()` in callback handlers:** Callback queries from inline buttons do NOT have `update.message`. Use `update.callback_query.answer()` and `update.callback_query.edit_message_text()`.
- **Forgetting to answer callback queries:** Every `CallbackQuery` MUST be answered with `query.answer()`, even if no notification is shown. Telegram clients may show loading indefinitely otherwise.
- **Keeping `allowed_updates=["message"]`:** Inline keyboard button taps generate `callback_query` updates, not `message` updates. If `allowed_updates` is not updated, ALL inline keyboard interactions will be silently dropped.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Text command parsing | Custom string splitting for "add keyword: X" | `MessageHandler(filters.Regex(pattern), callback)` + `context.matches` | Regex handles variations (whitespace, case), context.matches gives capture groups |
| Inline keyboard rendering | Custom message formatting with clickable-looking text | `InlineKeyboardMarkup` + `InlineKeyboardButton` | Telegram-native buttons with proper tap UX, callback routing |
| Button tap routing | if/elif on raw update text | `CallbackQueryHandler(callback, pattern="^menu_")` | Pattern matching routes callbacks to correct handler, composable with auth filter |
| YAML serialization | Manual string building for keywords file | `yaml.dump(config.model_dump(), ...)` | Handles quoting, indentation, Unicode, special characters correctly |
| SHA tracking for GitHub writes | Caching file SHA in memory | GET then PUT in single operation | SHA can change between bot restarts or concurrent pipeline runs |

**Key insight:** The bot is a thin command interface over the existing pipeline data. Every read comes from GitHub (Contents API GET), every write goes to GitHub (Contents API PUT). The bot itself stores nothing locally.

## Common Pitfalls

### Pitfall 1: allowed_updates Blocks Callback Queries
**What goes wrong:** /menu command shows inline keyboard, but tapping buttons does nothing. No errors in logs.
**Why it happens:** Current `entrypoint.py` has `allowed_updates=["message"]`. Callback queries from inline buttons are a different update type (`callback_query`), so Telegram never sends them to the bot.
**How to avoid:** Update `allowed_updates` to `["message", "callback_query"]` in `run_polling()`.
**Warning signs:** Menu displays fine, but button taps produce no response. No log entries for button taps.

### Pitfall 2: keywords.yaml vs keywords.json Naming Discrepancy
**What goes wrong:** Bot tries to read/write `data/keywords.json` (per roadmap text) but file does not exist. The actual file is `data/keywords.yaml`.
**Why it happens:** The roadmap/success criteria mention "keywords.json" but the project was implemented with YAML format in Phase 1 (per user intent for human-readable config).
**How to avoid:** Always use `data/keywords.yaml` as the file path. The schema (`KeywordsConfig`) and loader (`load_keywords`) already handle YAML.
**Warning signs:** 404 from GitHub Contents API when trying to read keywords.

### Pitfall 3: GitHub Contents API Requires SHA for Updates
**What goes wrong:** PUT request to update keywords.yaml returns 409 Conflict or 422 Unprocessable.
**Why it happens:** GitHub requires the current file's blob SHA in the PUT request body. Without it (or with a stale SHA), the API rejects the update.
**How to avoid:** Always GET the file first to obtain the current SHA, then immediately PUT with that SHA. Do NOT cache the SHA across requests -- it changes on every commit.
**Warning signs:** 409/422 errors from GitHub API on keyword add/remove.

### Pitfall 4: Concurrent Keyword Modifications
**What goes wrong:** Two users (or the same user rapidly) add keywords simultaneously. Second PUT fails because SHA changed.
**Why it happens:** First PUT commits and changes the SHA. Second PUT still has the old SHA.
**How to avoid:** For this project (2 users, infrequent keyword edits), this is unlikely. Handle it with a simple retry: if PUT returns 409, re-GET SHA and retry once. Log a warning.
**Warning signs:** Intermittent 409 errors on keyword changes.

### Pitfall 5: YAML Serialization Loses Comments and Formatting
**What goes wrong:** Original `keywords.yaml` has comments (# Metro & Rail, # Highways & Roads). After round-trip through Pydantic + yaml.dump, comments are lost.
**Why it happens:** YAML comments are not part of the data model. `yaml.safe_load()` discards them, `yaml.dump()` cannot restore them.
**How to avoid:** Accept this limitation. The bot-managed keyword file will lose comments after the first edit. Alternative: use `ruamel.yaml` to preserve comments, but this adds a new dependency for marginal benefit.
**Warning signs:** Keyword file loses all category comments after first bot-initiated edit.

### Pitfall 6: Inline Keyboard Message Length Limit
**What goes wrong:** /keywords via inline menu tries to display all 67+ keywords in a single `edit_message_text()` call, exceeding Telegram's 4096-char limit.
**Why it happens:** The keyword list is long. `edit_message_text()` has the same 4096-char limit as `send_message()`.
**How to avoid:** For /keywords display, show one category at a time with navigation buttons ("Next Category", "Previous Category"). Or truncate to category names with keyword counts, and let the user tap a category button to see its keywords.
**Warning signs:** Telegram API returns 400 Bad Request with "message is too long" error.

### Pitfall 7: Regex Pattern Conflicts with Existing Handlers
**What goes wrong:** Text like "add keyword: metro" is caught by the regex MessageHandler but also matched by the unauthorized catch-all handler.
**Why it happens:** Handler groups and priority order. The unauthorized handler in group=1 catches unmatched commands but the add/remove handlers need to be in group=0 (same as other authorized handlers).
**How to avoid:** Register add/remove MessageHandlers in group=0 with `auth_filter & filters.Regex(pattern)`. The auth filter ensures unauthorized users are rejected. The regex filter ensures only matching messages are processed.
**Warning signs:** Keyword commands get "Unauthorized" responses for authorized users.

## Code Examples

### GitHub File Writer (github.py)
```python
# Source: GitHub REST API docs (Contents endpoint)
import base64
import logging

import httpx

logger = logging.getLogger(__name__)


async def read_github_file_with_sha(
    path: str, token: str, owner: str, repo: str
) -> tuple[str, str]:
    """Read file content and SHA from GitHub Contents API.

    Returns (content, sha) tuple.
    Raises httpx.HTTPStatusError on API failure.
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
        return content, data["sha"]


async def write_github_file(
    path: str, content: str, message: str, sha: str,
    token: str, owner: str, repo: str,
) -> bool:
    """Write file to GitHub via Contents API PUT.

    Args:
        path: File path in repo (e.g. "data/keywords.yaml").
        content: New file content (raw string, will be base64 encoded).
        message: Git commit message.
        sha: Current blob SHA (from read_github_file_with_sha).
        token: GitHub PAT with Contents read/write.
        owner: Repo owner.
        repo: Repo name.

    Returns True on success (200 or 201), False otherwise.
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
    except Exception:
        logger.warning("Failed to write %s to GitHub", path, exc_info=True)
        return False
```

### Keyword Mutation Functions
```python
# Source: project patterns (model_copy immutability)
import yaml
from pipeline.schemas.keywords_schema import KeywordsConfig, KeywordCategory


def add_keyword(config: KeywordsConfig, category: str, keyword: str) -> KeywordsConfig:
    """Add keyword to category. Returns new config. Raises ValueError on invalid input."""
    cat_lower = category.lower()
    if cat_lower not in config.categories:
        raise ValueError(f"Unknown category: {category}")
    cat = config.categories[cat_lower]
    if keyword.lower() in [k.lower() for k in cat.keywords]:
        raise ValueError(f"'{keyword}' already exists in {category}")
    new_kw = [*cat.keywords, keyword]
    new_cat = cat.model_copy(update={"keywords": new_kw})
    new_cats = {**config.categories, cat_lower: new_cat}
    return config.model_copy(update={"categories": new_cats})


def remove_keyword(config: KeywordsConfig, category: str, keyword: str) -> KeywordsConfig:
    """Remove keyword from category. Returns new config. Raises ValueError if not found."""
    cat_lower = category.lower()
    if cat_lower not in config.categories:
        raise ValueError(f"Unknown category: {category}")
    cat = config.categories[cat_lower]
    # Case-insensitive match for removal
    matched = [k for k in cat.keywords if k.lower() == keyword.lower()]
    if not matched:
        raise ValueError(f"'{keyword}' not found in {category}")
    new_kw = [k for k in cat.keywords if k.lower() != keyword.lower()]
    new_cat = cat.model_copy(update={"keywords": new_kw})
    new_cats = {**config.categories, cat_lower: new_cat}
    return config.model_copy(update={"categories": new_cats})


def serialize_keywords(config: KeywordsConfig) -> str:
    """Serialize KeywordsConfig to YAML for GitHub commit."""
    return yaml.dump(
        config.model_dump(),
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
```

### Inline Keyboard Menu (menu.py)
```python
# Source: python-telegram-bot v22 inlinekeyboard.py official example
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the main menu with inline keyboard buttons."""
    keyboard = [
        [
            InlineKeyboardButton("Keywords", callback_data="menu_keywords"),
            InlineKeyboardButton("Status", callback_data="menu_status"),
        ],
        [
            InlineKeyboardButton("Help", callback_data="menu_help"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Khabri Menu:", reply_markup=reply_markup)


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle menu button taps via callback query."""
    query = update.callback_query
    await query.answer()  # REQUIRED: dismiss loading indicator

    if query.data == "menu_keywords":
        text = await _get_keywords_text(context)
        await query.edit_message_text(text=text)
    elif query.data == "menu_status":
        text = await _get_status_text()
        await query.edit_message_text(text=text)
    elif query.data == "menu_help":
        text = _get_help_text()
        await query.edit_message_text(text=text)
```

### Updated Entrypoint Registration
```python
# Source: current entrypoint.py pattern + new handlers
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, filters

# Existing handlers
app.add_handler(CommandHandler("help", help_command, filters=auth_filter))
app.add_handler(CommandHandler("status", status_command, filters=auth_filter))
app.add_handler(CommandHandler("start", help_command, filters=auth_filter))
app.add_handler(CommandHandler("run", run_now_command, filters=auth_filter))

# NEW Phase 9 handlers
app.add_handler(CommandHandler("keywords", keywords_command, filters=auth_filter))
app.add_handler(CommandHandler("menu", menu_command, filters=auth_filter))

# Text-based keyword add/remove (auth + regex)
app.add_handler(MessageHandler(
    auth_filter & filters.Regex(ADD_PATTERN), add_keyword_handler
))
app.add_handler(MessageHandler(
    auth_filter & filters.Regex(REMOVE_PATTERN), remove_keyword_handler
))

# Inline keyboard callback handler (auth checked via query.from_user)
app.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu_"))

# Unauthorized catch-all (group 1 -- lower priority)
app.add_handler(
    MessageHandler(filters.COMMAND & ~auth_filter, unauthorized_handler),
    group=1,
)

# CRITICAL: Update allowed_updates to include callback_query
app.run_polling(
    drop_pending_updates=True,
    allowed_updates=["message", "callback_query"],
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `ConversationHandler` for all multi-step flows | Simple `CallbackQueryHandler` with pattern routing for stateless menus | Best practice in v22 docs | ConversationHandler reserved for actual multi-step conversations (forms, wizards). Menus use pattern-matched callbacks. |
| `filters.Filters.regex()` (capital F, class) | `filters.Regex(pattern)` (module-level function) | v20 (2023) | Module restructured. `telegram.ext.filters` is a module, not a class. |
| Custom keyboard builders | `InlineKeyboardMarkup([[InlineKeyboardButton(...)]])` | Stable since v13+ | Nested list structure for rows/columns has not changed. |
| `bot.answer_callback_query()` | `query.answer()` shortcut | v20+ (2023) | Shortcut methods on CallbackQuery object are preferred. |

**Deprecated/outdated:**
- `telegram.ext.Filters` (capital F): Use `telegram.ext.filters` (lowercase module).
- `telegram.ext.RegexHandler`: Removed long ago. Use `MessageHandler(filters.Regex(...), callback)`.
- `Updater.start_polling()`: Use `Application.run_polling()`.

## Open Questions

1. **"add keyword" Default Category**
   - What we know: Success criteria says "add keyword: bullet train" adds to Infrastructure. But the user might want to add to other categories too.
   - What's unclear: Should "add keyword: X" always default to Infrastructure, or should it require a category?
   - Recommendation: Support both forms -- "add keyword: X" defaults to Infrastructure (most common), "add category: X" specifies the category (e.g., "add celebrity: Priyanka Chopra"). This matches the success criteria exactly.

2. **Inline Menu -- Stats Button Before Phase 10**
   - What we know: BOT-04 says menu should have buttons for "settings, keywords, and stats". But /stats is Phase 10 (BOT-10).
   - What's unclear: What should the Stats button do in Phase 9?
   - Recommendation: Include the Stats button in the menu but have it display last-run status summary (reusing /status data). Phase 10 adds the full 7-day stats.

3. **CallbackQuery Auth Filtering**
   - What we know: `filters.User` works on CommandHandler and MessageHandler. CallbackQueryHandler does not natively support the same filter parameter.
   - What's unclear: How to ensure only authorized users can tap menu buttons.
   - Recommendation: Check `update.callback_query.from_user.id` at the start of the callback handler. Since the /menu command itself is auth-filtered, only authorized users can generate the menu. But add an explicit check in the callback as defense-in-depth.

4. **YAML Comment Preservation**
   - What we know: The current keywords.yaml has extensive comments (category groups like "# Metro & Rail"). These will be lost on first bot edit.
   - What's unclear: Whether the user cares about comment preservation.
   - Recommendation: Accept comment loss. The bot provides a better UI for managing keywords than editing YAML comments. Document this in the plan.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -v --tb=short` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BOT-06 | /keywords formats all categories with active/inactive status | unit | `uv run pytest tests/test_bot_keywords.py::TestKeywordsDisplay -x` | Wave 0 |
| BOT-06 | /keywords reads keywords from GitHub Contents API | unit | `uv run pytest tests/test_bot_keywords.py::TestKeywordsCommand -x` | Wave 0 |
| BOT-05 | "add keyword: X" adds keyword to infrastructure category | unit | `uv run pytest tests/test_bot_keywords.py::TestAddKeyword -x` | Wave 0 |
| BOT-05 | "add category: X" adds keyword to specified category | unit | `uv run pytest tests/test_bot_keywords.py::TestAddKeywordCategory -x` | Wave 0 |
| BOT-05 | "remove category: X" removes keyword from category | unit | `uv run pytest tests/test_bot_keywords.py::TestRemoveKeyword -x` | Wave 0 |
| BOT-05 | Keyword changes written to GitHub via Contents API PUT | unit | `uv run pytest tests/test_bot_github.py::TestWriteGithubFile -x` | Wave 0 |
| BOT-04 | /menu shows inline keyboard with buttons | unit | `uv run pytest tests/test_bot_menu.py::TestMenuCommand -x` | Wave 0 |
| BOT-04 | Tapping menu button edits message with correct content | unit | `uv run pytest tests/test_bot_menu.py::TestMenuCallback -x` | Wave 0 |
| BOT-04 | Entrypoint registers callback_query in allowed_updates | unit | `uv run pytest tests/test_bot_entrypoint.py -x` | Exists (modify) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -v --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_bot_keywords.py` -- covers BOT-05, BOT-06 (keyword display, add, remove)
- [ ] `tests/test_bot_github.py` -- covers BOT-05 (GitHub Contents API write with SHA)
- [ ] `tests/test_bot_menu.py` -- covers BOT-04 (inline keyboard, callback handlers)
- [ ] `src/pipeline/bot/keywords.py` -- keyword command handlers and mutation functions
- [ ] `src/pipeline/bot/github.py` -- GitHub Contents API write (read_with_sha, write_file)
- [ ] `src/pipeline/bot/menu.py` -- inline keyboard menu and callback handlers

## Sources

### Primary (HIGH confidence)
- [python-telegram-bot v22.6 InlineKeyboard example](https://docs.python-telegram-bot.org/en/stable/examples.inlinekeyboard.html) - InlineKeyboardMarkup, CallbackQueryHandler pattern, handler registration
- [python-telegram-bot v22.6 CallbackQuery docs](https://docs.python-telegram-bot.org/en/stable/telegram.callbackquery.html) - answer(), edit_message_text() methods and signatures
- [python-telegram-bot v22 ConversationHandler docs](https://docs.python-telegram-bot.org/en/v22.3/telegram.ext.conversationhandler.html) - entry_points, states, fallbacks, per_message, per_chat, END constant
- [python-telegram-bot v22.6 filters docs](https://docs.python-telegram-bot.org/en/stable/telegram.ext.filters.html) - filters.Regex, filters.User, filter composition with &
- [GitHub REST API Contents endpoint](https://docs.github.com/en/rest/repos/contents) - PUT for create/update files, SHA requirement, base64 encoding
- Project codebase: `src/pipeline/bot/` (Phase 8 patterns), `src/pipeline/schemas/keywords_schema.py`, `src/pipeline/utils/loader.py`

### Secondary (MEDIUM confidence)
- [python-telegram-bot inlinekeyboard2.py example](https://github.com/python-telegram-bot/python-telegram-bot/blob/master/examples/inlinekeyboard2.py) - ConversationHandler with inline keyboards (reference only, not recommended for this use case)
- [GitHub REST API file update gist](https://gist.github.com/RammusXu/f3a01b4fe0fbc2096d65bf36204580ed) - GET SHA then PUT pattern confirmed

### Tertiary (LOW confidence)
- None. All critical findings verified against official documentation and project codebase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already installed and in use. No new dependencies.
- Architecture: HIGH - Extends established bot patterns from Phase 8. InlineKeyboardMarkup and CallbackQueryHandler are well-documented v22 APIs.
- Pitfalls: HIGH - `allowed_updates` issue verified by inspecting current entrypoint.py. YAML vs JSON discrepancy verified by inspecting data/ directory. GitHub SHA requirement verified against REST API docs.

**Research date:** 2026-03-08
**Valid until:** 2026-04-08 (stable domain, 30-day validity)
