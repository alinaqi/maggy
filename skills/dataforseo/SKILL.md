---
name: dataforseo
description: Keyword & SERP research via the DataForSEO API — search volume, competition, CPC, keyword ideas for naming/SEO decisions
when-to-use: When choosing a product/repo/domain name, sizing a keyword, checking search demand, or doing competitor/SEO research and WebSearch is not enough
user-invocable: true
effort: low
---

# DataForSEO Skill — keyword & SERP research

**Purpose:** Get real search demand (monthly volume, competition, CPC) and
keyword ideas from Google Ads data via [DataForSEO](https://dataforseo.com), so
naming and content decisions are grounded in data rather than intuition.

## Auth (never commit the key)

DataForSEO uses HTTP Basic auth. Provide credentials via environment only:

```bash
export DATAFORSEO_LOGIN="you@example.com"
export DATAFORSEO_PASSWORD="…"
# or a single combined value:
export DATAFORSEO_API_KEY="login:password"   # or its base64
```

The helper reads these from the env — it never hardcodes or logs the secret,
and only ever calls `api.dataforseo.com`. Keep the key in a local `.env` that is
git-ignored; do not paste it into the repo, a URL, or chat.

## Usage

The helper is `dataforseo.py` in this skill folder:

```bash
DFS="$(cat ~/.claude/.bootstrap-dir)/skills/dataforseo/dataforseo.py"

python3 "$DFS" whoami                                  # auth check + balance
python3 "$DFS" volume "claude code" "coding agent"     # search volume table
python3 "$DFS" ideas  "coding agent"                   # related keyword ideas
# options: --location <code, default 2840=US>  --language <code, default en>
```

`volume` → each keyword's monthly search volume, competition (LOW/MEDIUM/HIGH),
and CPC. `ideas` → the searched long-tail around a seed.

## Reading the results (naming decisions)

- **Zero / `n/a` volume on every candidate is itself the answer:** the names
  aren't search terms, so SEO can't rank them against each other — decide on
  clarity/brand and accept that discovery happens on GitHub/HN/X, not search.
- **Category term vs. brand term:** a huge-volume category word (e.g. the tool's
  ecosystem name) is where demand lives; a brand name rides it only if it
  contains it. Weigh discoverability against being on-brand for what you built.
- **Wrong-intent volume is a trap:** a candidate with existing volume may be
  drawing an audience searching for something *else* (a different industry
  meaning). That volume hurts, it doesn't help.
- **Competition + CPC** proxy commercial intent, not just popularity — high CPC
  means advertisers pay for that term (buyers), low CPC often means informational
  or noise.

## Cost & etiquette

`live` endpoints bill per call (search volume / ideas ≈ $0.05–0.10 each). Batch
many keywords into ONE `volume` call (it accepts up to 1000) rather than looping.
Check `whoami` for balance before large runs.

## Common endpoints (beyond the helper)

| Need | Endpoint |
|------|----------|
| Search volume | `keywords_data/google_ads/search_volume/live` |
| Keyword ideas | `keywords_data/google_ads/keywords_for_keywords/live` |
| SERP (who ranks) | `serp/google/organic/live/advanced` |
| Ranked keywords for a domain | `dataforseo_labs/google/ranked_keywords/live` |
| Competitor domains | `dataforseo_labs/google/competitors_domain/live` |

All take the same Basic-auth header; POST a JSON array of task objects.
