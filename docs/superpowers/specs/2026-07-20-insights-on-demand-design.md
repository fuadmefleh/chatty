# On-Demand Insights

## Problem

Insights only appear on the heartbeat's schedule. The outer loop ticks every
`HEARTBEAT_INTERVAL_MINUTES` (60 in `.env`), and each topic is additionally
gated by kind — news 24h, stock 4h, github 12h. There is no way to say "check
this now," and no way to ask a question the watchlist doesn't already cover.

The only existing manual trigger is `/heartbeat` in Telegram, which runs the
whole heartbeat and still respects the per-topic interval gate, so it usually
no-ops for insights.

Three capabilities are missing:

1. **Per-topic scan now** — refresh one watchlist topic, ignoring the gate.
2. **Scan all** — refresh every watchlist topic.
3. **Ad-hoc search** — run the pipeline against an arbitrary topic that is not
   on the watchlist, and keep the result.

## Key constraint: the process boundary

`chatty-bot` (`src/main.py`) and `chatty-web-server` (`chatty_web_server.py`)
are **separate pm2 processes**. `HeartbeatManager` — and therefore
`_process_world_watch()` — exists only in the bot process. The web API has its
own singletons in `src/web/state.py` layered over the same JSON files on disk.

A web endpoint therefore cannot call `heartbeat_manager._process_world_watch()`.
This is why the existing "scan now" precedent (`src/web/routers/trending.py:24`)
calls `run_trending_scan(...)`, a module-level function, rather than a
HeartbeatManager method. We follow that pattern.

## Design

### 1. Extract the per-topic pipeline

`_process_world_watch()` (`src/managers/heartbeat_manager.py:792-944`) is a
150-line method with a doubly-nested loop and the entire fetch → analyze →
store pipeline inlined, which is what makes it unreusable.

Extract the per-topic body (currently lines 847-930) into a module-level
function in a new `src/managers/world_watch.py`:

```python
async def scan_topic(
    user_id: str,
    kind: str,
    topic: str,
    *,
    topic_id: str | None = None,
    seen_markers: list[str],
    watchlist_mgr,
    insights_mgr,
    ad_hoc: bool = False,
) -> ScanResult
```

`ScanResult` carries `state` (`"stored" | "nothing_new" | "below_threshold" |
"fetch_failed" | "analysis_failed"`), the created `insight` (or `None`), and
the `analysis` so the caller can decide about pushing.

`_process_world_watch()` then becomes a thin loop: interval gate →
`scan_topic()` → Telegram push. **The heartbeat's behavior is unchanged**;
`tests/test_world_watch.py` should pass essentially as-is, which is the main
safety net for the extraction.

`ad_hoc=True` changes three things:

- **No `mark_run`.** An ad-hoc search must not advance a watchlist topic's
  `last_run_at` or consume its seen-markers, or searching "ai" by hand would
  suppress the next scheduled run.
- **Store gate bypassed.** `INSIGHT_MIN_SIGNIFICANCE_STORE` is not applied, so
  an explicit user action always yields a result rather than silently
  producing nothing on a quiet day.
- **Seen-marker dedup skipped** (`seen_markers=[]`), so an ad-hoc search sees
  the current state of the world rather than only what is new since the last
  scheduled run.

Telegram push is the caller's job, so ad-hoc never pushes: you are already
looking at the screen.

Prior-insight continuity (`get_insights_by_topic`) **is** still fed in for
ad-hoc, so a one-off on an existing topic can reference history.

### 2. Concurrent-write safety

Both processes will now write `data/insights/{user_id}.json`, and
`InsightsManager._save_insights` (`src/managers/insights_manager.py:130`) does
a full-file rewrite with no locking. A heartbeat scan overlapping an on-demand
scan can lose writes.

Add an `fcntl.flock` around the read-modify-write in `InsightsManager`. This is
a latent bug today rather than something this feature introduces — the feature
just makes it much more likely to fire.

### 3. Job registry

Scans run as background jobs so long runs survive gateway timeouts and the
frontend can show per-topic progress.

`src/managers/scan_jobs.py`:

```python
ScanJob:
    id, user_id, status, mode, created_at, finished_at
    targets: [{topic, kind, state, insight_id | None, error | None}]
    error: str | None

status: pending | running | done | failed
```

An in-memory registry keyed by user, held in `src/web/state.py` alongside the
existing `_pi_worker_task`.

Deliberate limits:

