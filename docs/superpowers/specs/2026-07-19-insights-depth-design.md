# Insights: depth, volume, and continuity

## Problem

The Insights feature surfaces too little, too shallowly, with no memory of
itself.

A news insight today is: 8 SearXNG results, filtered to unseen URLs, through
one LLM call that returns 2-4 sentences or the literal string
`NOTHING_NOTABLE`. Stock and GitHub insights never touch an LLM at all -
they're `str.format` output. Stored insights average ~750 characters and
reference nothing that came before them, so three consecutive `ai` insights
read as three unrelated blobs rather than a developing story.

Three things are wrong:

1. **Shallow.** A paragraph summary states what happened and stops. No
   analysis of why it matters or what to watch next.
2. **Suppressive.** The binary `NOTHING_NOTABLE` gate discards everything
   that isn't clearly notable. Marginal-but-real items vanish entirely.
3. **Amnesiac.** Each insight is isolated. Nothing connects a new development
   to the prior insight it follows up on or contradicts.

## Design

### Insight schema

Existing fields (`id`, `topic`, `summary`, `sources`, `created_at`,
`user_id`) stay. Added:

| Field | Type | Purpose |
|---|---|---|
| `kind` | `"news" \| "stock" \| "github"` | Currently lost at write time; needed to render and filter |
| `significance` | `int` 1-5 | Drives storage, push, and collapse decisions |
| `headline` | `str` | One-line title; the collapsed-state text |
| `what_happened` | `str` | The factual core |
| `why_it_matters` | `str` | The analysis missing today |
| `what_to_watch` | `List[str]` | Forward-looking bullets |
| `entities` | `List[str]` | Companies/people/repos; also feeds continuity matching |
| `connection` | `{prior_insight_id, relation, note} \| None` | `follows_up` / `contradicts` / `escalates` |
| `schema_version` | `int` | Distinguishes new records from legacy |

`summary` is retained and populated with a digest of the structured fields.
It is what the daily briefing (`heartbeat_manager._build_daily_briefing`) and
the push message consume, and what existing stored records already have.

**Backward compatibility.** `Insight.from_dict` defaults every new field, so
legacy records load without migration. The frontend renders the old flat
layout when `headline` is absent. No migration script - the existing corpus
is 4 records and ages out naturally.

### New module: `src/managers/insight_analyzer.py`

`heartbeat_manager.py` is ~1250 lines and `_process_world_watch` is 110 of
them. Three per-kind prompts plus JSON parsing plus validation would roughly
double that method, so analysis becomes its own unit:

```python
async def analyze(kind, topic, items, prior_insights) -> Optional[Analysis]
```

It owns prompt construction per kind, the LLM call, JSON parsing, and field
validation. `heartbeat_manager` keeps orchestration only: fetch -> analyze ->
store -> notify. The module is testable without a heartbeat loop.

**Parse failure degrades, never drops.** If the model returns unparseable
JSON, the raw text becomes `what_happened` with `significance = 2`. A
degraded insight beats a silently lost one. This is the largest reliability
risk in the change and is handled explicitly rather than left to an
exception handler.

### Significance tiers

`NOTHING_NOTABLE` is removed. The analyzer returns 1-5:

- **1** - spam, recycled, irrelevant. Discarded, not stored.
- **2-3** - real but minor. Stored, rendered collapsed, **no push message**.
- **4-5** - genuinely notable. Stored, rendered expanded, push message sent.

Thresholds live in `src/core/config.py` as
`INSIGHT_MIN_SIGNIFICANCE_STORE` (default 2) and
`INSIGHT_PUSH_MIN_SIGNIFICANCE` (default 4), tunable without a code change.

Net effect: items that today return `NOTHING_NOTABLE` and vanish now land in
the feed at tier 2-3. More is surfaced, while notifications get *quieter* -
today every surfaced news insight pings the user.

### Continuity

`InsightsManager.get_insights_by_topic(user_id, topic, limit=5)` feeds the
analyzer prior insights as `(id, created_at, headline, entities)`. The prompt
requests `connection` only where a genuine link exists - a nullable field,
not a required one, so the model cannot manufacture a relationship to fill a
slot. A `connection` whose `prior_insight_id` doesn't match a real insight is
dropped at validation. The frontend renders it as a link to the referenced
insight.

The prior-context count is `INSIGHT_PRIOR_CONTEXT_COUNT` (default 5).

### Per-kind depth

- **news** - retrieval unchanged (8 results, unseen only); structured
  analysis over them.
- **stock** - the `STOCK_WATCH_MOVE_THRESHOLD_PERCENT` pre-filter stays as a
  cheap deterministic gate. Once a move clears it, the analyzer additionally
  receives a `check_news(symbol)` result so the insight explains *why* the
  move happened.
- **github** - release body raised from 300 to 2000 characters; release notes
  and commit titles go through the analyzer to describe what actually
  changed.

### API and frontend

`GET /api/chatty/insights` gains an optional `min_significance` query
parameter and returns the new fields.

`Insights.tsx` gains a tier indicator, section rendering, collapsed cards for
tier 2-3 that expand on click, a connection link, and a topic filter. Records
without `headline` fall through to the current flat rendering.

### Cost

Stock insights go from 0 to 1 LLM call plus 1 search; GitHub from 0 to 1
call; news stays at 1 call with a longer prompt. These fire only when a check
finds something new - single-digit additional calls per day at current
watchlist size.

## Testing

Extending `tests/test_world_watch.py`:

- analyzer parses well-formed JSON into an `Analysis`
- malformed JSON degrades to tier 2 rather than dropping the insight
- missing optional fields default cleanly
- tier 1 is not stored
- tier 3 is stored without sending a push message
- tier 4 is stored and pushed
- a `connection` referencing an unknown insight id is dropped
- legacy flat records round-trip through `from_dict` / `to_dict`
