# Requirements: Khabri

**Defined:** 2026-02-26
**Core Value:** Deliver the right infrastructure and real estate news at the right time — so the user never misses critical developments and saves 2+ hours of daily manual research.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### News Fetching

- [x] **FETCH-01**: System fetches news from curated RSS feeds (government portals: MOHUA, NHAI, AAI, Smart Cities; news outlets: ET Realty, TOI Real Estate, Hindu BL, Moneycontrol RE)
- [x] **FETCH-02**: System fetches news from GNews.io API using keyword queries (100 req/day budget managed via batched Boolean queries)
- [x] **FETCH-03**: System filters articles by keyword library matching against title + description (relevance score >40 threshold)
- [x] **FETCH-04**: System applies exclusion keywords to filter noise (obituary, gossip, scandal, etc.)
- [x] **FETCH-05**: System applies geographic tier priority (Tier 1: always include; Tier 2: HIGH only; Tier 3: HIGH + impact >85 only)
- [x] **FETCH-06**: System handles RSS feed failures gracefully (timeout, malformed XML, HTTP errors) without failing entire run

### AI Analysis

- [ ] **AI-01**: System classifies articles as HIGH/MEDIUM/LOW priority using Claude Sonnet with domain-primed prompt (infrastructure, RERA, PMAY, celebrity criteria)
- [ ] **AI-02**: System generates 2-line AI summary per article explaining real estate/infrastructure impact
- [ ] **AI-03**: System detects duplicates against 7-day history using two-stage approach (title hash first, then semantic similarity at 0.85+ threshold)
- [ ] **AI-04**: System detects story updates (50-80% similarity) and labels them as "UPDATE" with reference to original
- [ ] **AI-05**: System extracts key entities per article (location, project name, budget, authority)
- [ ] **AI-06**: System uses Gemini as fallback when Claude API fails
- [ ] **AI-07**: System batches articles per AI call (up to 10-15 per batch) to stay within $5/month budget

### Delivery

- [ ] **DLVR-01**: System delivers curated news brief via Telegram to both users at 7 AM IST (formatted with priority sections, summaries, metadata, links)
- [ ] **DLVR-02**: System delivers curated news brief via Telegram to both users at 4 PM IST
- [ ] **DLVR-03**: System delivers HTML email digest via Gmail SMTP with styled template (priority-colored sections, article cards)
- [ ] **DLVR-04**: System selects max 15 stories per delivery with priority-based allocation (all HIGH up to 8, fill MEDIUM min 4, fill LOW min 2)
- [ ] **DLVR-05**: System sends breaking news alerts for critical HIGH-priority stories between scheduled deliveries
- [ ] **DLVR-06**: System handles slow news days gracefully (sends all available if <15, sends "no news" message if zero)
- [ ] **DLVR-07**: System notifies users when overflow HIGH stories exist (>8 HIGH, "reply 'more' to see them")

### Telegram Bot

- [ ] **BOT-01**: User can send /help to see available commands and usage
- [ ] **BOT-02**: User can send /status to see system health (last run, sources active, delivery success rate)
- [ ] **BOT-03**: User can send /pause and /resume to control alert delivery (with duration support: "pause 3 days")
- [ ] **BOT-04**: User can send /menu to access interactive inline keyboard settings menu
- [ ] **BOT-05**: User can add/remove keywords via commands ("add keyword: bullet train", "remove celebrity: Salman Khan")
- [ ] **BOT-06**: User can view current keywords organized by category (/keywords)
- [ ] **BOT-07**: User can send natural language commands parsed by AI ("stop evening alerts for a week", "track Priyanka Chopra")
- [ ] **BOT-08**: User can create event-based scheduling ("Budget on Feb 1, updates every 30 min from 10 AM to 3 PM")
- [ ] **BOT-09**: User can modify delivery schedule ("change morning alert to 6:30 AM")
- [ ] **BOT-10**: User can view delivery statistics (/stats — last 7 days: article counts, top topics, duplicates prevented)
- [ ] **BOT-11**: Bot restricts commands to authorized Telegram user IDs only

### Infrastructure

