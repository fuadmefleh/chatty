# Memory Tools for the ReACT Agent

## Overview

`StagedReACTAgent` (see [ARCHITECTURE.md](ARCHITECTURE.md)) has access to memory
search and retrieval tools implemented in `src/core/memory_tools.py`'s
`MemoryTools` class. These are always available regardless of which skills are
loaded, and are called via native OpenAI/Anthropic function calling - not
parsed from free-form text.

## Tools currently exposed to the LLM

Only three of `MemoryTools`' methods are actually advertised to the model
today (`_get_memory_tools_definitions()` in `staged_react_agent.py`):

### 1. `search_memory_grep(search_term)`
Greps all memory files (short-term and long-term) for a term, case-insensitive,
with surrounding context lines.

### 2. `save_important_fact(fact, category)`
Saves a fact directly to long-term memory. `category` is one of: preference,
personal, goal, other.

### 3. `get_memory_summary()`
Returns an overview of what memory is available (file counts, categories),
with no arguments.

## Additional methods that exist but aren't currently wired up

`MemoryTools` also implements `list_memory_files`, `read_memory_file`,
`search_by_date_range`, and `search_recent_mentions` - and
`_execute_memory_tool()` has dispatch cases ready for all of them - but none
are included in `_get_memory_tools_definitions()`'s advertised schema, so the
LLM currently has no way to call them. Wiring them up would just mean adding
their OpenAI function-calling schemas to that method; the implementations and
dispatch are already in place.

## A past bug worth knowing about

`search_memory_grep`'s advertised schema and its Python implementation used
to disagree on the parameter name (`pattern` vs. `search_term`), so every
LLM-initiated call failed silently - caught by `_execute_memory_tool`'s
try/except and returned as an inert `"Error executing search_memory_grep: ..."`
string instead of a real result or a visible crash. `tests/test_staged_react_agent.py`'s
`TestMemoryToolSchema` now asserts the advertised parameter names are actually
callable, specifically to catch this class of regression - worth checking
first if a memory tool call ever silently returns an "Error executing ..." string.

## Manual testing

```bash
pytest tests/test_memory_tools.py tests/test_staged_react_agent.py -v
```