- **One in-flight job per user.** A second POST while one is running returns
  `409` with the existing job id, so a double-click cannot fire duplicate LLM
  calls.
- **Jobs are in-memory and die with the process.** `chatty-web-server` restarts
  often; a scan in flight during a restart is lost. The frontend treats a `404`
  on poll as "job vanished — refetch the feed and stop polling" rather than an
  error, since the insight may well have been written before the restart.
  Losing a job costs a re-click, not data — the insight is on disk before the
  job goes terminal — so persisting the registry isn't worth the machinery.
- **Retention:** last 20 jobs per user, no TTL sweeper.

### 4. API

Both routes go in the existing `src/web/routers/insights.py`, inheriting
`require_api_key`.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/chatty/insights/scan` | Start a job → `202 {job_id}` |
| `GET` | `/api/chatty/insights/scan/{job_id}` | Poll status |

One body covers all three modes:

```jsonc
{ "mode": "topic",  "topic_id": "..." }
{ "mode": "all" }
{ "mode": "adhoc", "topic": "TSLA", "kind": "stock" }
```

The endpoint validates, creates the job, fires `asyncio.create_task(...)`, and
returns immediately. The task updates `job.targets[i].state` as each topic
completes.

`GET /api/chatty/insights` gains an `include_ad_hoc` param (default `false`),
so the default feed is unchanged for existing consumers.

### 5. Schema

`Insight` gains `ad_hoc: bool = False`, defaulted in `from_dict` so existing
records load unchanged. `schema_version` is untouched — this is an additive
field with a safe default, not a layout change.

### 6. Ad-hoc kind selection

The search box has an explicit `news | stock | github` dropdown, defaulting to
`news`. The three fetchers are not interchangeable (`check_stock("Anthropic
funding")` is meaningless), and inference from the string is wrong on exactly
the cases hit first — `AI` is both a valid ticker and an existing news topic.

### 7. Frontend

`order_explorer_site/frontend/src/pages/Insights.tsx` and `src/chattyApi.ts`.

- **Search bar** at the top: text input + kind dropdown + Search button →
  `mode: "adhoc"`.
- **Refresh icon** on each watchlist topic chip → `mode: "topic"`.
- **"Scan all"** secondary button next to the topic list → `mode: "all"`.
- **Progress panel** while a job is live, listing each target and its state.
  Polls every 2s; on terminal status, stops polling and calls the existing
  `load()` to refetch.
- **Ad-hoc results hidden by default**, with a "Show ad-hoc results" toggle
  near the existing topic filter chips. A just-completed ad-hoc search
  **auto-reveals** — otherwise you would search, watch the spinner finish, and
  see nothing appear, which reads as a bug.
- **All three triggers disable** while a job is in flight, mirroring the
  one-job-per-user server rule so a `409` is unreachable through the UI.

Explicitly out of scope: search history, saved searches, and "promote this
ad-hoc result to a watchlist topic."

## Testing

Extends `tests/test_world_watch.py`, `tests/test_insights_manager.py`.

- **`scan_topic()`** — each kind; failure paths (fetch returns `None`, analyzer
  returns `None`); `ad_hoc=True` does not call `mark_run` and does not apply
  the store gate.
- **Heartbeat regression** — existing `test_world_watch.py` tests pass
  unchanged after the extraction. If they need rewriting, the extraction
  changed behavior it should not have.
- **Job lifecycle** — pending → running → done; per-target states; one failing
  target does not fail the whole job; second POST returns 409.
- **Schema back-compat** — an insight dict without `ad_hoc` loads as `False`.
- **Locking** — concurrent `add_insight` calls do not lose writes.

## Cost and latency

Unchanged per scan: one fetch + one `gpt-5-nano` call per topic with findings
(stock adds one enrichment search). On-demand simply moves who decides when.
The one-job-per-user rule bounds the blast radius of an impatient user.

**Measured:** a single-topic news scan took **~90 seconds** end to end, far
above the few-seconds estimate this design started from. SearXNG aggregation
dominates; the `gpt-5-nano` call is a small share. Two consequences:

- Background jobs were the right call. A blocking request at this latency
  would sit at real risk of a proxy/gateway timeout, and "scan all" over
  several topics runs serially on top of that.
- The frontend's 2s poll is comfortably fine-grained; the per-target progress
  panel is doing real work here rather than flashing by.

If scan-all over many topics becomes routine, running targets concurrently
rather than serially is the obvious next lever — but that is speculative until
the watchlist is bigger than one topic.
