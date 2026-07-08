"""Memory management system using daily markdown files."""
import asyncio
import json
import aiofiles
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from src.core import config
from src.core.llm import get_llm_provider, with_retries
from src.core.logging_config import get_memory_logger
from src.core.wiki_store import WikiStore, _slugify

# Get memory logger
memory_logger = get_memory_logger()

# Max messages kept in the in-memory sliding window (used for LLM context)
CONVERSATION_WINDOW = 10
# Max messages per history page when viewing /history
HISTORY_PAGE_SIZE = 10
# Max seconds between messages before we consider it a new session
SESSION_GAP_SECONDS = 3600  # 1 hour
# Max sessions shown in /continue
MAX_SESSIONS_SHOWN = 10


def _is_suspicious_shrink(old_body: str, new_body: str) -> bool:
    """Cheap defense against an LLM silently dropping content on a
    full-body wiki-page rewrite: true if the new body is both drastically
    shorter than the old one AND missing most of its distinct lines."""
    old_lines = {line.strip() for line in old_body.split("\n") if line.strip()}
    if not old_lines:
        return False
    new_lines = {line.strip() for line in new_body.split("\n") if line.strip()}
    retained = len(old_lines & new_lines)
    return retained < len(old_lines) * 0.5 and len(new_body) < len(old_body) * 0.5


