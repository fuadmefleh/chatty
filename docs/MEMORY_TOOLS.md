# Memory Tools for the ReACT Agent

## Overview

Both `StagedReACTAgent` and `WebChatAgent` (see [ARCHITECTURE.md](ARCHITECTURE.md))
have access to memory via `MemoryRouter` (`src/core/memory_router.py`), which
exposes exactly three tools to the LLM through native OpenAI/Anthropic function
calling - not parsed from free-form text. `MemoryRouter` fans out to
`MemoryTools`/`LongTermFactsStore` under the hood; long-term memory itself is
stored as individually addressable facts (`src/core/long_term_facts.py`'s
`LongTermFactsStore`), not files - see [MEMORY_SYSTEM.md](MEMORY_SYSTEM.md).

This replaces an earlier 11-tool surface (`search_memory_grep`,
`list_memory_files`, `read_memory_file`, `search_by_date_range`,
`search_pattern`, `get_memory_summary`, `search_recent_mentions`,
`save_important_fact`, `forget_fact`, `delete_fact_by_id`,
`semantic_search_memory`) that had grown organically and left the LLM guessing
which of several overlapping search tools to call. Those `MemoryTools` methods
still exist and are still called directly (not via LLM tool-calling) by
`main.py`'s `/forget` Telegram command and `chatty_web_server.py`'s
`/api/chatty/memory*` endpoints.

## Tools exposed to the LLM

All three are defined once in `get_tool_definitions()`
(`src/core/memory_router.py`) and imported by both agents, so their schemas
and dispatch (`MEMORY_TOOL_NAMES`) can't drift apart between Telegram and web.

### 1. `recall(query, top_k=5)`
Finds memory relevant to `query`: semantically-ranked long-term facts
(embedding cosine similarity, falling back to/topped up by substring search
if embeddings are unavailable), plus recent short-term conversation excerpts
(grep). Replaces having to choose between `search_memory_grep`,
`search_pattern`, `search_recent_mentions`, and `semantic_search_memory`.

### 2. `remember(content, category=None)`
Saves a fact to long-term memory. `category` defaults to `important_facts`
if omitted; any category name is accepted (not restricted to the 6 canonical
ones - those are just a display-order hint, see `long_term_facts.py`'s
`CANONICAL_CATEGORY_ORDER`).

### 3. `forget(query)`
Deletes a long-term fact matching `query`. Auto-deletes when there's exactly
one match; with multiple matches, asks to call `forget` again with more
specific wording (this 3-tool surface has no id-based delete for the LLM to
call - `main.py`'s `/forget` Telegram command still uses the id-based
`forget_fact`/`delete_fact_by_id` flow directly via inline buttons, since a
human tapping a button can disambiguate by id in a way the LLM can't).

## A past bug worth knowing about

Under the old 11-tool surface, `search_memory_grep`'s advertised schema and
its Python implementation used to disagree on the parameter name (`pattern`
vs. `search_term`), and `save_important_fact`'s schema once advertised `fact`
where the real method took `content` - both meant every LLM-initiated call
failed silently, caught by `_execute_memory_tool`'s try/except and returned as
an inert `"Error executing <tool>: ..."` string instead of a real result or a
visible crash. A second, related bug: `_execute_tool()`'s dispatch gate used
to be a `startswith()` prefix tuple that didn't match some tool names at all,
silently misrouting those calls to `skills_manager.execute_tool()`
(`"Unknown tool: ..."`) instead of ever reaching `MemoryTools`.
`tests/test_staged_react_agent.py`'s `TestMemoryToolSchema` asserts every
advertised tool's parameter names are actually callable **through
`_execute_tool()`** (the real dispatch entry point) and that the surface
stays at exactly 3 tools - worth checking first if a memory tool call ever
silently returns an "Error executing ..." or "Unknown tool ..." string, or if
the tool count creeps back up.

## Manual testing

```bash
pytest tests/test_memory_tools.py tests/test_memory_router.py tests/test_staged_react_agent.py tests/test_web_chat_agent.py tests/test_long_term_facts.py -v
```
