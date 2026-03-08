# Khabri - System Blueprint

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    KHABRI NEWS PIPELINE v1.0                     │
│         Indian Infrastructure & Real Estate Intelligence         │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  GITHUB ACTIONS  │    │     RAILWAY      │    │    TELEGRAM      │
│  (Scheduled)     │    │  (24/7 Bot)      │    │   (Users)        │
│                  │    │                  │    │                  │
│ deliver.yml      │    │ bot/entrypoint   │◄──►│ /help /status    │
│  7AM & 4PM IST   │───►│ long polling     │    │ /run /keywords   │
│                  │    │                  │    │ /pause /resume   │
│ breaking.yml     │    │ Auth + NLP +     │    │ /stats /schedule │
│  Every hour      │    │ 12 command       │    │ /menu + NL text  │
│                  │    │ handlers         │    │                  │
│ keepalive.yml    │    │                  │    │ 2 authorized     │
│  Weekly          │    │                  │    │ users            │
└──────────────────┘    └──────────────────┘    └──────────────────┘
         │                       │
         ▼                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                     GITHUB REPOSITORY                            │
│  ai-meharbnsingh/jasmine_khabri                                  │
│                                                                  │
│  State Files (git-committed after each run):                     │
│  ├── data/seen.json           (dedup store, 7-day TTL)           │
│  ├── data/history.json        (stats history)                    │
│  ├── data/ai_cost.json        (monthly AI spend tracking)        │
│  ├── data/pipeline_status.json (run metrics + usage counters)    │
│  ├── data/bot_state.json      (pause/schedule state)             │
│  └── data/gnews_quota.json    (daily API call counter)           │
│                                                                  │
│  Config Files:                                                   │
│  ├── data/config.yaml         (8 RSS feeds, schedule, delivery)  │
│  └── data/keywords.yaml       (4 categories + exclusions)        │
└──────────────────────────────────────────────────────────────────┘
```

## Pipeline Flow

```
FETCH (8 RSS + GNews)
  │  ~200 articles
  ▼
24-HOUR AGE FILTER
  │  Only articles published within last 24 hours
  ▼
RELEVANCE FILTER (keyword scoring)
  │  Title match = +20 pts, Body match = +10 pts
  │  Threshold: 40 points minimum
  │  Exclusion keywords: instant reject
  ▼
DEDUP FILTER (hash + similarity)
  │  Exact hash → DUPLICATE (skip)
  │  ≥80% similar → DUPLICATE (skip)
  │  50-80% similar → UPDATE (tracked, not delivered)
  │  <50% → NEW (delivered)
  ▼
GEO FILTER (city tier)
  │  Tier 1 (metros): always pass
  │  Tier 2 (secondary): need score ≥60
  │  Tier 3 (other): need score ≥85
  │  Government sources: treated as Tier 1
  ▼
AI CLASSIFIER
  │  Gemini 2.5 Flash (primary, free)
  │  Claude Haiku 4.5 (fallback)
  │  Keyword-only (if budget exceeded)
  │  Output: HIGH / MEDIUM / LOW + summary + entities
  ▼
SELECTOR
  │  Cap: 15 articles total (8 HIGH max)
  │  Priority order: HIGH → MEDIUM → LOW
  │  Only dedup_status="NEW" delivered
  ▼
DELIVER
  ├── Telegram: HTML formatted brief with priority sections
  └── Email: Styled HTML cards with colored borders
