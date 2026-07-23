# The Insights Engine

The insights engine watches topics the user cares about — news subjects,
stock tickers, GitHub repos — and turns fresh developments into structured,
graded "insight" cards on the dashboard's Insights page. It runs on a
schedule in the background and can also be triggered on demand.

This document describes how it works end to end.

## What an insight is

An insight is one structured analysis of one storyline. Unlike the original
version (a single flat paragraph), each insight carries discrete fields the
UI renders as sections:

| Field | Meaning |
|---|---|
| `headline` | One-line title; the collapsed-state text |
| `what_happened` | The factual core |
| `why_it_matters` | Analysis — implications, second-order effects |
| `what_to_watch` | Forward-looking bullets |
| `entities` | Companies / people / repos named |
| `significance` | 1–5 grade that drives storage, push, and collapse |
| `connection` | Optional link to a prior insight on the same topic |
| `sources` | The articles this card drew on |
| `kind` | `news` \| `stock` \| `github` |
| `ad_hoc` | True for a one-off user search (kept out of the curated feed) |

`summary` (a plain-text flattening of the structured fields) is retained too,
because the daily briefing and the outgoing chat notification both consume a
single string, and because legacy records only have that field.

Records written before the structured-insight change default every new field
and carry `schema_version = 1`; the frontend falls back to the old flat
layout for those. There is no migration — old records age out.

## The pipeline

Everything funnels through one function: `world_watch.scan_topic()`
(`src/managers/world_watch.py`). It owns a single topic's pipeline and
nothing else — deciding *when* to run and whether to *notify* is left to
callers, which is what lets the scheduled heartbeat and the dashboard share
the same code while behaving differently.

```
scan_topic(user, kind, topic)
   │
   ├─ 1. FETCH        _fetch() → source-specific checker (news/stock/github)
   │                  normalizes to {items, sources, markers, notable}
   │                  None  → state="fetch_failed"  (don't advance schedule)
   │                  empty → state="nothing_new"   (advance schedule)
   │
   ├─ 2. DEDUP/MARK   mark_run() records what was seen so the next scheduled
   │                  run only surfaces genuinely new items (skipped for ad-hoc)
   │
   ├─ 3. PRIOR        get_insights_by_topic() — recent insights on this topic,
   │                  fed to the analyzer for continuity
   │
   ├─ 4. ANALYZE      insight_analyzer.analyze() → List[Analysis]
   │                  (two-phase: cluster → per-storyline analysis)
   │                  empty → state="analysis_failed"
   │
   ├─ 5. GRADE-GATE   scheduled runs drop analyses below
   │                  INSIGHT_MIN_SIGNIFICANCE_STORE; ad-hoc keeps everything
   │                  all dropped → state="below_threshold"
   │
   └─ 6. STORE        one add_insight() per surviving storyline
                      → state="stored", returns the list of insights
```

The result is a `ScanResult` carrying a `state` (one of `SCAN_STATES`), the
list of stored `insights`, their `analyses`, and the full `sources` set. Only
`stored` produced anything; the other states are the normal, expected ways a
scan comes up empty and are surfaced to the UI rather than raised.

## The three sources

`_fetch()` dispatches on `kind` to a checker in `src/managers/watch_sources.py`
and normalizes every result to the same shape so the rest of `scan_topic`
never branches on kind again.

- **news** — SearXNG news search, `WORLD_WATCH_NEWS_RESULTS` results (25).
  New items are those whose URL isn't already in the topic's seen-markers.
- **stock** — Yahoo Finance day-move check. A move under
  `STOCK_WATCH_MOVE_THRESHOLD_PERCENT` (5%) is `notable: False` and stops
  there. A move that clears the bar is *enriched*: `_enrich_stock_context()`
  runs a news search on the ticker and attaches those headlines, so the
  analysis can explain **why** the stock moved rather than just that it did.
- **github** — GitHub's public API for a new release or new default-branch
  commit. Release bodies are captured up to 2000 chars so a changelog
  survives into the analysis.

