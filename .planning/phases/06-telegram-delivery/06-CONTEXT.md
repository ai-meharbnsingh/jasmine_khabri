# Phase 6: Telegram Delivery - Context

**Gathered:** 2026-03-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Classified articles are selected by priority allocation, formatted as rich HTML Telegram messages, and delivered to both users at 7 AM and 4 PM IST. Messages include priority-labelled sections with AI summaries, entity metadata, and source links. Only NEW articles are delivered — UPDATEs and DUPLICATEs are excluded. Messages exceeding Telegram's 4096-char limit are automatically chunked.

</domain>

<decisions>
## Implementation Decisions

### Message format
- Telegram HTML parse mode (not Markdown V2 or plain text)
- Full detail per article: bold title, italic source + location, AI summary, entity line (budget/authority when present), clickable "Read" link
- Entities shown conditionally — only when AI extracted non-empty values; entity line omitted entirely if all empty
- Priority section indicators: colored circle emojis (🔴 HIGH, 🟡 MEDIUM, 🟢 LOW) with bold headers and story count
- Continuous numbering across sections (1-8 HIGH, 9-12 MEDIUM, 13-15 LOW) — no reset per section

### Message structure
- Header: "📰 Khabri Morning/Evening Brief" with IST time, date, and story count breakdown (X HIGH, Y MED, Z LOW)
- Horizontal separator between header and articles
- Footer: "Powered by Khabri" with next delivery time
- Section separators between priority groups

### Delivery filtering
- Only articles with `dedup_status="NEW"` are delivered — UPDATEs and DUPLICATEs are dropped entirely
- No "update to previous story" labels needed — similar stories are simply excluded

### Timezone handling
- All user-facing times in Telegram messages display as IST (Indian Standard Time, UTC+5:30)
- All backend/pipeline timestamps remain UTC
- Proper UTC→IST conversion for display: delivery time, article timestamps, "next delivery" footer
- Consistent with Phase 2 convention: cron in UTC, display in IST

### Claude's Discretion
- Story selection edge cases (fewer than 15 articles, 0 of a priority level, flexible allocation)
- Message chunking strategy for 4096-char Telegram limit (split by section vs per-article)
- Delivery error handling (retry logic, partial failure handling)
- Telegram API library choice (httpx direct vs python-telegram-bot)
- Rate limit handling for Telegram API
- Morning vs Evening brief title detection logic

</decisions>

<specifics>
## Specific Ideas

- Message should feel like a professional editorial brief — clean, scannable, not cluttered
- The preview mockup approved by user:
  ```
  📰 Khabri Morning Brief
  7:00 AM IST • Fri, 7 Mar 2026
  15 stories • 8 HIGH • 5 MED • 2 LOW
  ────────────────────────────────
  🔴 HIGH PRIORITY (8 stories)
  1️⃣ Delhi Metro Phase 4 Gets Cabinet Nod
     ET Realty • Delhi NCR
     Approval unlocks 3 new corridor stories
     for NCR real estate coverage.
     Budget: ₹46,000 Cr • Authority: DMRC
     ➤ Read
  ...
  ────────────────────────────────
  Powered by Khabri • Next: 4:00 PM
  ```

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/pipeline/deliverers/telegram_sender.py`: Empty placeholder ready for implementation
- `src/pipeline/schemas/config_schema.py`: TelegramConfig with bot_token, chat_ids, breaking_news_enabled
- `src/pipeline/schemas/config_schema.py`: DeliveryConfig with max_stories=15
- `src/pipeline/schemas/config_schema.py`: ScheduleConfig with morning_ist="07:00", evening_ist="16:00"
- `src/pipeline/schemas/article_schema.py`: Article model with priority, summary, location, project_name, budget_amount, authority, dedup_status fields

### Established Patterns
- Pydantic v2 models for all data, loader utilities for disk I/O
- httpx for HTTP calls (already a dependency)
- Functional style: functions return results, no mutation
- Environment variables for API keys/tokens (GNEWS_API_KEY, ANTHROPIC_API_KEY pattern — same for TELEGRAM_BOT_TOKEN)
- Config-driven: chat_ids from config.yaml, bot_token from env var

### Integration Points
- `main.py` line 153: "Phase 6-7: deliver (not yet implemented)" — wire delivery after classified_articles
- `deliver.yml`: already triggers at 01:30 UTC and 10:30 UTC (7 AM and 4 PM IST)
- `deliver.yml` env section: needs TELEGRAM_BOT_TOKEN secret added
- Article.dedup_status field: filter to "NEW" only before delivery

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-telegram-delivery*
*Context gathered: 2026-03-07*
