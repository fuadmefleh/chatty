"""LLM-facing memory surface: recall/remember/forget.

The only memory tools advertised to the LLM (both StagedReACTAgent and
WebChatAgent) - fans out to the existing LongTermFactsStore/MemoryTools
primitives and fuses their results into one ranked list, instead of making
the LLM guess which of several overlapping search tools to call.
MemoryTools' other methods stay Python-callable (main.py's /forget command
and chatty_web_server.py's /api/chatty/memory* endpoints call them
directly) but are no longer part of the LLM tool schema.
"""
import logging
from typing import Dict, List, Optional, Tuple

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


def _cap_short_term_excerpts(short_term_block: str, cap: int = SHORT_TERM_EXCERPT_CAP) -> str:
    """short_term_block is '### Short-Term Memory Matches\\n<grep -C output>'.
    grep separates non-contiguous context groups with a '--' line; keep only
    the first `cap` groups."""
    header, _, body = short_term_block.partition("\n")
    groups = body.split("--\n")
    capped = "--\n".join(groups[:cap])
    return f"{header}\n{capped}".rstrip()


class MemoryRouter:
    """Fuses long-term semantic/keyword search and short-term grep into a
    single recall() call, plus remember()/forget()."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        # Reuse MemoryTools' own LongTermFactsStore/short-term dir rather
        # than constructing a second store against the same facts.json.
        self.memory_tools = MemoryTools(user_id)

    async def recall(self, query: str, top_k: int = 5) -> str:
        """Find memory relevant to `query`: semantically-ranked long-term
        facts (falling back to/topped up by substring search), plus recent
        short-term conversation excerpts."""
        facts_store = self.memory_tools._facts_store

        scored: List[Tuple[Dict, Optional[float]]] = []
        seen_ids = set()

        try:
            # Local import (not module-level) so tests can monkeypatch
            # src.core.embeddings.get_embedding - matches the pattern used
            # by MemoryManager.add_long_term_memory / MemoryTools.semantic_search_memory.
            from src.core.embeddings import get_embedding

            query_embedding = await get_embedding(query)
        except Exception as e:
            logger.error(f"Error embedding query for recall: {e}")
            query_embedding = None

        if query_embedding is not None:
            for fact, score in facts_store.semantic_search(query_embedding, top_k=top_k):
                scored.append((fact, score))
                seen_ids.add(fact["id"])

        if len(scored) < top_k:
            for fact in facts_store.search_facts(query):
                if fact["id"] in seen_ids:
                    continue
                scored.append((fact, None))
                seen_ids.add(fact["id"])
                if len(scored) >= top_k:
                    break

        sections = []
        if scored:
            lines = []
            for fact, score in scored:
                if score is not None:
                    lines.append(f"- ({score:.2f}) [{fact['category']}] {fact['content']}")
                else:
                    lines.append(f"- [{fact['category']}] {fact['content']}")
            sections.append("### Long-Term Memory\n" + "\n".join(lines))

        short_term_matches = self.memory_tools._grep_short_term(query, context_lines=1)
        if short_term_matches:
            sections.append(_cap_short_term_excerpts(short_term_matches))

        if not sections:
            return f"No memory found for '{query}'."

        return "\n\n".join(sections)

    async def remember(self, content: str, category: Optional[str] = None) -> str:
        """Save a fact to long-term memory. `category` defaults to
        'important_facts' if not given; any category name is accepted."""
        return await self.memory_tools.save_important_fact(
            category=category or "important_facts", content=content
        )

    async def forget(self, query: str) -> str:
        """Delete a long-term memory fact matching `query`. Auto-deletes on
        a single match; on multiple matches, asks to call forget again with
        more specific wording (this 3-tool surface has no id-based
        delete_fact_by_id for the LLM to call - unlike main.py's /forget
        Telegram command, which still uses the id-based flow directly)."""
        result = await self.memory_tools.forget_fact(search_term=query)
        if result.startswith("Found ") and "Call delete_fact_by_id" in result:
            lines = result.split("\n")
            lines[0] = lines[0].replace(
                "Call delete_fact_by_id with the id:",
                "Call forget again with more specific wording to narrow it down to one:",
            )
            result = "\n".join(lines)
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