class ConversationHistoryManager:
    """Persistent conversation history stored as JSON per-user.

    Keeps a full log of every user↔assistant exchange in
    `memory/<user_id>/conversations/history.json` so chats survive
    bot restarts.  Also maintains a sliding in-memory window that is
    passed to the LLM as context.

    Public API
    ----------
    load()          → List[Dict]   – read history from disk
    append(user, assistant)         – save one exchange
    get_messages(window) → List[Dict]  – most recent *window* entries
    get_page(page)   → (messages, total_pages)
    clear()         → None         – erase persisted history
    count()         → int          – total message count
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        history_dir = config.MEMORY_DIR / str(user_id) / "conversations"
        history_dir.mkdir(parents=True, exist_ok=True)
        self._path = history_dir / "history.json"

    # -- I/O -----------------------------------------------------------------

    async def load(self) -> List[Dict]:
        """Load conversation history from disk."""
        if not self._path.exists():
            return []
        try:
            async with aiofiles.open(self._path, "r") as f:
                data = await f.read()
            msgs = json.loads(data)
            memory_logger.info(
                f"Loaded {len(msgs)} history messages for user {self.user_id}"
            )
            return msgs
        except Exception as e:
            memory_logger.error(f"Error loading history for {self.user_id}: {e}")
            return []

    async def save(self, messages: List[Dict]):
        """Overwrite history file with the given messages."""
        try:
            async with aiofiles.open(self._path, "w") as f:
                await f.write(json.dumps(messages, indent=2))
        except Exception as e:
            memory_logger.error(f"Error saving history for {self.user_id}: {e}")

    # -- Mutations -----------------------------------------------------------

    async def append(self, user_msg: str, assistant_msg: str, attachment: Optional[Dict] = None):
        """Append one user↔assistant exchange to persisted history.

        `attachment` (if given) is stored on the user message only - metadata
        about a chat-attached image/video (see chatty_web_server.py's
        websocket_chat), so the frontend can re-render the thumbnail after a
        reload. Not used for LLM context (get_messages/get_session for the
        agent's own preload strip it away naturally since callers that need
        the plain shape just read "role"/"content").
        """
        history = await self.load()
        user_entry = {"role": "user", "content": user_msg, "ts": datetime.now().isoformat()}
        if attachment:
            user_entry["attachment"] = attachment
        history.append(user_entry)
        history.append({"role": "assistant", "content": assistant_msg, "ts": datetime.now().isoformat()})
        await self.save(history)

    async def replace_last_assistant(self, new_text: str):
        """Replace the last assistant message's content (used by regenerate)."""
        history = await self.load()
        if history and history[-1]["role"] == "assistant":
            history[-1]["content"] = new_text
            history[-1]["ts"] = datetime.now().isoformat()
        else:
            history.append({"role": "assistant", "content": new_text, "ts": datetime.now().isoformat()})
        await self.save(history)

    async def replace_last_pair(self, new_user: str, new_assistant: str):
        """Replace the last user+assistant exchange (used by edit-and-resend)."""
        history = await self.load()
        if history and history[-1]["role"] == "assistant":
            history.pop()
        if history and history[-1]["role"] == "user":
            history.pop()
        history.append({"role": "user", "content": new_user, "ts": datetime.now().isoformat()})
        history.append({"role": "assistant", "content": new_assistant, "ts": datetime.now().isoformat()})
        await self.save(history)

    # -- Queries -------------------------------------------------------------

    async def get_messages(self, window: int = CONVERSATION_WINDOW) -> List[Dict]:
        """Return the most recent *window* messages (stripped of ``ts``)."""
        history = await self.load()
        tail = history[-window:] if window else history
        return [{"role": m["role"], "content": m["content"]} for m in tail]

    async def get_page(self, page: int = 0) -> tuple:
        """Return a page of messages for display.

        Returns (messages_with_timestamps, total_pages, total_count).
        """
        history = await self.load()
        total = len(history)
        total_pages = max(1, (total + HISTORY_PAGE_SIZE - 1) // HISTORY_PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        start = page * HISTORY_PAGE_SIZE
        end = start + HISTORY_PAGE_SIZE
        return history[start:end], total_pages, total

    async def clear(self):
        """Delete persisted history."""
        if self._path.exists():
            self._path.unlink()
        memory_logger.info(f"Cleared conversation history for user {self.user_id}")

    async def count(self) -> int:
        """Total number of stored messages."""
        history = await self.load()
        return len(history)

    # -- Sessions ------------------------------------------------------------

    def _group_into_sessions(self, history: List[Dict]) -> List[List[Dict]]:
        """Group a flat message list into sessions based on time gaps.

        Groups consecutive messages into sessions when the gap between them
        is less than SESSION_GAP_SECONDS. Returns groups in chronological
        order (oldest session first). The returned lists reference the same
        dict objects as `history`, not copies.
        """
        if not history:
            return []

        sessions: List[List[Dict]] = []
        current_session: List[Dict] = [history[0]]

        for i in range(1, len(history)):
            prev_ts = history[i - 1].get("ts", "")
            curr_ts = history[i].get("ts", "")
            try:
                prev_dt = datetime.fromisoformat(prev_ts)
                curr_dt = datetime.fromisoformat(curr_ts)
                gap = (curr_dt - prev_dt).total_seconds()
            except Exception:
                gap = 0

            if gap > SESSION_GAP_SECONDS:
                sessions.append(current_session)
                current_session = []
            current_session.append(history[i])

        if current_session:
            sessions.append(current_session)

        return sessions

    async def get_sessions(self) -> List[Dict]:
        """Detect conversation sessions based on time gaps.

        Returns a list of session dicts sorted newest-first:

            [{
                "id": int,           # 0-based index, NOT stable across calls
                                     # (shifts whenever a new session appears)
                "messages": List[Dict],  # full messages with ts
                "first_ts": str,      # ISO timestamp of first message (stable key)
                "last_ts": str,       # ISO timestamp of last message
                "summary": str,       # first user message (truncated)
                "title": Optional[str],  # user-assigned custom title, if any
            }, ...]
        """
        history = await self.load()
        if not history:
            return []

        sessions = self._group_into_sessions(history)
        titles = await self._load_titles()

        # Build session summary, newest first
        result: List[Dict] = []
        for idx, sess_msgs in enumerate(reversed(sessions)):
            first_user_msg = next(
                (m["content"] for m in sess_msgs if m["role"] == "user"),
                "",
            )
            first_ts = sess_msgs[0].get("ts", "")
            result.append({
                "id": idx,
                "messages": sess_msgs,
                "first_ts": first_ts,
                "last_ts": sess_msgs[-1].get("ts", ""),
                "message_count": len(sess_msgs),
                "summary": (first_user_msg[:100] + "...") if len(first_user_msg) > 100 else first_user_msg,
                "title": titles.get(first_ts),
            })
        return result

    async def get_session(self, session_id: int) -> List[Dict]:
        """Return messages for a specific session (stripped of ts, attachment kept if present)."""
        sessions = await self.get_sessions()
        if 0 <= session_id < len(sessions):
            sess = sessions[session_id]
            out = []
            for m in sess["messages"]:
                entry = {"role": m["role"], "content": m["content"]}
                if m.get("attachment"):
                    entry["attachment"] = m["attachment"]
                out.append(entry)
            return out
        return []

    async def delete_session(self, session_id: int) -> bool:
        """Delete a session by its (positionally-derived) id. Returns True if found."""
        history = await self.load()
        groups = self._group_into_sessions(history)
        reversed_groups = list(reversed(groups))
        if not (0 <= session_id < len(reversed_groups)):
            return False

        target = reversed_groups[session_id]
        target_ids = {id(m) for m in target}
        remaining = [m for m in history if id(m) not in target_ids]
        await self.save(remaining)

        first_ts = target[0].get("ts", "") if target else ""
        if first_ts:
            titles = await self._load_titles()
            if first_ts in titles:
                del titles[first_ts]
                await self._save_titles(titles)

        return True

    # -- Session titles --------------------------------------------------------

    def _titles_path(self) -> Path:
        return self._path.parent / "session_titles.json"

    async def _load_titles(self) -> Dict[str, str]:
        path = self._titles_path()
        if not path.exists():
            return {}
        try:
            async with aiofiles.open(path, "r") as f:
                data = await f.read()
            return json.loads(data)
        except Exception as e:
            memory_logger.error(f"Error loading session titles for {self.user_id}: {e}")
            return {}

    async def _save_titles(self, titles: Dict[str, str]):
        try:
            async with aiofiles.open(self._titles_path(), "w") as f:
                await f.write(json.dumps(titles, indent=2))
        except Exception as e:
            memory_logger.error(f"Error saving session titles for {self.user_id}: {e}")

    async def get_session_title(self, first_ts: str) -> Optional[str]:
        titles = await self._load_titles()
        return titles.get(first_ts)

    async def set_session_title(self, first_ts: str, title: str):
        titles = await self._load_titles()
        titles[first_ts] = title
        await self._save_titles(titles)


class MemoryManager:
    """Manages conversation memory stored in daily markdown files."""
    
    def __init__(self, user_id: str):
        """Initialize memory manager for a specific user.
        
        Args:
            user_id: Unique identifier for the user
        """
        self.user_id = user_id
        self.user_memory_dir = config.MEMORY_DIR / str(user_id)
        self.short_term_dir = self.user_memory_dir / "short_term"
        self.long_term_dir = self.user_memory_dir / "long_term"
        self.uploads_dir = self.user_memory_dir / "uploads"

        # Create directories
        self.user_memory_dir.mkdir(parents=True, exist_ok=True)
        self.short_term_dir.mkdir(parents=True, exist_ok=True)
        self.long_term_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)

        self._wiki_store = WikiStore(user_id, self.long_term_dir)
        self._recent_memory_cache: Dict[Path, Tuple[int, str]] = {}  # path -> (mtime_ns, content)

        memory_logger.info(f"Initialized MemoryManager for user {user_id}")
    
    def _get_today_file(self) -> Path:
        """Get the path to today's short-term memory file."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.short_term_dir / f"{today}.md"
    
    def _get_recent_files(self, days: int = 7) -> List[Path]:
        """Get list of recent short-term memory files.
        
        Args:
            days: Number of recent days to retrieve
            
        Returns:
            List of file paths sorted by date (newest first)
        """
        files = sorted(
            self.short_term_dir.glob("*.md"),
            key=lambda p: p.stem,
            reverse=True
        )
        return files[:days]
    
    async def add_interaction(self, user_message: str, assistant_message: str):
        """Add a conversation interaction to today's memory.
        
        Args:
            user_message: Message from the user
            assistant_message: Response from the assistant
        """
        today_file = self._get_today_file()
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        memory_logger.debug(f"Adding interaction for user {self.user_id} to {today_file.name}")
        
        # Create file with header if it doesn't exist
        if not today_file.exists():
            async with aiofiles.open(today_file, 'w') as f:
                date_str = datetime.now().strftime("%Y-%m-%d")
                await f.write(f"# Memory Log - {date_str}\n\n")
            memory_logger.info(f"Created new memory file: {today_file.name} for user {self.user_id}")
        
        # Append interaction
        async with aiofiles.open(today_file, 'a') as f:
            await f.write(f"## [{timestamp}]\n\n")
            await f.write(f"**User**: {user_message}\n\n")
            await f.write(f"**Assistant**: {assistant_message}\n\n")
            await f.write("---\n\n")
        
        memory_logger.info(f"Saved interaction for user {self.user_id}: user_msg_len={len(user_message)}, assistant_msg_len={len(assistant_message)}")
    
    async def get_recent_memory(self, days: int = 7) -> str:
        """Retrieve recent memory as a formatted string.
        
        Args:
            days: Number of recent days to retrieve
            
        Returns:
            Formatted memory string
        """
        recent_files = self._get_recent_files(days)
        
        memory_logger.debug(f"Retrieving recent memory for user {self.user_id}: {len(recent_files)} files from last {days} days")
        
        if not recent_files:
            memory_logger.info(f"No recent memory files found for user {self.user_id}")
            return "No previous conversations found."
        
        memory_parts = []
        for file_path in recent_files:
            try:
                mtime_ns = file_path.stat().st_mtime_ns
                cached = self._recent_memory_cache.get(file_path)
                if cached is not None and cached[0] == mtime_ns:
                    content = cached[1]
                else:
                    async with aiofiles.open(file_path, 'r') as f:
                        content = await f.read()
                    self._recent_memory_cache[file_path] = (mtime_ns, content)
                memory_parts.append(content)
                memory_logger.debug(f"Loaded memory file {file_path.name}: {len(content)} chars")
            except Exception as e:
                memory_logger.error(f"Error reading memory file {file_path}: {e}")
        
        total_chars = sum(len(part) for part in memory_parts)
        memory_logger.info(f"Retrieved recent memory for user {self.user_id}: {len(memory_parts)} files, {total_chars} total chars")
        return "\n\n".join(memory_parts) if memory_parts else "No previous conversations found."
    
    async def add_note(self, note: str):
        """Add a standalone note to today's memory.
        
        Args:
            note: Note text to add
        """
        today = datetime.now().strftime("%Y-%m-%d")
        today_file = self.short_term_dir / f"{today}.md"
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        memory_logger.debug(f"Adding note for user {self.user_id} to {today_file.name}")
        
        # Create file with header if it doesn't exist
        if not today_file.exists():
            async with aiofiles.open(today_file, 'w') as f:
                date_str = datetime.now().strftime("%Y-%m-%d")
                await f.write(f"# Memory Log - {date_str}\n\n")
            memory_logger.info(f"Created new memory file: {today_file.name} for user {self.user_id}")
        
        # Append note
        async with aiofiles.open(today_file, 'a') as f:
            await f.write(f"### Note [{timestamp}]\n\n")
            await f.write(f"{note}\n\n")
            await f.write("---\n\n")
        
        memory_logger.info(f"Added note for user {self.user_id}: {note[:100]}...")
    
    async def get_summary(self) -> Dict[str, int]:
        """Get summary statistics about user's memory.

        Returns:
            Dictionary with memory statistics
        """
        short_term_files = list(self.short_term_dir.glob("*.md"))
        total_size = sum(f.stat().st_size for f in short_term_files)
        pages = self._wiki_store.list_pages()
        total_size += self._wiki_store.storage_size_bytes()

        return {
            "total_days": len(short_term_files),
            "long_term_entries": len(pages),
            "total_size_bytes": total_size,
            "oldest_date": min(f.stem for f in short_term_files) if short_term_files else None,
            "newest_date": max(f.stem for f in short_term_files) if short_term_files else None,
        }

    async def get_long_term_memory(self, max_chars: Optional[int] = None) -> str:
        """Retrieve all long-term memory (the wiki) as a formatted string.

        Args:
            max_chars: If given, cap total output at this many characters,
                split evenly across pages so no single page (by virtue of
                sort order or unbounded growth) starves out the others. If
                None, returns full content (e.g. for the heartbeat's
                watch-suggestion mining, which needs everything).

        Returns:
            Formatted long-term memory string
        """
        pages = await asyncio.to_thread(self._wiki_store.list_pages)

        if not pages:
            return "No long-term memories yet."

        per_page_budget = max_chars // len(pages) if max_chars is not None else None

        memory_parts = []
        for page in pages:
            block = f"# {page['title']}\n\n{page['body']}"
            if per_page_budget is not None:
                block = block[:per_page_budget]
            memory_parts.append(block)

        return "\n\n".join(memory_parts) if memory_parts else "No long-term memories yet."

    async def add_long_term_memory(self, title: str, content: str):
        """Add a long-term memory entry: appends a bullet to the wiki
        concept page named by `title` (creating it if it doesn't exist
        yet), synchronously and without an LLM call - see
        MemoryRouter.remember()'s docstring for why this stays a cheap
        heuristic append rather than the heartbeat's richer page-editing
        ingest.

        Args:
            title: Category/page-slug hint (e.g., 'preferences', 'important_facts')
            content: Content to store
        """
        slug = _slugify(title) if title.strip() else "important-facts"
        page_title = title.replace("_", " ").replace("-", " ").title() or "Important Facts"
        self._wiki_store.append_section(
            type_="concept", slug=slug, content=f"- {content}", title_hint=page_title,
        )
    
    async def get_short_term_files_for_consolidation(self, days_old: int = 7) -> List[Path]:
        """Get short-term memory files older than specified days for consolidation.
        
        Args:
            days_old: Get files older than this many days
            
        Returns:
            List of file paths that should be consolidated
        """
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")
        
        all_files = sorted(
            self.short_term_dir.glob("*.md"),
            key=lambda p: p.stem
        )
        
        # Return files older than cutoff
        return [f for f in all_files if f.stem < cutoff_str]
    
    async def archive_short_term_memory(self, file_path: Path):
        """Archive a short-term memory file after consolidation.
        
        Args:
            file_path: Path to the short-term memory file to archive
        """
        # Move to archive folder within short_term
        archive_dir = self.short_term_dir / "archived"
        archive_dir.mkdir(exist_ok=True)
        
        archive_path = archive_dir / file_path.name
        
        # Move the file
        try:
            file_path.rename(archive_path)
        except Exception as e:
            print(f"Error archiving {file_path}: {e}")
    
    async def consolidate_memories(self, agent) -> str:
        """Consolidate old short-term memories into long-term insights.
        
        This method analyzes older short-term memories and updates/creates
        the long-term wiki pages they belong to (edit, not just append -
        see _ingest_content()).

        Args:
            agent: StagedReACTAgent instance whose LLM is used for the ingest

        Returns:
            Summary of consolidation results
        """

        # Get files older than 7 days
        files_to_consolidate = await self.get_short_term_files_for_consolidation(days_old=7)

        if not files_to_consolidate:
            return "No short-term memories ready for consolidation."

        # Read all files to consolidate
        all_content = []
        for file_path in files_to_consolidate:
            try:
                async with aiofiles.open(file_path, 'r') as f:
                    content = await f.read()
                    all_content.append(f"## From {file_path.stem}\n{content}")
            except Exception as e:
                print(f"Error reading file {file_path}: {e}")

        if not all_content:
            return "No content to consolidate."

        combined_content = "\n\n".join(all_content)

        try:
            ingest_result = await self._ingest_content(combined_content, agent.llm.complete)
        except Exception as e:
            print(f"Error during consolidation: {e}")
            return f"Error consolidating memories: {e}"

        if ingest_result.startswith("Error"):
            return ingest_result

        # Archive the processed files (even if nothing was memory-worthy -
        # they've been considered, no need to reprocess them next cycle)
        for file_path in files_to_consolidate:
            await self.archive_short_term_memory(file_path)

        return f"Successfully consolidated {len(files_to_consolidate)} day(s) of memories into long-term storage."

    @staticmethod
    def _build_contradiction_resolution_prompt(
        page_a: Dict, page_b: Dict, description: str, guidance: str,
    ) -> str:
        """Build the one-shot task prompt for resolve_contradiction(), kept
        as a pure function so its wording can be unit-tested without
        constructing a real agent."""
        a_label = f"{page_a.get('title') or page_a.get('slug', '?')} ({page_a.get('type', '?')}/{page_a.get('slug', '?')})"
        b_label = f"{page_b.get('title') or page_b.get('slug', '?')} ({page_b.get('type', '?')}/{page_b.get('slug', '?')})"
        return (
            "A lint pass over your long-term memory wiki flagged a contradiction "
            "between two pages:\n\n"
            f"- {a_label}\n"
            f"- {b_label}\n\n"
            f"Contradiction: {description}\n\n"
            f'The user has clarified how to resolve it: "{guidance}"\n\n'
            "Use your memory tools to correct the wiki so it reflects the user's "
            "clarification and both pages stay internally consistent afterward. "
            "Briefly summarize what you changed."
        )

    async def resolve_contradiction(
        self, page_a: Dict, page_b: Dict, description: str, guidance: str, agent,
    ) -> str:
        """Ask `agent` (a live StagedReACTAgent, with full recall/remember/
        forget/browse_wiki tool access) to fix a lint-flagged contradiction
        between two wiki pages, incorporating the user's clarification.

        Unlike consolidate_memories()/consolidate_text()'s narrow ingest
        pipeline (one triage call + one edit call, LLM-only), this runs the
        agent's *full* ReACT tool loop - the fix may need to read/edit more
        than the two flagged pages (e.g. a third page repeating the wrong
        claim), which the ingest pipeline's fixed two-call shape can't do
        but the agent's tool loop can, by calling recall/remember/forget as
        many times as it judges necessary.

        Args:
            page_a, page_b: {"type", "slug", "title"} refs, as returned by
                WikiStore.read_health()'s contradictions list
            description: the lint pass's description of the contradiction
            guidance: free-text clarification from the user
            agent: StagedReACTAgent instance whose tool loop performs the fix

        Returns:
            The agent's final response describing what it did
        """
        prompt = self._build_contradiction_resolution_prompt(page_a, page_b, description, guidance)
        return await agent.think(prompt, [])

    # Per-page char cap when building a full-wiki prompt (propose/apply
    # reorganization) - this system's local LLM backend has been observed
    # to return an empty/unparseable response for very large single-shot
    # prompts (the same failure lint_wiki()'s full-body contradiction scan
    # can hit), so bound the payload rather than sending every page in full.
    REORG_BODY_CHARS_PER_PAGE = 1500

    async def _complete_json_retrying_empty(
        self, complete_fn, prompt: str, *, temperature: float, retries: int = 1,
    ) -> Optional[Dict]:
        """Call complete_fn(prompt), parsing the response as JSON, retrying
        up to `retries` more times if the response is empty/unparseable.
        This is a *logical* retry on top of with_retries()'s transport-level
        one - with_retries only retries on exceptions (rate limits,
        connection errors), not on a 200 response whose content is empty or
        not valid JSON, which is the failure mode actually observed here."""
        last_error: Optional[Exception] = None
        for attempt in range(retries + 1):
            try:
                response = await with_retries(
                    lambda: complete_fn(
                        [{"role": "user", "content": prompt}],
                        response_format="json", temperature=temperature,
                    ),
                    logger=memory_logger,
                )
                return json.loads(response.content)
            except Exception as e:
                last_error = e
                memory_logger.error(
                    f"Empty/invalid JSON from LLM for {self.user_id} "
                    f"(attempt {attempt + 1}/{retries + 1}): {e}"
                )
        if last_error:
            raise last_error
        return None

    def _truncated_page_block(self, page: Dict, header: str) -> str:
        body = page["body"]
        if len(body) > self.REORG_BODY_CHARS_PER_PAGE:
            body = body[: self.REORG_BODY_CHARS_PER_PAGE].rstrip() + "\n…(truncated)"
        return f"{header}\n{body}"

    async def propose_reorganization(self) -> Dict:
        """One read-only LLM call: given the full current wiki, propose a
        more granular target page structure - a dedicated entity page per
        distinct named person/place instead of lumped catch-all pages
        (e.g. splitting a single 'Relationships' page into one page per
        family member). Writes nothing; the plan this returns is meant to
        be reviewed (and optionally trimmed) by the user before being
        passed to apply_reorganization().

        Returns:
            {"target_pages": [{"type", "slug", "title", "summary",
            "source_pages": ["type/slug", ...], "already_exists": bool}, ...]}
            (plus an "error" key if the LLM call itself failed)
        """
        wiki_store = self._wiki_store
        pages = wiki_store.list_pages()
        if not pages:
            return {"target_pages": []}

        bodies_text = "\n\n".join(
            self._truncated_page_block(p, f"## {p['type']}/{p['slug']}: {p['title']}") for p in pages
        )
        existing_keys = {(p["type"], p["slug"]) for p in pages}

        prompt = f"""You are redesigning the structure of a personal long-term-memory wiki to be more like a real wiki - one dedicated page per distinct subject, not lumped catch-all pages.

