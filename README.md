# Khabri - Indian Infrastructure News Pipeline

Automated news intelligence system that fetches, classifies, and delivers curated Indian infrastructure and real estate news via Telegram and Email.

## What It Does

- Fetches news from **8 RSS feeds** (ET Realty, Livemint, Housing.com, etc.)
- Filters by **keyword relevance**, **geographic tier**, and **deduplication**
- Classifies articles using **Gemini 2.5 Flash AI** (HIGH/MEDIUM/LOW priority)
- Delivers to **Telegram** (formatted briefs) and **Email** (styled HTML cards)
- Sends **hourly breaking news alerts** for critical stories
- Interactive **Telegram bot** with 10+ commands, NLP, keyword management

## Architecture

```
GitHub Actions (2x daily + hourly)
  └─ Fetch RSS (8 feeds) + GNews API
  └─ Filter: relevance → dedup → geo-tier
  └─ Classify: Gemini 2.5 Flash → Claude Haiku fallback
  └─ Deliver: Telegram HTML + Email cards
  └─ Save state: seen.json, ai_cost.json (git commit)

Railway (24/7 polling)
  └─ Telegram bot: /status, /run, /keywords, /pause, /menu, NLP
```

## Quick Start

```bash
# Install dependencies
uv sync

# Set environment variables (see .env.example)
export TELEGRAM_BOT_TOKEN=...
export GOOGLE_API_KEY=...

# Run pipeline locally
uv run python -m pipeline.main

# Run breaking news check
uv run python -m pipeline.breaking

# Start bot locally
uv run python -m pipeline.bot.entrypoint

# Run tests
uv run pytest tests/ -v
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/status` | Pipeline health + free-tier usage % |
| `/run` | Trigger on-demand pipeline run |
| `/keywords` | View keyword library |
| `/menu` | Interactive inline keyboard |
| `/pause [duration]` | Pause deliveries (e.g. `/pause 3 days`) |
| `/resume` | Resume deliveries |
| `/stats` | 7-day delivery statistics |
| `/schedule [time]` | View/change delivery times |
| `add category: term` | Add keyword |
| `remove category: term` | Remove keyword |

Natural language also works: _"stop evening alerts for a week"_

## Delivery Schedule

| Event | Time (IST) | Frequency |
|-------|-----------|-----------|
| Morning Brief | 7:00 AM | Daily |
| Evening Brief | 4:00 PM | Daily |
| Breaking News | Hourly | When HIGH priority found |

## Keyword Categories

- **Infrastructure** (active): metro, highway, airport, smart city, NHAI, DMRC...
- **Regulatory** (active): MAHADA, PMAY, affordable housing, MoHUA, CIDCO, DDA...
- **Celebrity** (active): Bollywood + South Indian stars + sports players (infra news only)
- **Transaction** (inactive): property purchase, luxury apartment, villa...

Exclusions filter non-infra noise: gossip, scandal, movie reviews, box office, etc.

## AI Classification

| Provider | Role | Cost |
|----------|------|------|
| Gemini 2.5 Flash | Primary classifier | Free tier |
| Claude Haiku 4.5 | Fallback | $1/$5 per MTok |
| Keyword-only | Budget exceeded ($4.75+) | Free |

Budget gates: warn at $4.00, degrade at $4.75, hard cap at $5.00/month.

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot authentication |
| `TELEGRAM_CHAT_IDS` | Yes | Delivery recipients (comma-separated) |
| `GOOGLE_API_KEY` | Recommended | Gemini AI classification |
| `ANTHROPIC_API_KEY` | No | Claude fallback |
| `GMAIL_USER` | Optional | Email sender address |
| `GMAIL_APP_PASSWORD` | Optional | Gmail SMTP app password |
| `GMAIL_RECIPIENTS` | Optional | Email recipients |
| `GITHUB_PAT` | For bot | Fine-grained PAT (Contents + Actions R/W) |
| `GITHUB_OWNER` | For bot | Repo owner |
| `GITHUB_REPO` | For bot | Repo name |
| `AUTHORIZED_USER_IDS` | Optional | Bot access whitelist |
| `GNEWS_API_KEY` | Optional | GNews.io API |

## Deployment

**GitHub Actions** (news delivery):
- Secrets configured in repo settings
- `deliver.yml` — 2x daily + manual + bot `/run` dispatch
- `breaking.yml` — hourly breaking news checks
- `keepalive.yml` — weekly repo activity touch

**Railway** (Telegram bot):
- NIXPacks auto-build from `railway.json`
- Single replica, restart on failure (max 3)
- Environment variables set via Railway dashboard

## Project Structure

```
src/pipeline/
├── main.py              # Full pipeline entrypoint
├── breaking.py          # Breaking news pipeline
├── fetchers/            # RSS + GNews fetchers
├── filters/             # Relevance, dedup, geo filters
├── analyzers/           # AI classifier + cost tracking
├── deliverers/          # Telegram + Email + selector
├── bot/                 # 12 bot modules (commands, NLP, auth)
├── schemas/             # 9 Pydantic v2 models
└── utils/               # Loaders, hashing, purge

data/                    # Config + state files
├── config.yaml          # RSS feeds, schedule, delivery settings
├── keywords.yaml        # 4 keyword categories + exclusions
├── seen.json            # Dedup store (7-day TTL)
├── history.json         # Stats history
├── ai_cost.json         # Monthly AI spend
├── pipeline_status.json # Run metrics + usage
├── bot_state.json       # Pause/schedule state
└── gnews_quota.json     # Daily API quota

tests/                   # 537 tests across 30 modules
```

## Stats

- **537 tests** passing in 10.9s
- **8 RSS feeds** (all active, 200+ articles/run)
- **11 development phases** completed
- **24-hour article age filter** (no stale news)
- **Free tier optimized** (~4% GitHub Actions, ~$0.003/month AI)

## License

Private project by [ai-meharbnsingh](https://github.com/ai-meharbnsingh)
