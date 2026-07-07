"""Memory search and retrieval tools for the ReACT agent."""
import subprocess
from src.core import config
from src.core.wiki_store import WikiStore
import logging

logger = logging.getLogger('react')


class MemoryTools:
    """Tools for searching and retrieving information from memory files."""

    def __init__(self, user_id: str):
        """Initialize memory tools for a specific user.

        Args:
            user_id: Unique identifier for the user
        """
        self.user_id = user_id
        self.user_memory_dir = config.MEMORY_DIR / str(user_id)
        self.short_term_dir = self.user_memory_dir / "short_term"
        self.long_term_dir = self.user_memory_dir / "long_term"
        self._wiki_store = WikiStore(user_id, self.long_term_dir)

    def _grep_short_term(self, search_term: str, context_lines: int = 2) -> str | None:
        """Grep the daily short-term markdown logs for search_term. Returns
        the raw grep output (with a header), or None if there were no
        matches / the short_term dir doesn't exist yet. Shared by
        search_memory_grep and MemoryRouter.recall so both search short-term
        memory the same way."""
        if not self.short_term_dir.exists():
            return None
        try:
            cmd = [
                'grep', '-r', '-i', '-n',
                f'-C{context_lines}',
                '--', search_term,
                str(self.short_term_dir)
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.stdout:
                return f"### Short-Term Memory Matches\n{proc.stdout}"
        except Exception as e:
            logger.error(f"Error searching short-term memory: {e}")
        return None

    async def search_memory_grep(self, search_term: str, context_lines: int = 2) -> str:
        """Search all memory for a specific term: short-term via grep over
        the daily markdown logs, long-term via a substring match over the
        wiki's page bodies.

        Args:
            search_term: Term to search for
            context_lines: Number of context lines to show before/after
                match (short-term only; long-term wiki matches are whole
                pages, not surrounding lines)

        Returns:
            Search results with file names and matched lines
        """
        logger.info(f"[TOOL] search_memory_grep: searching for '{search_term}' with {context_lines} context lines")

        results = []

        # Search short-term memory
        short_term_matches = self._grep_short_term(search_term, context_lines)
        if short_term_matches:
            results.append(short_term_matches)

        # Search the long-term wiki
        matches = self._wiki_store.search_pages_fulltext(search_term)
        if matches:
            lines = [f"- [{p['title']}] {p['summary']}" for p in matches]
            results.append("### Long-Term Memory Matches\n" + "\n".join(lines))

        if not results:
            return f"No matches found for '{search_term}'"

        return "\n\n".join(results)

    async def save_important_fact(self, category: str, content: str) -> str:
        """Save important information to long-term memory.

        Args:
            category: Category to save to (e.g., 'important_facts', 'relationships', 'personal_preferences')
            content: The information to save

        Returns:
            Success message
        """
        logger.info(f"[TOOL] save_important_fact: saving to '{category}'")

        # Map user-friendly names to canonical concept-page slugs
        category_map = {
            'facts': 'important_facts',
            'important': 'important_facts',
            'important_facts': 'important_facts',
            'relationships': 'relationships',
            'family': 'relationships',
            'preferences': 'personal_preferences',
            'personal_preferences': 'personal_preferences',
            'goals': 'goals_and_projects',
            'projects': 'goals_and_projects',
            'goals_and_projects': 'goals_and_projects',
            'insights': 'key_insights',
            'key_insights': 'key_insights',
            'topics': 'recurring_topics',
            'recurring_topics': 'recurring_topics'
        }

        category_clean = category.lower().replace(' ', '_')
        page_name = category_map.get(category_clean, category_clean)

        try:
            from src.core.memory import MemoryManager

            memory_manager = MemoryManager(self.user_id)
            await memory_manager.add_long_term_memory(page_name, content)

            logger.info(f"Successfully saved to wiki page {page_name}")
            return f"✅ Successfully saved information to long-term memory ({page_name})"

        except Exception as e:
            error_msg = f"Error saving to long-term memory: {e}"
            logger.error(error_msg)
            return f"❌ {error_msg}"

    async def forget_fact(self, search_term: str, category: str = None) -> str:
        """Delete a long-term memory fact the user asked to be forgotten.

        Searches by content first (the LLM never knows a fact's exact
        wiki-page/line address from conversation) and auto-deletes when
        there's exactly one match. When there are multiple matches, lists
        them instead of deleting, so a follow-up call can finish the job
        once the LLM (or, for the Telegram /forget command, the user
        tapping a button) has seen which one was meant.

        Args:
            search_term: Text to search for among stored facts
            category: Optional page title/slug substring to restrict the
                search to (loosely matched, not an exact category anymore -
                the wiki doesn't have a fixed category enum)

        Returns:
            Confirmation message, or a disambiguation list
        """
        logger.info(f"[TOOL] forget_fact: searching for '{search_term}'" + (f" in {category}" if category else ""))

        matches = self._wiki_store.find_matches(search_term)
        if category:
            category_lower = category.lower()
            matches = [
                m for m in matches
                if category_lower in m["title"].lower() or category_lower in m["slug"]
            ]
        if not matches:
            return f"No matching long-term memory found for '{search_term}'."

        if len(matches) == 1:
            return await self.forget_match(matches[0])

        lines = [f"Found {len(matches)} matching facts - which one?"]
        for i, m in enumerate(matches):
            lines.append(f"- [{i}] [{m['title']}] {m['line_text']}")
        return "\n".join(lines)

    async def forget_match(self, match: dict) -> str:
        """Delete a specific fact given a match dict (as returned by
        find_matches()/forget_fact()'s disambiguation list) - a page/slug +
        the verbatim line to remove. Replaces the old id-based
        delete_fact_by_id now that facts don't have persistent UUIDs; the
        page is addressed by type/slug and the fact within it by its exact
        text, which is robust to the page having been lightly re-edited
        since the match was found (the delete just reports "not found" if
        the exact text is gone, rather than deleting the wrong line).

        Args:
            match: {"type", "slug", "title", "line_text"} - as produced by
                WikiStore.find_matches()

        Returns:
            Confirmation message
        """
        logger.info(f"[TOOL] forget_match: {match.get('type')}/{match.get('slug')}")

        deleted = self._wiki_store.delete_line(match["type"], match["slug"], match["line_text"])
        if not deleted:
            return f"No fact found matching \"{match.get('line_text', '')}\" - it may have changed."
        return f"✅ Forgot: \"{match['line_text']}\" (from {match['title']})"
