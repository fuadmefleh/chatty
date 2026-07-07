"""Structured per-user long-term memory fact store.

Replaces the old markdown-file-per-category format (`{category}.md` with
appended `## Updated: {timestamp}` blocks) with a single JSON list of facts,
each with a stable UUID id - the old format had no way to address, edit, or
delete a single fact short of hand-editing a markdown file. Follows the same
JSON + file-lock + atomic-write + UUID pattern as
`skills/speakers/speaker_manager.py`'s `SpeakerManager`.
"""
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.core.file_lock import locked
from src.core.logging_config import get_memory_logger

memory_logger = get_memory_logger()

# Intentional display order (the old format's accidental reverse-alphabetical
# file sort put "relationships" first and, once it grew past the char
# budget, silently hid "important_facts" forever - see the prior bug fix).
# Any category outside this list (unexpected, but not prevented) is appended
# alphabetically after these.
CANONICAL_CATEGORY_ORDER = [
    "important_facts",
    "personal_preferences",
    "goals_and_projects",
    "relationships",
    "recurring_topics",
    "key_insights",
]


def _category_sort_key(category: str) -> Tuple[int, str]:
    try:
        return (CANONICAL_CATEGORY_ORDER.index(category), category)
    except ValueError:
        return (len(CANONICAL_CATEGORY_ORDER), category)


def render_category_facts(category: str, facts: List[Dict], max_chars: Optional[int] = None) -> str:
    """Render one category's facts as a markdown-ish block, shared by
    MemoryManager.get_long_term_memory and MemoryTools.read_memory_file's
    long-term branch so both stay in sync."""
    lines = [f"# Long-Term Memory: {category}", ""]
    for fact in facts:
        lines.append(f"- [{fact['id'][:8]}] {fact['content']} (updated: {fact['updated_at']})")
    rendered = "\n".join(lines)
    if max_chars is not None:
        rendered = rendered[:max_chars]
    return rendered