- [x] **INFRA-01**: System runs on GitHub Actions with UTC cron schedules correctly mapped to IST delivery times
- [x] **INFRA-02**: System stores mutable state (seen articles, config, keywords) as JSON files committed back to repo
- [x] **INFRA-03**: System includes keepalive workflow to prevent GitHub's 60-day inactivity cron disable
- [ ] **INFRA-04**: Telegram bot runs as persistent Python process on Railway (polling mode, no webhook needed) — handles commands instantly, dispatches heavy processing to GitHub Actions via repository_dispatch
- [x] **INFRA-05**: System auto-purges article history older than 7 days
- [x] **INFRA-06**: System operates within free tier limits (Railway $5/month credit for bot, $0 GitHub Actions, <$5/month AI API)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Enhanced Sources

- **SRC-01**: Hindi-language news source support
- **SRC-02**: Social media signal monitoring (Twitter/LinkedIn mentions)
- **SRC-03**: Source credibility weighting (ET Realty weighted higher than generic outlets)

### Analytics

- **ANLT-01**: 30-day trend analysis in /stats
- **ANLT-02**: Web UI analytics dashboard
- **ANLT-03**: PDF weekly summary report

### Content

- **CONT-01**: Automatic content draft suggestions based on trending topics
- **CONT-02**: Social media sentiment analysis on real estate topics

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Video news monitoring | Text only — complexity/cost too high for v1 |
| Automatic article writing | News delivery only, not content generation |
| Image/photo analysis | No vision AI needed — text metadata sufficient |
| Multi-language sources | English only — Hindi deferred to v2 |
| Voice notifications (WhatsApp) | Text channels sufficient, WhatsApp API costly |
| CMS integration (Magic Bricks) | Standalone system — no coupling to employer's platform |
| News archives >7 days | Recent news focus, storage/cost constraint |
| Paid news sources | Free sources only — budget constraint |
| Full web scraping | ToS violations, maintenance burden — use RSS/API only |
| Per-user personalized keywords | Two users share preferences — overkill for scale |
| ML recommendation learning | Keyword library IS the preference model |
| Read receipt tracking | Apple MPP makes this misleading |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FETCH-01 | Phase 3 | Complete |
| FETCH-02 | Phase 3 | Complete |
| FETCH-03 | Phase 4 | Complete |
| FETCH-04 | Phase 4 | Complete |
| FETCH-05 | Phase 4 | Complete |
| FETCH-06 | Phase 3 | Complete |
| AI-01 | Phase 5 | Pending |
| AI-02 | Phase 5 | Pending |
| AI-03 | Phase 4 | Pending |
| AI-04 | Phase 4 | Pending |
| AI-05 | Phase 5 | Pending |
| AI-06 | Phase 5 | Pending |
| AI-07 | Phase 5 | Pending |
| DLVR-01 | Phase 6 | Pending |
| DLVR-02 | Phase 6 | Pending |
| DLVR-03 | Phase 7 | Pending |
| DLVR-04 | Phase 6 | Pending |
| DLVR-05 | Phase 11 | Pending |
| DLVR-06 | Phase 7 | Pending |
| DLVR-07 | Phase 7 | Pending |
| BOT-01 | Phase 8 | Pending |
| BOT-02 | Phase 8 | Pending |
| BOT-03 | Phase 10 | Pending |
| BOT-04 | Phase 9 | Pending |
| BOT-05 | Phase 9 | Pending |
| BOT-06 | Phase 9 | Pending |
| BOT-07 | Phase 10 | Pending |
| BOT-08 | Phase 10 | Pending |
| BOT-09 | Phase 10 | Pending |
| BOT-10 | Phase 10 | Pending |
| BOT-11 | Phase 8 | Pending |
| INFRA-01 | Phase 2 | Complete |
| INFRA-02 | Phase 1 | Complete |
| INFRA-03 | Phase 2 | Complete |
| INFRA-04 | Phase 8 | Pending |
| INFRA-05 | Phase 2 | Complete |
| INFRA-06 | Phase 1 | Complete |

**Coverage:**
- v1 requirements: 37 total
- Mapped to phases: 37
- Unmapped: 0

---
*Requirements defined: 2026-02-26*
*Last updated: 2026-02-27 after 02-02 execution (INFRA-05 complete — Phase 2 all requirements done)*