```

## Component Map

```
src/pipeline/
│
├── main.py ─────────────────── Full pipeline (GitHub Actions)
├── breaking.py ─────────────── Hourly breaking news (GitHub Actions)
│
├── fetchers/
│   ├── rss_fetcher.py ──────── 8 RSS feeds via httpx + feedparser
│   └── gnews_fetcher.py ────── GNews API with quota management
│
├── filters/
│   ├── relevance_filter.py ─── Keyword scoring (40pt threshold)
│   ├── dedup_filter.py ─────── Hash + SequenceMatcher dedup
│   └── geo_filter.py ──────── 3-tier city classification
│
├── analyzers/
│   ├── classifier.py ──────── Gemini → Claude → keyword fallback
│   └── cost_tracker.py ────── Budget gates ($4.00 warn, $4.75 degrade)
│
├── deliverers/
│   ├── telegram_sender.py ─── HTML formatting + 4096-char chunking
│   ├── email_sender.py ────── Gmail SMTP + styled cards
│   ├── selector.py ────────── Priority-based article selection
│   └── edge_cases.py ─────── No-news / slow-news / overflow
│
├── bot/
│   ├── entrypoint.py ──────── Bot startup + polling (Railway)
│   ├── handler.py ─────────── /help, /status, /run
│   ├── auth.py ────────────── User whitelist filter
│   ├── dispatcher.py ──────── GitHub Actions dispatch for /run
│   ├── keywords.py ────────── Keyword add/remove/display
│   ├── menu.py ────────────── Inline keyboard UI
│   ├── nlp.py ─────────────── Natural language intent parsing
│   ├── pause.py ───────────── Pause/resume with duration
│   ├── schedule.py ────────── Schedule view/modify
│   ├── stats.py ───────────── 7-day delivery statistics
│   ├── status.py ──────────── GitHub file reads for /status
│   └── github.py ──────────── GitHub Contents API wrapper
│
├── schemas/ ────────────────── 9 Pydantic v2 models
│   ├── article_schema.py       (Article: title, url, priority, entities)
│   ├── config_schema.py        (AppConfig: feeds, schedule, delivery)
│   ├── keywords_schema.py      (KeywordsConfig: categories + exclusions)
│   ├── ai_response_schema.py   (BatchClassificationResponse)
│   ├── ai_cost_schema.py       (AICost: monthly token/cost tracking)
│   ├── pipeline_status_schema.py (PipelineStatus: metrics + usage)
│   ├── bot_state_schema.py     (BotState: pause, schedule)
│   ├── seen_schema.py          (SeenStore: dedup entries)
│   └── gnews_quota_schema.py   (GNewsQuota: daily limit)
│
└── utils/
    ├── loader.py ──────────── Config/state file I/O
    ├── hashing.py ─────────── Title normalization + SHA256
    └── purge.py ───────────── 7-day TTL entry removal
```

## Keyword Strategy

```
ACTIVE CATEGORIES                         SCORING
─────────────────                         ───────
Infrastructure (52 keywords)              Title match: +20 pts
  metro, highway, airport, smart city     Body match:  +10 pts
  NHAI, DMRC, flyover, expressway         Threshold:    40 pts
                                          Breaking:     80 pts
Regulatory (18 keywords)
  MAHADA, PMAY, affordable housing
  MoHUA, CIDCO, MMRDA, DDA, BDA

Celebrity (55 keywords)                   EXCLUSIONS (15 terms)
  Bollywood: SRK, Akshay, Deepika...     ───────────────────
  South: Rajinikanth, Allu Arjun...       obituary, scandal, gossip
  Sports: Virat, Dhoni, Rohit...          divorce, affair, breakup
  Business: Ambani, Adani, Tata...        box office, movie review
                                          trailer launch, song launch
INACTIVE
────────
Transaction: property purchase, luxury apartment, villa...
```

## AI Classification

```
                    ┌─────────────────────┐
                    │  Articles to classify │
                    └──────────┬──────────┘
                               ▼
                    ┌─────────────────────┐
              ┌─YES─│  Budget < $4.75?    │─NO──┐
              │     └─────────────────────┘     │
              ▼                                  ▼
    ┌──────────────────┐              ┌──────────────────┐
    │ Gemini 2.5 Flash │              │ KEYWORD FALLBACK │
    │ (primary, free)  │              │ score≥80 → HIGH  │
    └────────┬─────────┘              │ score≥60 → MED   │
             │                        │ else → LOW        │
        Success?                      └──────────────────┘
        │      │
       YES     NO
        │      ▼
        │  ┌──────────────────┐
        │  │ Claude Haiku 4.5 │
        │  │ (fallback)       │
        │  └────────┬─────────┘
        │           │
        │      Success?
        │      │      │
        │     YES     NO
        │      │      ▼
        │      │  All → MEDIUM (safe default)
        ▼      ▼
    ┌──────────────────┐
    │ OUTPUT per article│
    │  priority: H/M/L │
    │  summary: 2 lines │
    │  location: city   │
    │  project_name     │
    │  budget_amount    │
    │  authority        │
    └──────────────────┘