Current wiki pages (type/slug: title, then body):
{bodies_text}

Propose a target page structure: a dedicated ENTITY page for each distinct named person (the primary user, their spouse, each named child individually, other named individuals mentioned repeatedly) and each distinct named place, plus CONCEPT pages for themes/goals/preferences/topics that aren't tied to one person or place. Do not propose splitting things that are already well-separated - only propose splitting lumped/mixed pages and filling real gaps.

For each target page, list which existing page(s) its content should be drawn from. Respond with ONLY a JSON object of this exact shape:
{{"target_pages": [{{"type": "entity"|"concept", "slug": "...", "title": "...", "summary": "one-line summary", "source_pages": ["type/slug", ...]}}, ...]}}
Use lowercase hyphenated slugs. If the wiki is already well-structured, respond {{"target_pages": []}}.
"""

        try:
            llm = get_llm_provider()
            data = await self._complete_json_retrying_empty(llm.complete, prompt, temperature=0.2)
        except Exception as e:
            memory_logger.error(f"Error proposing wiki reorganization for {self.user_id}: {e}")
            return {"target_pages": [], "error": str(e)}

        target_pages = []
        for t in data.get("target_pages") or []:
            type_ = t.get("type") if t.get("type") in ("entity", "concept") else "concept"
            slug = _slugify(t.get("slug") or t.get("title") or "")
            source_pages = [s for s in (t.get("source_pages") or []) if isinstance(s, str)]
            target_pages.append({
                "type": type_, "slug": slug, "title": t.get("title") or slug.replace("-", " ").title(),
                "summary": t.get("summary") or "", "source_pages": source_pages,
                "already_exists": (type_, slug) in existing_keys,
            })
        return {"target_pages": target_pages}

    async def apply_reorganization(self, target_pages: List[Dict]) -> str:
        """Execute a (possibly user-trimmed) plan from propose_reorganization():
        draft each target page's body from its source pages' content via one
        batched LLM call, then write it. Source pages are never deleted -
        this only ever adds/overwrites the target pages, so the user can
        review the result and delete stale lumped pages themselves once
        satisfied nothing was lost (same "don't act destructively without
        review" posture as lint_wiki()'s flag-only contradiction/gap
        checks)."""
        if not target_pages:
            return "Nothing to reorganize."

        wiki_store = self._wiki_store

        seen_sources = set()
        source_context_parts = []
        for t in target_pages:
            for ref in t.get("source_pages") or []:
                if ref in seen_sources:
                    continue
                seen_sources.add(ref)
                type_dir, _, slug = str(ref).partition("/")
                type_ = "entity" if type_dir in ("entity", "entities") else "concept"
                page = wiki_store.get_page(type_, slug)
                if page:
                    source_context_parts.append(
                        self._truncated_page_block(page, f"## Source page {type_}/{slug}: {page['title']}")
                    )
        source_context = "\n\n".join(source_context_parts) or "(none)"

        targets_context = "\n".join(
            f"- {t['type']}/{t['slug']} \"{t['title']}\" - draw from: "
            f"{', '.join(t.get('source_pages') or []) or '(no sources - draft from general context only)'}"
            for t in target_pages
        )

        prompt = f"""You are drafting new, more granular wiki pages as part of a reorganization.