Dedup uses opaque "markers": news uses result URLs, GitHub uses
`release:<tag>` / `commit:<sha>`, stock needs none (each check just asks "is
today's move notable right now").

## Two-phase LLM analysis

`insight_analyzer.analyze()` is the heart of the engine. A scan's findings
usually span several *unrelated* stories, so the analyzer clusters them and
produces one insight per story rather than one vague card for the whole
topic. It does this in two deliberately separate LLM calls:

**Phase 1 — cluster** (`_cluster`). One cheap call groups the findings into
storylines, asking only for a label and each group's source URLs — no
analysis, so the response stays short. Findings with a single item skip this
call entirely. If clustering fails or returns nothing usable, it falls back
to treating all findings as one story (one insight beats none). Groups are
capped at `INSIGHT_MAX_PER_SCAN` (5).

**Phase 2 — analyze** (`_analyze_one`). One focused call per storyline writes
that insight, seeing only its own group's findings plus the prior-insight
context. These run concurrently, bounded by a semaphore of
`INSIGHT_ANALYSIS_CONCURRENCY` (2). A failed storyline is dropped without
taking the others down (`asyncio.gather(..., return_exceptions=True)`).
Results are sorted most-significant-first.

> **Why split?** Asking one call for all N insights meant a single long
> (~2500-token) generation on the local 27B model whose quality visibly
> drifted toward the end — later storylines came back thinner. Per-storyline
> calls each stay small and sharp. The tradeoff is wall-clock time: on a
> 2-slot local server the calls largely serialize, so a busy topic can take
> several minutes. See "Performance" below.

**Robustness.** JSON is extracted tolerantly (code fences, bare arrays, or a
bare object all parse). Unparseable output *degrades* to a tier-2 insight
built from the raw text rather than being dropped. Source attribution comes
from the clustering step, not the model's word, so a card can't claim an
article it was never shown; invented URLs are filtered against the known set.

## Significance tiers

The model grades every storyline 1–5, replacing the old binary
notable/not-notable gate. The grade drives three decisions:

| Tier | Stored? | Pushed to chat? | UI |
|---|---|---|---|
| 1 | No (scheduled) | No | — |
| 2–3 | Yes | No | Collapsed card |
| 4–5 | Yes | Yes | Expanded card |

Two thresholds, both env-tunable, own this: `INSIGHT_MIN_SIGNIFICANCE_STORE`
(2) and `INSIGHT_PUSH_MIN_SIGNIFICANCE` (4). The net effect versus the old
gate: more lands in the feed (things that used to be discarded now appear at
tier 2–3), while *notifications* get quieter (only tier 4+ pings).

Grading is per-storyline, so a minor story alongside a major one no longer
suppresses the major one. **Ad-hoc searches bypass the store floor entirely**
— an explicit user action should always yield something.

## Continuity between insights

Before analyzing, `scan_topic` pulls the last `INSIGHT_PRIOR_CONTEXT_COUNT`
(5) insights on the same topic and hands the analyzer their ids, headlines,
and entities. The prompt asks for a `connection` **only** when a storyline
genuinely relates to one of them — it's nullable, so the model can't
manufacture a link to fill a field. A connection whose `prior_insight_id`
doesn't match a real insight is dropped at validation, so the UI never
renders a dead reference. Relations are `follows_up` / `contradicts` /
`escalates`.

## What triggers a scan

**1. The scheduled heartbeat** (`heartbeat_manager._process_world_watch`,
runs from chatty-bot). The heartbeat ticks every
`HEARTBEAT_INTERVAL_MINUTES` (15). On each tick it walks every authorized
user's watchlist and scans topics whose per-kind interval has elapsed:

- news — `WORLD_WATCH_INTERVAL_HOURS` (24h)
- stock — `STOCK_WATCH_INTERVAL_HOURS` (4h)
- github — `GITHUB_WATCH_INTERVAL_HOURS` (12h)

`last_run_at` gates this, and it's only advanced when a check actually
happened (a `fetch_failed` leaves it alone so the topic retries next tick).
For each stored insight at tier ≥ push threshold, it sends one chat message —
**one per storyline**, so a busy topic doesn't collapse into a single blob.

It iterates *only* `authorized_users`, never discovered `memory/*`
directories, to avoid spamming watches for users who never set one up.

**2. On-demand "scan now"** (`POST /api/chatty/insights/scan`, runs in
chatty-web-server). Bypasses the interval gate. Modes:

- `topic` — rescan one watchlist topic
- `all` — rescan the whole watchlist
- `adhoc` — a one-off search on a topic that isn't (and won't become) a watch

The work runs directly in the web process — chatty-bot and chatty-web-server
are separate processes, so the router calls `scan_topic` itself rather than
handing work to the bot. It returns a job id immediately (202); the frontend
polls `GET /scan/{job_id}` for per-target progress. One scan per user at a
time — a second request while one is in flight gets a 409 with the running
job's id, so a double-click can't fire duplicate LLM calls. Jobs live in an
in-memory registry (`scan_jobs.py`) bounded per user; a web restart loses
them, and the frontend treats a 404 as "refetch the feed and move on."

