"""LLM-facing memory surface: recall/remember/forget.

The only memory tools advertised to the LLM (both StagedReACTAgent and
WebChatAgent) - fans out to WikiStore (src/core/wiki_store.py) and MemoryTools,
fusing index-first, keyword-scored long-term wiki lookup with short-term
grep into one ranked/rendered result, instead of making the LLM guess which
of several overlapping search tools to call. MemoryTools' other methods stay
Python-callable (main.py's /forget command and chatty_web_server.py's
/api/chatty/memory* endpoints call them directly) but are no longer part of
the LLM tool schema.
"""
import json
import logging
from typing import Dict, List, Optional

from src.core.memory_tools import MemoryTools

logger = logging.getLogger('react')

# Single source of truth for which tool names route to the memory router,
# imported by both staged_react_agent.py and web_chat_agent.py so they can
# never drift apart on which names dispatch where.
MEMORY_TOOL_NAMES = {"recall", "remember", "forget"}

# Short-term grep results are unscored and can be long; cap how many
# separate match groups get included so recall()'s output stays bounded
# regardless of how noisy the match is.
SHORT_TERM_EXCERPT_CAP = 3

# Above this many wiki pages, a blind full-text grep fallback (when keyword
# scoring finds nothing) gets noisy - fall back to one LLM call over the
# index instead. At or below this, full-text search is cheap and precise
# enough that an LLM call isn't worth the latency/cost.
_FULLTEXT_FALLBACK_MAX_PAGES = 15

_TYPE_LABEL = {"entity": "entities", "concept": "concepts"}


def _cap_short_term_excerpts(short_term_block: str, cap: int = SHORT_TERM_EXCERPT_CAP) -> str:
    """short_term_block is '### Short-Term Memory Matches\\n<grep -C output>'.
    grep separates non-contiguous context groups with a '--' line; keep only
    the first `cap` groups."""
    header, _, body = short_term_block.partition("\n")
    groups = body.split("--\n")
    capped = "--\n".join(groups[:cap])
    return f"{header}\n{capped}".rstrip()


class MemoryRouter:
    """Fuses index-first long-term wiki lookup and short-term grep into a
    single recall() call, plus remember()/forget()."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        # Reuse MemoryTools' own WikiStore/short-term dir rather than
        # constructing a second store against the same wiki files.
        self.memory_tools = MemoryTools(user_id)

    async def recall(self, query: str, top_k: int = 5) -> str:
        """Find memory relevant to `query`: keyword-scored long-term wiki
        pages (index-first, no embeddings - falling back to full-text
        search on a small wiki, or one LLM call over the index on a larger
        one, if keyword scoring finds nothing), plus recent short-term
        conversation excerpts."""
        wiki_store = self.memory_tools._wiki_store
        pages = wiki_store.list_pages()

        selected: List[Dict] = []
        if pages:
            selected = wiki_store.search_index(query, top_k=top_k)
            if not selected:
                if len(pages) <= _FULLTEXT_FALLBACK_MAX_PAGES:
                    selected = wiki_store.search_pages_fulltext(query, top_k=top_k)
                else:
                    selected = await self._llm_select_pages(query, wiki_store, top_k=top_k)

        sections = []
        if selected:
            blocks = []
            for page in selected:
                type_label = _TYPE_LABEL.get(page["type"], page["type"])
                header = f"#### {page['title']} ({type_label}/{page['slug']})"
                blocks.append(f"{header}\n{page['body']}")
            sections.append("### Long-Term Memory\n" + "\n\n".join(blocks))

        short_term_matches = self.memory_tools._grep_short_term(query, context_lines=1)
        if short_term_matches:
            sections.append(_cap_short_term_excerpts(short_term_matches))

        if not sections:
            return f"No memory found for '{query}'."

        return "\n\n".join(sections)

    async def _llm_select_pages(self, query: str, wiki_store, top_k: int) -> List[Dict]:
        """Ask the LLM which wiki pages (given just the index catalog, not
        every page body) are relevant to `query`. Only reached when keyword
        scoring over the index found zero candidates and the wiki is too
        large for a blind full-text grep fallback to be precise."""
        try:
            from src.core.llm import get_llm_provider, with_retries

            index_text = wiki_store.read_index()
            prompt = (
                "Given this wiki index and a query, list which pages (if any) are "
                "relevant to the query. Respond with ONLY a JSON object of this "
                'exact shape: {"pages": [{"type": "entity"|"concept", "slug": "..."}, ...]}. '
                'If nothing is relevant, respond {"pages": []}.\n\n'
                f"Wiki index:\n{index_text}\n\nQuery: {query}"
            )
            llm = get_llm_provider()
            response = await with_retries(
                lambda: llm.complete(
                    [{"role": "user", "content": prompt}],
                    response_format="json", temperature=0.0,
                ),
                logger=logger,
            )
            data = json.loads(response.content)
        except Exception as e:
            logger.error(f"Error in LLM page selection for recall: {e}")
            return []

        selected = []
        for entry in data.get("pages", [])[:top_k]:
            page = wiki_store.get_page(entry.get("type", ""), entry.get("slug", ""))
            if page:
                selected.append(page)
        return selected

    async def remember(self, content: str, category: Optional[str] = None) -> str:
        """Save a fact to long-term memory. `category` (the wiki concept
        page it's filed under) defaults to 'important_facts' if not given;
        any category name is accepted."""
        return await self.memory_tools.save_important_fact(
            category=category or "important_facts", content=content
        )

    async def forget(self, query: str) -> str:
        """Delete a long-term memory fact matching `query`. Auto-deletes on
        a single match; on multiple matches, asks to call forget again with
        more specific wording (this 3-tool surface has no id-based delete
        for the LLM to call - unlike main.py's /forget Telegram command,
        which still uses a button-based pick-one-of-N flow directly)."""
        result = await self.memory_tools.forget_fact(search_term=query)
        if result.startswith("Found ") and "which one?" in result:
            result += "\n\nCall forget again with more specific wording to narrow it down to one."
        return result


def get_tool_definitions() -> List[Dict]:
    """OpenAI function-calling schema for recall/remember/forget - defined
    once here, imported by both staged_react_agent.py and web_chat_agent.py."""
    return [
        {
            "type": "function",
            "function": {
                "name": "recall",
                "description": (
                    "Search memory (long-term facts and recent short-term conversation "
                    "logs) for information relevant to a query. Combines semantic and "
                    "keyword search automatically - use this instead of guessing which "
                    "search mechanism to use."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Natural-language description of what to recall"},
                        "top_k": {"type": "integer", "description": "Max number of long-term facts to return (default 5)"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "remember",
                "description": "Save an important fact to long-term memory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "The information to remember"},
                        "category": {
                            "type": "string",
                            "description": (
                                "Category to file this under, e.g. 'important_facts', "
                                "'relationships', 'personal_preferences', or any other "
                                "short label. Defaults to 'important_facts' if omitted."
                            ),
                        },
                    },
                    "required": ["content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "forget",
                "description": (
                    "Delete a long-term memory fact the user asked to be forgotten. "
                    "Searches by content; auto-deletes if there's exactly one match, "
                    "otherwise lists candidates and asks you to call forget again with "
                    "more specific wording."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Text to search for among stored facts, e.g. 'sushi' or 'old job'"},
                    },
                    "required": ["query"],
                },
            },
        },
    ]
