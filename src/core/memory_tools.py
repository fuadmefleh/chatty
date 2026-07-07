"""Memory search and retrieval tools for the ReACT agent."""
import re
import subprocess
import aiofiles
from pathlib import Path
from datetime import datetime, timedelta
from src.core import config
from src.core.long_term_facts import LongTermFactsStore
import logging

logger = logging.getLogger('react')


def _resolve_memory_path(base_dir: Path, filename: str) -> Path | None:
    """Resolve `filename` under `base_dir`, rejecting any path that escapes it.

    Mirrors the containment check used by chatty_web_server.py's
    _resolve_code_path() - required here because `filename` can come from
    LLM tool-call arguments (prompt injection surface), not just trusted
    callers.
    """
    candidate = (base_dir / (filename or "").strip().lstrip("/")).resolve()
    try:
        candidate.relative_to(base_dir.resolve())
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


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
        self._facts_store = LongTermFactsStore(user_id, self.long_term_dir)

    async def search_memory_grep(self, search_term: str, context_lines: int = 2) -> str:
        """Search all memory for a specific term: short-term via grep over
        the daily markdown logs, long-term via a substring match over
        stored facts.

        Args:
            search_term: Term to search for
            context_lines: Number of context lines to show before/after
                match (short-term only; long-term facts are single entries
                with no surrounding lines)

        Returns:
            Search results with file names and matched lines
        """
        logger.info(f"[TOOL] search_memory_grep: searching for '{search_term}' with {context_lines} context lines")

        results = []

        # Search short-term memory
        if self.short_term_dir.exists():
            try:
                cmd = [
                    'grep', '-r', '-i', '-n',
                    f'-C{context_lines}',
                    '--', search_term,
                    str(self.short_term_dir)
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True)
                if proc.stdout:
                    results.append(f"### Short-Term Memory Matches\n{proc.stdout}")
            except Exception as e:
                logger.error(f"Error searching short-term memory: {e}")

        # Search long-term memory facts
        matches = self._facts_store.search_facts(search_term)
        if matches:
            lines = [f"- [{f['category']}] {f['content']}" for f in matches]
            results.append("### Long-Term Memory Matches\n" + "\n".join(lines))

        if not results:
            return f"No matches found for '{search_term}'"

        return "\n\n".join(results)
    
    async def list_memory_files(self, memory_type: str = "all") -> str:
        """List all available memory files.
        
        Args:
            memory_type: Type of memory to list ('short_term', 'long_term', or 'all')
            
        Returns:
            Formatted list of memory files with dates/categories
        """
        logger.info(f"[TOOL] list_memory_files: listing {memory_type} memory files")
        
        results = []
        
        if memory_type in ["short_term", "all"]:
            if self.short_term_dir.exists():
                files = sorted(self.short_term_dir.glob("*.md"), reverse=True)
                if files:
                    results.append("### Short-Term Memory Files (Daily Logs)")
                    for f in files:
                        stat = f.stat()
                        size_kb = stat.st_size / 1024
                        results.append(f"- {f.name} ({size_kb:.1f} KB)")
        
        if memory_type in ["long_term", "all"]:
            categories = self._facts_store.list_categories()
            if categories:
                results.append("\n### Long-Term Memory Categories")
                for category in categories:
                    count = len(self._facts_store.list_facts(category=category))
                    results.append(f"- {category} ({count} facts)")

        if not results:
            return "No memory files found"

        return "\n".join(results)
    
    async def read_memory_file(self, filename: str, memory_type: str = "short_term") -> str:
        """Read a specific memory file, or (for long_term) a category's facts.

        Args:
            filename: Name of the short-term file to read (e.g.,
                '2026-01-30.md'), or a long-term category name (e.g.
                'important_facts', with or without a trailing '.md')
            memory_type: Type of memory ('short_term' or 'long_term')

        Returns:
            Content of the memory file / category
        """
        logger.info(f"[TOOL] read_memory_file: reading {memory_type}/{filename}")

        if memory_type == "long_term":
            category = filename[:-3] if filename.endswith(".md") else filename
            facts = self._facts_store.list_facts(category=category)
            if not facts:
                return f"No long-term memory found for category '{category}'"
            from src.core.long_term_facts import render_category_facts
            return render_category_facts(category, facts)

        if memory_type != "short_term":
            return f"Invalid memory_type '{memory_type}'. Use 'short_term' or 'long_term'"

        file_path = _resolve_memory_path(self.short_term_dir, filename)
        if file_path is None:
            return f"File not found: {filename}"

        try:
            async with aiofiles.open(file_path, 'r') as f:
                content = await f.read()
                return content
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return f"Error reading file: {str(e)}"
    
    async def search_by_date_range(self, start_date: str, end_date: str) -> str:
        """Search short-term memories within a date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            Combined content from files in the date range
        """
        logger.info(f"[TOOL] search_by_date_range: {start_date} to {end_date}")
        
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as e:
            return f"Invalid date format. Use YYYY-MM-DD: {str(e)}"
        
        if not self.short_term_dir.exists():
            return "No short-term memory directory found"
        
        results = []
        current = start
        
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            file_path = self.short_term_dir / f"{date_str}.md"
            
            if file_path.exists():
                try:
                    async with aiofiles.open(file_path, 'r') as f:
                        content = await f.read()
                        results.append(f"## {date_str}\n{content}")
                except Exception as e:
                    logger.error(f"Error reading {file_path}: {e}")
            
            current += timedelta(days=1)
        
        if not results:
            return f"No memory files found between {start_date} and {end_date}"
        
        return "\n\n".join(results)
    
    async def search_pattern(self, regex_pattern: str, memory_type: str = "all") -> str:
        """Search memory files using a regex pattern.
        
        Args:
            regex_pattern: Regular expression pattern to search for
            memory_type: Type of memory to search ('short_term', 'long_term', or 'all')
            
        Returns:
            Matches with context
        """
        logger.info(f"[TOOL] search_pattern: pattern '{regex_pattern}' in {memory_type}")
        
        try:
            pattern = re.compile(regex_pattern, re.IGNORECASE)
        except re.error as e:
            return f"Invalid regex pattern: {str(e)}"
        
        results = []

        async def search_directory(directory: Path, label: str):
            if not directory.exists():
                return

            matches = []
            for file_path in directory.glob("*.md"):
                try:
                    async with aiofiles.open(file_path, 'r') as f:
                        content = await f.read()
                        lines = content.split('\n')

                        for i, line in enumerate(lines):
                            if pattern.search(line):
                                # Get context
                                start = max(0, i - 2)
                                end = min(len(lines), i + 3)
                                context = '\n'.join(lines[start:end])
                                matches.append(f"**{file_path.name}:{i+1}**\n```\n{context}\n```\n")
                except Exception as e:
                    logger.error(f"Error searching {file_path}: {e}")

            if matches:
                results.append(f"### {label}\n" + "\n".join(matches))

        if memory_type in ["short_term", "all"]:
            await search_directory(self.short_term_dir, "Short-Term Memory Matches")

        if memory_type in ["long_term", "all"]:
            fact_matches = [
                f"**{fact['category']}/{fact['id'][:8]}**\n{fact['content']}\n"
                for fact in self._facts_store.list_facts()
                if pattern.search(fact["content"])
            ]
            if fact_matches:
                results.append("### Long-Term Memory Matches\n" + "\n".join(fact_matches))

        if not results:
            return f"No matches found for pattern '{regex_pattern}'"

        return "\n\n".join(results)
    
    async def get_memory_summary(self) -> str:
        """Get a summary of available memory.
        
        Returns:
            Summary with file counts and sizes
        """
        logger.info("[TOOL] get_memory_summary")
        
        summary = []
        
        # Short-term summary
        if self.short_term_dir.exists():
            files = list(self.short_term_dir.glob("*.md"))
            total_size = sum(f.stat().st_size for f in files)
            summary.append(f"**Short-Term Memory**: {len(files)} daily logs ({total_size/1024:.1f} KB)")
            if files:
                oldest = min(files, key=lambda f: f.stem)
                newest = max(files, key=lambda f: f.stem)
                summary.append(f"  - Date range: {oldest.stem} to {newest.stem}")
        
        # Long-term summary
        facts = self._facts_store.list_facts()
        total_size = self._facts_store.storage_size_bytes()
        summary.append(f"\n**Long-Term Memory**: {len(facts)} facts ({total_size/1024:.1f} KB)")
        if facts:
            categories = self._facts_store.list_categories()
            summary.append(f"  - Categories: {', '.join(c.replace('_', ' ').title() for c in categories)}")
        
        if not summary:
            return "No memory files found"
        
        return "\n".join(summary)
    
    async def search_recent_mentions(self, topic: str, days: int = 7) -> str:
        """Search for recent mentions of a topic in short-term memory.
        
        Args:
            topic: Topic to search for
            days: Number of recent days to search
            
        Returns:
            Recent mentions with dates
        """
        logger.info(f"[TOOL] search_recent_mentions: '{topic}' in last {days} days")
        
        if not self.short_term_dir.exists():
            return "No short-term memory found"
        
        # Get recent files
        files = sorted(self.short_term_dir.glob("*.md"), reverse=True)[:days]
        
        results = []
        for file_path in files:
            try:
                async with aiofiles.open(file_path, 'r') as f:
                    content = await f.read()
                    
                    # Search for topic (case-insensitive)
                    if topic.lower() in content.lower():
                        # Extract relevant sections
                        lines = content.split('\n')
                        mentions = []
                        
                        for i, line in enumerate(lines):
                            if topic.lower() in line.lower():
                                # Get context around the mention
                                start = max(0, i - 1)
                                end = min(len(lines), i + 2)
                                context = '\n'.join(lines[start:end])
                                mentions.append(context)
                        
                        if mentions:
                            results.append(f"### {file_path.stem}\n" + "\n\n---\n\n".join(mentions[:3]))  # Limit to 3 per day
            except Exception as e:
                logger.error(f"Error reading {file_path}: {e}")
        
        if not results:
            return f"No recent mentions of '{topic}' found in the last {days} days"
        
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
        
        # Map user-friendly names to file names
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
        file_name = category_map.get(category_clean, 'important_facts')

        try:
            from src.core.memory import MemoryManager

            memory_manager = MemoryManager(self.user_id)
            await memory_manager.add_long_term_memory(file_name, content)

            logger.info(f"Successfully saved to {file_name}.md")
            return f"✅ Successfully saved information to long-term memory ({file_name})"

        except Exception as e:
            error_msg = f"Error saving to long-term memory: {e}"
            logger.error(error_msg)
            return f"❌ {error_msg}"

    async def forget_fact(self, search_term: str, category: str = None) -> str:
        """Delete a long-term memory fact the user asked to be forgotten.

        Searches by content first (the LLM never knows a fact's id from
        conversation) and auto-deletes when there's exactly one match. When
        there are multiple matches, lists them with ids instead of deleting,
        so a follow-up delete_fact_by_id call can finish the job once the
        LLM has seen which one the user meant.

        Args:
            search_term: Text to search for among stored facts
            category: Optional category to restrict the search to

        Returns:
            Confirmation message, or a disambiguation list
        """
        logger.info(f"[TOOL] forget_fact: searching for '{search_term}'" + (f" in {category}" if category else ""))

        matches = self._facts_store.search_facts(search_term, category=category)
        if not matches:
            return f"No matching long-term memory found for '{search_term}'."

        if len(matches) == 1:
            deleted = self._facts_store.delete_fact(matches[0]["id"])
            return f"✅ Forgot: \"{deleted['content']}\" (category: {deleted['category']})"

        lines = [f"Found {len(matches)} matching facts - which one? Call delete_fact_by_id with the id:"]
        for f in matches:
            lines.append(f"- id={f['id']} [{f['category']}] {f['content']}")
        return "\n".join(lines)

    async def delete_fact_by_id(self, fact_id: str) -> str:
        """Delete a specific long-term memory fact by its id, as returned by
        a previous forget_fact call that found multiple candidates.

        Args:
            fact_id: The fact id from a previous forget_fact result

        Returns:
            Confirmation message
        """
        logger.info(f"[TOOL] delete_fact_by_id: {fact_id}")

        deleted = self._facts_store.delete_fact(fact_id)
        if deleted is None:
            return f"No fact found with id '{fact_id}'."
        return f"✅ Forgot: \"{deleted['content']}\" (category: {deleted['category']})"

    async def semantic_search_memory(self, query: str, top_k: int = 5) -> str:
        """Find long-term memory facts semantically related to a query, even
        if they don't share exact keywords - best for vague/conceptual
        recall. Additive to search_memory_grep, not a replacement: only
        covers long-term facts (short-term daily logs aren't embedded), and
        needs a working OPENAI_API_KEY.

        Args:
            query: Natural-language description of what to recall
            top_k: Number of results to return

        Returns:
            Ranked matches, or a message suggesting search_memory_grep instead
        """
        logger.info(f"[TOOL] semantic_search_memory: '{query}' (top_k={top_k})")

        try:
            from src.core.embeddings import get_embedding

            query_embedding = await get_embedding(query)
        except Exception as e:
            logger.error(f"Error embedding query for semantic_search_memory: {e}")
            return f"Semantic search unavailable right now ({e}); try search_memory_grep instead."

        results = self._facts_store.semantic_search(query_embedding, top_k=top_k)
        if not results:
            return f"No semantically relevant long-term memories found for '{query}'."

        lines = [f"- ({score:.2f}) [{f['category']}] {f['content']}" for f, score in results]
        return "\n".join(lines)