Source page content to draw from:
{source_context}

Target pages to draft (each should pull only the content relevant to its own subject from the source pages listed for it):
{targets_context}

For each target page, produce its FULL body - concise bullet points, only the facts relevant to that specific subject. Respond with ONLY a JSON object of this exact shape:
{{"pages": [{{"type": "entity"|"concept", "slug": "...", "title": "...", "summary": "one-line summary", "tags": ["..."], "body": "- bullet\\n- bullet"}}, ...]}}
"""

        try:
            llm = get_llm_provider()
            edit_result = await self._complete_json_retrying_empty(llm.complete, prompt, temperature=0.3)
        except Exception as e:
            memory_logger.error(f"Error applying wiki reorganization for {self.user_id}: {e}")
            return f"Error during reorganization: {e}"

        touched = 0
        for page in edit_result.get("pages") or []:
            type_ = page.get("type") or "concept"
            slug = page.get("slug") or ""
            title = page.get("title") or ""
            summary = page.get("summary") or ""
            tags = page.get("tags") or []
            body = page.get("body") or ""
            if not slug or not body.strip():
                continue

            existing = wiki_store.get_page(type_, slug)
            if existing and _is_suspicious_shrink(existing["body"], body):
                memory_logger.error(
                    f"Rejected suspicious reorganization rewrite of {type_}/{slug} for {self.user_id} "
                    f"(new body much shorter/missing content vs old) - keeping existing page"
                )
                continue

            wiki_store.write_page(
                type_=type_, slug=slug, title=title or slug.replace("-", " ").title(),
                summary=summary, body=body, tags=tags, rebuild_index=False,
            )
            wiki_store.append_log("reorganize", f"{title or slug} — created/updated via reorganization")
            touched += 1

        if touched:
            wiki_store.rebuild_index()

        if not touched:
            return "No pages were created."
        return (
            f"Reorganized into {touched} page(s). Original source pages were left untouched - "
            "review them and delete any that are now redundant once you've confirmed nothing was lost."
        )

    async def consolidate_text(self, text: str) -> str:
        """Extract and store long-term-memory-worthy content from arbitrary
        text (e.g. a mined transcription) via the same wiki-editing ingest
        as consolidate_memories().

        Unlike consolidate_memories(), this takes raw text directly instead
        of reading short-term memory files, and calls the LLM directly
        rather than going through a live agent instance - so it can run
        without one (e.g. from the heartbeat, for a web/iOS user who may
        not have an active chat session).

        Args:
            text: Raw text to mine for long-term-memory-worthy content.

        Returns:
            Summary string of what was stored.
        """
        try:
            llm = get_llm_provider()
            return await self._ingest_content(text, llm.complete)
        except Exception as e:
            memory_logger.error(f"Error consolidating text for {self.user_id}: {e}")
            return f"Error consolidating text: {e}"

    async def _ingest_content(self, source_content: str, complete_fn) -> str:
        """Shared two-LLM-call wiki ingest, used by both consolidate_memories
        (agent.llm.complete) and consolidate_text (get_llm_provider().complete)
        - complete_fn is an async callable matching LLMProvider.complete's
        signature (messages, *, response_format, temperature) -> LLMResponse.

        Call 1 (triage): given the wiki's index and the new content, decide
        which existing pages to update and which new pages to create.
        Call 2 (edit): given the new content plus the *current full body*
        of only the pages triage selected (not the whole wiki - keeps token
        cost roughly constant regardless of total wiki size), produce full
        rewritten bodies - this is the wiki's "edit, don't just append"
        behavior, unlike the old flat-fact-per-entry model.

        Returns a human-readable summary string.
        """
        wiki_store = self._wiki_store
        index_text = wiki_store.read_index()

        triage_prompt = f"""You are triaging new content to decide how a personal long-term-memory wiki should be updated.