class LongTermFactsStore:
    """Manages a user's long-term memory facts as a JSON list with stable
    UUID ids, enabling per-fact search/update/delete."""

    _UPDATE_MARKER_RE = re.compile(r'\n\n## Updated: ([^\n]+)\n\n')
    _CREATED_RE = re.compile(r'Created: ([^\n]+)\n')
    _HEADER_RE = re.compile(r'^# Long-Term Memory:.*\n')

    def __init__(self, user_id: str, long_term_dir: Path):
        self.user_id = user_id
        self.long_term_dir = Path(long_term_dir)
        self.long_term_dir.mkdir(parents=True, exist_ok=True)
        self._path = self.long_term_dir / "facts.json"
        self._migrate_legacy_markdown_if_needed()

    # -- I/O -------------------------------------------------------------

    def _load(self) -> List[Dict]:
        if not self._path.exists():
            return []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            memory_logger.error(f"Error loading long-term facts for {self.user_id}: {e}")
            return []

    def _save(self, facts: List[Dict]) -> None:
        """Write atomically (temp file + rename), same as SpeakerManager._save,
        so a concurrent reader never observes a partial write."""
        tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(facts, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, self._path)

    # -- CRUD ------------------------------------------------------------

    def add_fact(self, category: str, content: str, embedding: Optional[List[float]] = None) -> Dict:
        with locked(self._path):
            facts = self._load()
            now = datetime.now().isoformat()
            fact = {
                "id": str(uuid.uuid4()),
                "category": category,
                "content": content,
                "created_at": now,
                "updated_at": now,
                "embedding": embedding,
            }
            facts.append(fact)
            self._save(facts)
            return fact

    def list_facts(self, category: Optional[str] = None) -> List[Dict]:
        facts = self._load()
        if category is not None:
            facts = [f for f in facts if f["category"] == category]
        return facts

    def storage_size_bytes(self) -> int:
        """Size of the backing facts.json file, or 0 if it doesn't exist yet."""
        return self._path.stat().st_size if self._path.exists() else 0

    def list_categories(self) -> List[str]:
        """Distinct categories that currently have at least one fact, in
        canonical display order."""
        categories = {f["category"] for f in self._load()}
        return sorted(categories, key=_category_sort_key)

    def get_fact(self, fact_id: str) -> Optional[Dict]:
        for f in self._load():
            if f["id"] == fact_id:
                return f
        return None

    def update_fact_embedding(self, fact_id: str, embedding: List[float]) -> bool:
        with locked(self._path):
            facts = self._load()
            for f in facts:
                if f["id"] == fact_id:
                    f["embedding"] = embedding
                    f["updated_at"] = datetime.now().isoformat()
                    self._save(facts)
                    return True
            return False

    def delete_fact(self, fact_id: str) -> Optional[Dict]:
        with locked(self._path):
            facts = self._load()
            for i, f in enumerate(facts):
                if f["id"] == fact_id:
                    deleted = facts.pop(i)
                    self._save(facts)
                    return deleted
            return None

    def search_facts(self, search_term: str, category: Optional[str] = None) -> List[Dict]:
        """Case-insensitive substring match on fact content."""
        term = search_term.lower()
        return [f for f in self.list_facts(category=category) if term in f["content"].lower()]

    # -- Semantic search (embeddings attached by src/core/embeddings.py) -----

    def semantic_search(
        self, query_embedding: List[float], top_k: int = 5, category: Optional[str] = None
    ) -> List[Tuple[Dict, float]]:
        """Rank stored facts by cosine similarity to query_embedding, same
        brute-force numpy pattern as SpeakerManager.match(). Facts with no
        embedding yet (pre-migration data, or a fact whose embedding call
        failed) are skipped - callers needing full recall should also
        consult search_facts() as a substring fallback."""
        import numpy as np

        query = np.asarray(query_embedding, dtype=np.float64)
        qnorm = np.linalg.norm(query)
        if qnorm == 0:
            return []
        query = query / qnorm

        scored: List[Tuple[Dict, float]] = []
        for fact in self.list_facts(category=category):
            embedding = fact.get("embedding")
            if not embedding:
                continue
            vec = np.asarray(embedding, dtype=np.float64)
            norm = np.linalg.norm(vec)
            if norm == 0:
                continue
            score = float(np.dot(query, vec / norm))
            scored.append((fact, score))

        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]

    # -- Migration from the old markdown-per-category format ----------------

    def _migrate_legacy_markdown_if_needed(self) -> None:
        """One-time, idempotent: if facts.json doesn't exist yet but legacy
        `*.md` category files do, parse them into fact records and rename
        the sources to `.md.bak` (backup, and inert to any future *.md
        globbing)."""
        if self._path.exists():
            return
        legacy_files = list(self.long_term_dir.glob("*.md"))
        if not legacy_files:
            return

        migrated: List[Dict] = []
        for file_path in legacy_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                migrated.extend(self._parse_legacy_file(file_path.stem, content))
            except Exception as e:
                memory_logger.error(f"Error migrating legacy memory file {file_path}: {e}")
                continue
            try:
                file_path.rename(file_path.with_suffix(".md.bak"))
            except Exception as e:
                memory_logger.error(f"Error backing up legacy memory file {file_path}: {e}")

        if migrated:
            self._save(migrated)
            memory_logger.info(
                f"Migrated {len(migrated)} legacy long-term fact(s) for user {self.user_id}"
            )

    @classmethod
    def _parse_legacy_file(cls, category: str, content: str) -> List[Dict]:
        """Split a legacy `{category}.md` file's content into individual
        fact records. The first block (before any '## Updated:' marker) uses
        the file's 'Created:' timestamp; each subsequent block starts at its
        own '## Updated: {timestamp}' marker."""
        # re.split with a capturing group interleaves: [pre, ts1, block1, ts2, block2, ...]
        parts = cls._UPDATE_MARKER_RE.split(content)
        first_block, *rest = parts

        created_match = cls._CREATED_RE.search(first_block)
        first_ts = created_match.group(1).strip() if created_match else datetime.now().isoformat()
        first_content = cls._CREATED_RE.sub('', first_block)
        first_content = cls._HEADER_RE.sub('', first_content).strip()

        facts: List[Dict] = []
        if first_content:
            facts.append(cls._make_migrated_fact(category, first_content, first_ts))

        for i in range(0, len(rest) - 1, 2):
            ts = rest[i].strip()
            block_content = rest[i + 1].strip()
            if block_content:
                facts.append(cls._make_migrated_fact(category, block_content, ts))

        return facts

    @staticmethod
    def _make_migrated_fact(category: str, content: str, timestamp: str) -> Dict:
        return {
            "id": str(uuid.uuid4()),
            "category": category,
            "content": content,
            "created_at": timestamp,
            "updated_at": timestamp,
            "embedding": None,
        }