```

## Delivery Format

### Telegram
```
📰 Khabri Morning Brief
08 Mar 2026 | 07:00 AM IST
5 stories (2 High | 2 Medium | 1 Low)
────────────────────────
🔴 HIGH PRIORITY (2)
1. Metro Phase 4 Gets Cabinet Nod
   ET Infra | Delhi NCR
   Cabinet approves 3 new corridors worth ₹32,000 crore...
   Budget: ₹32,000 Cr | Authority: MoHUA
   Read

2. NHAI Awards 200km Highway Contract
   Livemint | Gujarat
   ...

🟡 MEDIUM PRIORITY (2)
3. ...

🟢 LOW PRIORITY (1)
5. ...
────────────────────────
Powered by Khabri
Next: 4:00 PM IST
```

### Breaking Alert
```
🚨 BREAKING NEWS ALERT (1 story)
────────────────────────
1. Major Policy Change Announced
   Hindu BL Economy
   Summary of impact...
   Read
────────────────────────
Full brief in next scheduled delivery
```

## Cost & Usage (Free Tier)

```
MONTHLY BUDGET BREAKDOWN
────────────────────────────────────────
GitHub Actions:   ~81 / 2,000 min  (4%)
AI (Gemini):      ~$0.003 / $5.00  (<1%)
GNews API:        25 / 100 calls/day
Railway:          ~360 / 500 CPU hrs (72%)

COST GATES
────────────────────────────────────────
$0.00 - $4.00    Normal AI operation
$4.00 - $4.74    Warning logged, AI continues
$4.75+           Degrade to keyword-only (no AI)
$5.00            Hard monthly cap
```

## Secrets & Deployment

```
GITHUB ACTIONS SECRETS              RAILWAY ENV VARS
───────────────────────             ────────────────────
TELEGRAM_BOT_TOKEN    ✅            TELEGRAM_BOT_TOKEN    ✅
TELEGRAM_CHAT_IDS     ✅            TELEGRAM_CHAT_IDS     ✅
GOOGLE_API_KEY        ✅            GOOGLE_API_KEY        ✅
ANTHROPIC_API_KEY     ✅            ANTHROPIC_API_KEY     ✅
GMAIL_USER            ✅            GITHUB_PAT            ✅ (fine-grained)
GMAIL_APP_PASSWORD    ✅            GITHUB_OWNER          ✅
GMAIL_RECIPIENTS      ✅            GITHUB_REPO           ✅
                                    AUTHORIZED_USER_IDS   ✅
```

## Test Coverage

```
537 tests | 30 modules | 10.9s execution

Fetchers:     60+ tests  (RSS parsing, GNews API, quota)
Filters:      80+ tests  (keywords, dedup, geo tiers)
Analyzers:    50+ tests  (Gemini/Claude, cost tracking)
Deliverers:  100+ tests  (Telegram HTML, email, selection)
Bot:         120+ tests  (commands, NLP, auth, pause, schedule)
Integration:  40+ tests  (pipeline, breaking, edge cases)
Schemas:      30+ tests  (model validation)
GitHub API:   25+ tests  (file read/write, dispatch)
```

## Development History

```
Phase  1: Project Scaffold ──────────── 23 tests
Phase  2: Scheduling Infrastructure ─── 31 tests
Phase  3: News Fetching ─────────────── 73 tests
Phase  4: Filtering & Deduplication ─── 120 tests
Phase  5: AI Analysis Pipeline ──────── 169 tests
Phase  6: Telegram Delivery ─────────── 222 tests
Phase  7: Email & Edge Cases ────────── 294 tests
Phase  8: Railway Bot Foundation ────── 343 tests
Phase  9: Keyword & Menu Management ─── 403 tests
Phase 10: Advanced Bot Controls ─────── 489 tests
Phase 11: Breaking News & Hardening ─── 537 tests
```