Wiki index (existing pages):
{index_text}

New content to incorporate:
{source_content}

Decide which EXISTING pages (if any) this content should update, and which NEW pages (if any) should be created. Respond with ONLY a JSON object of this exact shape:
{{"update_pages": ["concepts/budgeting", ...], "create_pages": [{{"type": "entity", "slug": "acme-corp", "title": "Acme Corp"}}, ...]}}
Use lowercase hyphenated slugs. "entity" pages are for people/organizations/places/products; "concept" pages are for themes, preferences, goals, recurring topics. Prefer one dedicated entity page per distinct named person or place over folding them into a general/catch-all page (e.g. a new fact about a specific named child belongs on that child's own page, not a shared "family" or "relationships" page) - this keeps the wiki a real encyclopedia of individually addressable subjects rather than a few large lumped ones. If nothing in the content is memory-worthy, respond {{"update_pages": [], "create_pages": []}}.
"""

        try:
            triage_response = await with_retries(
                lambda: complete_fn(
                    [{"role": "user", "content": triage_prompt}],
                    response_format="json", temperature=0.2,
                ),
                logger=memory_logger,
            )
            triage = json.loads(triage_response.content)
        except Exception as e:
            memory_logger.error(f"Error in wiki ingest triage for {self.user_id}: {e}")
            return f"Error during consolidation: {e}"

        update_refs = triage.get("update_pages") or []
        create_specs = triage.get("create_pages") or []

        if not update_refs and not create_specs:
            return "No long-term-memory-worthy content found."

        existing_pages: Dict[Tuple[str, str], Dict] = {}
        for ref in update_refs:
            type_dir, _, slug = str(ref).partition("/")
            type_ = "entity" if type_dir == "entities" else "concept"
            page = wiki_store.get_page(type_, slug)
            if page:
                existing_pages[(type_, slug)] = page

        if not existing_pages and not create_specs:
            return "No long-term-memory-worthy content found."

        pages_context = "\n\n".join(
            f"## Existing page {t}/{s}\n{p['body']}" for (t, s), p in existing_pages.items()
        ) or "(none)"
        create_context = "\n".join(
            f"- NEW {spec.get('type', 'concept')}/{spec.get('slug', '')}: {spec.get('title', '')}"
            for spec in create_specs
        ) or "(none)"

        edit_prompt = f"""You are editing a personal long-term-memory wiki based on new content.

New content:
{source_content}

Existing pages selected for update (full current body):
{pages_context}

Pages to create:
{create_context}

For each page listed above (both existing and new), produce the FULL new body - rewrite/merge the existing content with the new information rather than just appending, keeping it as concise bullet points. Respond with ONLY a JSON object of this exact shape:
{{"pages": [{{"type": "entity"|"concept", "slug": "...", "title": "...", "summary": "one-line summary", "tags": ["..."], "body": "- bullet\\n- bullet"}}, ...]}}
"""

        try:
            edit_response = await with_retries(
                lambda: complete_fn(
                    [{"role": "user", "content": edit_prompt}],
                    response_format="json", temperature=0.3,
                ),
                logger=memory_logger,
            )
            edit_result = json.loads(edit_response.content)
        except Exception as e:
            memory_logger.error(f"Error in wiki ingest edit for {self.user_id}: {e}")
            return f"Error during consolidation: {e}"

        touched = self._apply_ingest_result(edit_result.get("pages") or [], existing_pages)
        if not touched:
            return "No long-term-memory-worthy content found."

        return f"Successfully consolidated content into {touched} wiki page(s)."

    def _apply_ingest_result(self, pages: List[Dict], existing_pages: Dict[Tuple[str, str], Dict]) -> int:
        """Write each page from an ingest edit-call's output, guarding
        against a rewrite that silently drops most of a page's prior
        content (a cheap defense against the LLM discarding information on
        a full-body rewrite - reject and keep the existing page in that
        case, logging it for manual review)."""
        touched = 0
        for page in pages:
            type_ = page.get("type") or "concept"
            slug = page.get("slug") or ""
            title = page.get("title") or ""
            summary = page.get("summary") or ""
            tags = page.get("tags") or []
            body = page.get("body") or ""
            if not slug or not body.strip():
                continue

            old = existing_pages.get((type_, slug))
            if old and _is_suspicious_shrink(old["body"], body):
                memory_logger.error(
                    f"Rejected suspicious ingest rewrite of {type_}/{slug} for {self.user_id} "
                    f"(new body much shorter/missing content vs old) - keeping existing page"
                )
                continue

            self._wiki_store.write_page(
                type_=type_, slug=slug, title=title or slug.replace("-", " ").title(),
                summary=summary, body=body, tags=tags, rebuild_index=False,
            )
            self._wiki_store.append_log(
                "ingest",
                f"{title or slug} — {'updated' if old else 'created'} via consolidation",
            )
            touched += 1

        if touched:
            self._wiki_store.rebuild_index()

        return touched

    async def lint_wiki(self) -> str:
        """Periodic wiki health-check pass, replacing the old dedupe_facts().

        Heuristic checks (no LLM, auto-applied): merge near-duplicate pages
        and auto-link bare mentions of other pages' titles into cross-
        references - both are safe, mechanical fixes. Orphan-page detection
        is heuristic too but flag-only (logged, never auto-edited - even a
        marker comment would be an unrequested edit for something this
        judgment-laden). Contradictions and coverage gaps need an LLM call
        and are always flag-only, since auto-resolving "which claim is
        correct" risks silently discarding correct information.

        Returns:
            Summary of what was auto-fixed and what was flagged.
        """
        wiki_store = self._wiki_store

        merged_count = 0
        for keep, remove in wiki_store.find_duplicate_pages(threshold=0.95):
            wiki_store.merge_pages(keep, remove)
            wiki_store.append_log("lint", f"Merged duplicate page '{remove['title']}' into '{keep['title']}'")
            merged_count += 1

        linked_count = wiki_store.fix_missing_cross_references()
        if linked_count:
            wiki_store.append_log("lint", f"Added {linked_count} missing cross-reference(s)")

        orphans = wiki_store.find_orphan_pages()
        for page in orphans:
            wiki_store.append_log("lint", f"Orphan page flagged (no inbound links): {page['title']}")

        contradictions, coverage_gaps = await self._lint_llm_checks()

        total_pages = len(wiki_store.list_pages())
        auto_fixed = merged_count + linked_count
        flagged = len(orphans) + len(contradictions) + len(coverage_gaps)

        wiki_store.write_health({
            "generated_at": datetime.now().isoformat(),
            "total_pages": total_pages,
            "auto_fixed": {"cross_references_added": linked_count, "duplicates_merged": merged_count},
            "orphans": [{"type": p["type"], "slug": p["slug"], "title": p["title"]} for p in orphans],
            "contradictions": contradictions,
            "coverage_gaps": coverage_gaps,
        })

        fixed_parts = []
        if linked_count:
            fixed_parts.append(f"{linked_count} cross-reference(s) added")
        if merged_count:
            fixed_parts.append(f"{merged_count} duplicate page(s) merged")
        flagged_parts = []
        if orphans:
            flagged_parts.append(f"{len(orphans)} orphan page(s)")
        if contradictions:
            flagged_parts.append(f"{len(contradictions)} contradiction(s)")
        if coverage_gaps:
            flagged_parts.append(f"{len(coverage_gaps)} coverage gap(s)")

        fixed_str = f"auto-fixed {auto_fixed} issue(s) ({', '.join(fixed_parts)})" if auto_fixed else "no auto-fixes needed"
        flagged_str = f"flagged {flagged} for review ({', '.join(flagged_parts)})" if flagged else "nothing flagged"

        return f"Lint: {fixed_str}, {flagged_str} across {total_pages} page(s)."

    async def _lint_llm_checks(self) -> Tuple[List[Dict], List[Dict]]:
        """One LLM call: find contradictions between pages and coverage gaps
        (a theme mentioned repeatedly with no dedicated page). Both are
        flag-only - logged to log.md, never auto-applied."""
        wiki_store = self._wiki_store
        pages = wiki_store.list_pages()
        if not pages:
            return [], []

        index_text = wiki_store.read_index()
        bodies_text = "\n\n".join(
            self._truncated_page_block(p, f"## {p['title']} ({p['type']}/{p['slug']})") for p in pages
        )

        prompt = f"""You are reviewing a personal long-term-memory wiki for two kinds of issues.

Wiki index:
{index_text}

Full page contents:
{bodies_text}

1. Contradictions: a claim in one page that is directly contradicted or clearly superseded by a claim in another page.
2. Coverage gaps: a theme or entity mentioned repeatedly across pages but with no dedicated page of its own.

Respond with ONLY a JSON object of this exact shape:
{{"contradictions": [{{"page_a": "type/slug", "page_b": "type/slug", "description": "..."}}, ...], "coverage_gaps": [{{"suggested_title": "...", "suggested_type": "entity"|"concept", "description": "..."}}, ...]}}
If there are none of either, respond with empty lists.
"""

        try:
            llm = get_llm_provider()
            data = await self._complete_json_retrying_empty(llm.complete, prompt, temperature=0.2)
        except Exception as e:
            memory_logger.error(f"Error in wiki lint LLM checks for {self.user_id}: {e}")
            return [], []

        raw_contradictions = data.get("contradictions") or []
        coverage_gaps = data.get("coverage_gaps") or []

        contradictions = []
        for c in raw_contradictions:
            contradictions.append({
                "page_a": self._resolve_ref(c.get("page_a", "")),
                "page_b": self._resolve_ref(c.get("page_b", "")),
                "description": c.get("description", ""),
            })
            wiki_store.append_log(
                "lint",
                f"Contradiction flagged: {c.get('page_a', '?')} vs {c.get('page_b', '?')} — {c.get('description', '')}",
            )
        for g in coverage_gaps:
            wiki_store.append_log(
                "lint",
                f"Coverage gap flagged: '{g.get('suggested_title', '?')}' — {g.get('description', '')}",
            )

        return contradictions, coverage_gaps

    def _resolve_ref(self, ref: str) -> Dict:
        """'entities/acme-corp' or 'entity/acme-corp' -> {type, slug, title}
        (title falls back to slug if the referenced page can't be found -
        the LLM's ref might be slightly off, and this stays link-able
        regardless)."""
        type_dir, _, slug = str(ref).partition("/")
        type_ = "entity" if type_dir in ("entity", "entities") else "concept"
        page = self._wiki_store.get_page(type_, slug)
        return {"type": type_, "slug": slug, "title": page["title"] if page else slug}