def get_tools_description() -> str:
    """Get a description of available memory tools for the system prompt.
    
    Returns:
        Formatted description of tools
    """
    return """
## Available Memory Tools

You can use these tools to search and retrieve information from memory files:

1. **search_memory_grep(search_term, context_lines=2)**
   - Search all memory files for a specific term using grep
   - Returns matches with surrounding context
   - Example: search_memory_grep("pizza", 3)

2. **list_memory_files(memory_type="all")**
   - List all available memory files
   - memory_type: "short_term", "long_term", or "all"
   - Shows file names and sizes

3. **read_memory_file(filename, memory_type="short_term")**
   - Read the complete content of a specific memory file
   - Example: read_memory_file("2026-01-30.md", "short_term")

4. **search_by_date_range(start_date, end_date)**
   - Get all short-term memories between two dates
   - Dates in YYYY-MM-DD format
   - Example: search_by_date_range("2026-01-20", "2026-01-25")

5. **search_pattern(regex_pattern, memory_type="all")**
   - Search using regular expressions for complex patterns
   - Example: search_pattern("\\b(phone|call|contact)\\b", "all")

6. **get_memory_summary()**
   - Get an overview of available memory files and categories
   - Shows file counts, sizes, and date ranges

7. **search_recent_mentions(topic, days=7)**
   - Find recent mentions of a topic in the last N days
   - Returns relevant excerpts with dates
   - Example: search_recent_mentions("project", 14)

To use a tool, format your action like:
ACTION: use tool search_memory_grep with search_term="keyword"
"""
