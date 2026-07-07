# Memory Tools for the ReACT Agent

## Overview

`StagedReACTAgent` (see [ARCHITECTURE.md](ARCHITECTURE.md)) has access to memory
search and retrieval tools implemented in `src/core/memory_tools.py`'s
`MemoryTools` class. These are always available regardless of which skills are
loaded, and are called via native OpenAI/Anthropic function calling - not
parsed from free-form text. Long-term memory itself is stored as individually
addressable facts (`src/core/long_term_facts.py`'s `LongTermFactsStore`), not
files - see [MEMORY_SYSTEM.md](MEMORY_SYSTEM.md).

## Tools exposed to the LLM

All of `MemoryTools`' methods are advertised via
`_get_memory_tools_definitions()` in `staged_react_agent.py`:

### 1. `search_memory_grep(search_term)`
Greps short-term daily logs for a term, and substring-matches long-term
facts, case-insensitive.

### 2. `save_important_fact(category, content)`
Saves a fact directly to long-term memory. `category` is one of the 6
canonical categories (personal_preferences, important_facts,
goals_and_projects, relationships, recurring_topics, key_insights).

### 3. `get_memory_summary()`
Returns an overview of what memory is available (counts, categories), with
no arguments.

### 4. `list_memory_files(memory_type="all")`
Lists short-term daily log files and/or long-term categories (with fact
counts per category).

### 5. `read_memory_file(filename, memory_type="short_term")`
Reads a specific short-term daily file, or (for `memory_type="long_term"`)
all facts in a named category.

### 6. `search_by_date_range(start_date, end_date)`
Gets short-term conversation logs between two dates (inclusive). Short-term
only - long-term facts don't have a date-range concept.

### 7. `search_pattern(regex_pattern, memory_type="all")`
Regex search over short-term daily logs and/or long-term fact contents.

### 8. `search_recent_mentions(topic, days=7)`
Finds recent mentions of a topic in the last N days of short-term memory.
Short-term only, by design - recency is a short-term-memory concept; a
long-term fact is already curated/permanent, not something to search "in the
last N days".

### 9. `forget_fact(search_term, category=None)`
Deletes a long-term fact the user asked to be forgotten. Searches by content
(the LLM doesn't know a fact's id from conversation) and auto-deletes when
there's exactly one match; with multiple matches, lists candidates with ids
for a follow-up `delete_fact_by_id` call instead of deleting.

### 10. `delete_fact_by_id(fact_id)`
Deletes a specific fact by id, typically following a `forget_fact` call that
found multiple candidates.

### 11. `semantic_search_memory(query, top_k=5)`
Ranks long-term facts by embedding cosine similarity to `query` - useful for
vague/conceptual recall ("what does the user like to eat?") where
`search_memory_grep` would need an exact keyword. Additive, not a
replacement: it only covers long-term facts (short-term daily logs aren't
embedded) and needs a working `OPENAI_API_KEY`; `search_memory_grep` remains
the zero-dependency fallback. See `src/core/embeddings.py`.

## A past bug worth knowing about

`search_memory_grep`'s advertised schema and its Python implementation used
to disagree on the parameter name (`pattern` vs. `search_term`), and
`save_important_fact`'s schema once advertised `fact` where the real method
took `content` - both meant every LLM-initiated call failed silently, caught
by `_execute_memory_tool`'s try/except and returned as an inert
`"Error executing <tool>: ..."` string instead of a real result or a visible
crash. A second, related bug: `_execute_tool()`'s dispatch gate used to be a
`startswith()` prefix tuple that didn't match `search_by_date_range`,
`search_pattern`, or `search_recent_mentions` at all, silently misrouting
those calls to `skills_manager.execute_tool()` (`"Unknown tool: ..."`)
instead of ever reaching `MemoryTools`. `tests/test_staged_react_agent.py`'s
`TestMemoryToolSchema` now asserts every advertised tool's parameter names
are actually callable **through `_execute_tool()`** (the real dispatch entry
point, not just `_execute_memory_tool()` directly) - worth checking first if
a memory tool call ever silently returns an "Error executing ..." or
"Unknown tool ..." string.

## Manual testing

```bash
pytest tests/test_memory_tools.py tests/test_staged_react_agent.py tests/test_long_term_facts.py -v
```