**3. Ad-hoc search** is `adhoc` mode above. It never touches watchlist state
(no `mark_run`), never applies the significance floor, and every insight it
produces is flagged `ad_hoc=True` so it's kept out of the curated feed unless
the user asks to see one-off results.

## Storage

Insights persist as per-user JSON at `data/insights/<user_id>.json`
(`InsightsManager`). Both chatty-bot (scheduled) and chatty-web-server
(on-demand) write the same file from separate processes, so writes are
guarded:

- a **sidecar file lock** (`<user_id>.lock`, `fcntl.flock`) serializes the
  read-modify-write, so an interleaved pair of scans can't silently drop one
  insight;
- `_save_insights` writes a temp file and `os.replace`s it, so a concurrent
  reader always sees complete JSON, never a half-written file.

`get_insights()` sorts newest-first, filters by `min_significance`, and
excludes `ad_hoc` records unless asked. `get_insights_by_topic()` feeds the
continuity step.

## The API

| Route | Purpose |
|---|---|
| `GET /api/chatty/insights` | Feed; `limit`, `min_significance`, `include_ad_hoc` |
| `DELETE /api/chatty/insights/{id}` | Remove one insight |
| `POST /api/chatty/insights/scan` | Start an on-demand scan → job id (202) |
| `GET /api/chatty/insights/scan/{job_id}` | Poll scan progress |

The Insights page renders the sections, a significance meter, collapsed cards
for low tiers (click to expand), the connection link, per-card sources, and a
topic filter. The daily briefing also reads recent insights to mention how
many new ones surfaced.

## Configuration

| Env var | Default | What it does |
|---|---|---|
| `HEARTBEAT_INTERVAL_MINUTES` | 15 | How often the scheduled loop ticks |
| `WORLD_WATCH_INTERVAL_HOURS` | 24 | News recheck interval |
| `STOCK_WATCH_INTERVAL_HOURS` | 4 | Stock recheck interval |
| `GITHUB_WATCH_INTERVAL_HOURS` | 12 | GitHub recheck interval |
| `STOCK_WATCH_MOVE_THRESHOLD_PERCENT` | 5.0 | Day move needed to be notable |
| `WORLD_WATCH_NEWS_RESULTS` | 25 | News results fetched per scan |
| `INSIGHT_MAX_PER_SCAN` | 5 | Max storylines (and insights) per scan |
| `INSIGHT_ANALYSIS_CONCURRENCY` | 2 | Concurrent phase-2 calls; match server slots |
| `INSIGHT_MIN_SIGNIFICANCE_STORE` | 2 | Feed floor (scheduled runs) |
| `INSIGHT_PUSH_MIN_SIGNIFICANCE` | 4 | Chat-notification floor |
| `INSIGHT_PRIOR_CONTEXT_COUNT` | 5 | Prior insights fed for continuity |

## Performance and tradeoffs

The two-phase design costs LLM calls: 1 clustering call + 1 per storyline, up
to 6 per topic scan. On the local 2-slot 27B server these largely serialize,
so a busy "ai"-type topic measured ~470s wall clock for 5 insights (versus
~184s for the older single-call approach that produced 4 thinner ones). The
quality is better and per-card source attribution is tighter, but it is
slower on this hardware.

Levers if a scan is too slow, in order of effect:

1. `INSIGHT_MAX_PER_SCAN=3` — roughly 40% fewer calls; the tier-3 cards were
   the weakest anyway.
2. `WORLD_WATCH_NEWS_RESULTS=15` — smaller clustering prompt, fewer stories.
3. More llama.cpp server slots — makes `INSIGHT_ANALYSIS_CONCURRENCY` > 1
   actually pay off, since today two concurrent requests on one GPU each run
   near half speed.

## Key files

| File | Role |
|---|---|
| `src/managers/world_watch.py` | The per-topic pipeline (`scan_topic`) |
| `src/managers/insight_analyzer.py` | Two-phase LLM analysis |
| `src/managers/watch_sources.py` | Source checkers (news/stock/github) |
| `src/managers/insights_manager.py` | Persistence + locking |
| `src/managers/scan_jobs.py` | In-memory on-demand job registry |
| `src/managers/heartbeat_manager.py` | Scheduled trigger + chat push |
| `src/web/routers/insights.py` | HTTP API |
| `order_explorer_site/frontend/src/pages/Insights.tsx` | Dashboard UI |
