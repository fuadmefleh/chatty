"""Wiki-style long-term memory store, modeled on Andrej Karpathy's LLM-wiki
pattern (https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):
LLM-owned markdown pages (entities/concepts) that get edited over time
rather than appended to, organized around an index.md catalog and an
append-only log.md timeline, with index-first (keyword, no embeddings)
retrieval instead of vector search.

Replaces the old flat JSON facts.json store (formerly
src/core/long_term_facts.py's LongTermFactsStore).

Frontmatter is a small fixed schema (title/type/slug/summary/tags/
created/updated/source_ids), parsed/rendered by hand rather than via a
general YAML library - the schema never needs anything YAML gives beyond
flat key: value pairs and comma-separated lists, and this avoids adding a
new runtime dependency for it.
"""
import json
import os
import re
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.core.file_lock import locked
from src.core.logging_config import get_memory_logger

memory_logger = get_memory_logger()

PAGE_TYPES = ("entity", "concept")
_TYPE_DIRS = {"entity": "entities", "concept": "concepts"}
_FRONTMATTER_FIELDS = ("title", "type", "slug", "summary", "tags", "created", "updated", "source_ids")
_LIST_FIELDS = ("tags", "source_ids")

_FRONTMATTER_RE = re.compile(r'\A---\n(.*?)\n---\n(.*)\Z', re.DOTALL)
_WIKI_LINK_RE = re.compile(r'\[[^\]]*\]\(([^)]+)\)')
_PAGE_LINK_TARGET_RE = re.compile(r'pages/(entities|concepts)/([^/]+)\.md$')


def _slugify(text: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', text.strip().lower()).strip('-')
    return slug or "untitled"


def _now() -> str:
    return datetime.now().isoformat()


def _rel_path(type_: str, slug: str) -> str:
    return f"pages/{_TYPE_DIRS[type_]}/{slug}.md"


def _parse_frontmatter(content: str) -> Tuple[Dict, str]:
    """Parse a page file's `key: value` frontmatter block. Returns
    (fields, body); fields not present default to empty string/list by
    the caller, not here."""
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return {}, content
    raw_fm, body = m.group(1), m.group(2)
    fields: Dict = {}
    for line in raw_fm.split("\n"):
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key in _LIST_FIELDS:
            fields[key] = [v.strip() for v in value.split(",") if v.strip()]
        else:
            fields[key] = value
    return fields, body


def _render_frontmatter(fields: Dict) -> str:
    lines = ["---"]
    for key in _FRONTMATTER_FIELDS:
        value = fields.get(key, "")
        if key in _LIST_FIELDS:
            value = ", ".join(value or [])
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def _render_page(fields: Dict, body: str) -> str:
    return f"{_render_frontmatter(fields)}\n\n{body.strip()}\n"


class WikiStore:
    """Manages a user's long-term memory as a directory of markdown wiki
    pages plus an index.md catalog and a log.md timeline.

    Concurrency: a single flock (wiki/.wiki.lock, via src/core/file_lock.
    locked) guards every mutating operation, since one logical op (e.g. a
    heartbeat ingest) can touch several pages plus the index in one batch.
    Reads never lock, matching the read/write asymmetry already used by
    the old LongTermFactsStore. Every file write uses a temp-file-then-
    os.replace atomic idiom.
    """

    def __init__(self, user_id: str, long_term_dir: Path):
        self.user_id = user_id
        self.long_term_dir = Path(long_term_dir)
        self.wiki_dir = self.long_term_dir / "wiki"
        self.pages_dir = self.wiki_dir / "pages"
        self.index_path = self.wiki_dir / "index.md"
        self.log_path = self.wiki_dir / "log.md"
        self.health_path = self.wiki_dir / "health.json"
        self._lock_path = self.wiki_dir / ".wiki.lock"
        self._pages_cache: Optional[List[Dict]] = None
        self._pages_cache_fingerprint: Optional[Tuple] = None

        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        for type_dir in _TYPE_DIRS.values():
            (self.pages_dir / type_dir).mkdir(parents=True, exist_ok=True)

        if not self.log_path.exists():
            self.log_path.write_text("", encoding="utf-8")

        self._migrate_legacy_facts_if_needed()

        if not self.index_path.exists():
            self.rebuild_index()

    # -- Paths -----------------------------------------------------------

    def _page_path(self, type_: str, slug: str) -> Path:
        return self.pages_dir / _TYPE_DIRS[type_] / f"{slug}.md"

    # -- Atomic I/O --------------------------------------------------------

    def _atomic_write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)

    def _backup_prev(self, path: Path) -> None:
        """Keep a one-generation-back copy of a page before overwriting it,
        as a manual recovery path if an LLM-driven rewrite silently drops
        content."""
        if path.exists():
            prev_path = path.with_suffix(path.suffix + ".prev")
            try:
                prev_path.write_bytes(path.read_bytes())
            except Exception as e:
                memory_logger.error(f"Error backing up {path} before overwrite: {e}")

    def _read_page_file(self, path: Path) -> Optional[Dict]:
        if not path.exists():
            return None
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            memory_logger.error(f"Error reading wiki page {path}: {e}")
            return None
        fields, body = _parse_frontmatter(content)
        return {
            "type": fields.get("type", ""),
            "slug": fields.get("slug", path.stem),
            "title": fields.get("title", path.stem),
            "summary": fields.get("summary", ""),
            "tags": fields.get("tags", []),
            "created": fields.get("created", ""),
            "updated": fields.get("updated", ""),
            "source_ids": fields.get("source_ids", []),
            "body": body.strip(),
            "path": str(path),
        }

    # -- Pages -------------------------------------------------------------

    def _scan_dir_fingerprint(self, dir_path: Path) -> Tuple[Tuple[str, int], ...]:
        """(filename, mtime_ns) for every *.md file in dir_path, sorted by
        name. A cheap stat-only directory snapshot used to detect writes
        made by *any* WikiStore instance/process against this same
        on-disk directory, not just this instance's own writes."""
        entries = []
        try:
            with os.scandir(dir_path) as it:
                for entry in it:
                    if not entry.name.endswith(".md"):
                        continue
                    try:
                        entries.append((entry.name, entry.stat().st_mtime_ns))
                    except OSError:
                        continue
        except OSError:
            pass
        entries.sort()
        return tuple(entries)

    def _pages_fingerprint(self) -> Tuple:
        return tuple(
            (t, self._scan_dir_fingerprint(self.pages_dir / _TYPE_DIRS[t]))
            for t in PAGE_TYPES
        )

    def _list_pages_uncached(self) -> List[Dict]:
        pages = []
        for t in PAGE_TYPES:
            dir_path = self.pages_dir / _TYPE_DIRS[t]
            if not dir_path.exists():
                continue
            for path in sorted(dir_path.glob("*.md")):
                page = self._read_page_file(path)
                if page:
                    pages.append(page)
        return pages

    def list_pages(self, type: Optional[str] = None) -> List[Dict]:
        """All pages (optionally filtered by type), backed by an in-memory
        cache keyed on a stat-only fingerprint of the pages directories -
        re-globs and re-parses page bodies only when a file was actually
        added/removed/rewritten since the last call, by this instance or
        any other process sharing the same on-disk wiki."""
        fingerprint = self._pages_fingerprint()
        if self._pages_cache is None or fingerprint != self._pages_cache_fingerprint:
            self._pages_cache = self._list_pages_uncached()
            self._pages_cache_fingerprint = fingerprint
        pages = self._pages_cache
        if type:
            pages = [p for p in pages if p["type"] == type]
        return list(pages)

    def get_page(self, type_: str, slug: str) -> Optional[Dict]:
        return self._read_page_file(self._page_path(type_, slug))

    def storage_size_bytes(self) -> int:
        """Total size of the wiki (all pages + index.md + log.md)."""
        total = 0
        for path in (self.index_path, self.log_path):
            if path.exists():
                total += path.stat().st_size
        for type_dir in _TYPE_DIRS.values():
            dir_path = self.pages_dir / type_dir
            if dir_path.exists():
                total += sum(p.stat().st_size for p in dir_path.glob("*.md"))
        return total

    def write_page(
        self, type_: str, slug: str, title: str, summary: str, body: str,
        tags: Optional[List[str]] = None, source_ids: Optional[List[str]] = None,
        rebuild_index: bool = True,
    ) -> Dict:
        """Full create-or-replace of a page's title/summary/tags/body."""
        with locked(self._lock_path):
            path = self._page_path(type_, slug)
            existing = self._read_page_file(path)
            now = _now()
            created = existing["created"] if existing else now
            merged_source_ids = (
                source_ids if source_ids is not None
                else (existing["source_ids"] if existing else [])
            )
            fields = {
                "title": title, "type": type_, "slug": slug, "summary": summary,
                "tags": tags or [], "created": created, "updated": now,
                "source_ids": merged_source_ids,
            }
            self._backup_prev(path)
            self._atomic_write(path, _render_page(fields, body))
            if rebuild_index:
                self._rebuild_index_locked()
            result = dict(fields)
            result["body"] = body
            result["path"] = str(path)
            return result

    def append_section(self, type_: str, slug: str, content: str, title_hint: Optional[str] = None) -> Dict:
        """Lightweight bullet-append: create the page if missing, else
        append `content` to its existing body. Always keeps index.md in
        sync immediately (cheap - a single page's worth of work)."""
        with locked(self._lock_path):
            path = self._page_path(type_, slug)
            existing = self._read_page_file(path)
            now = _now()
            if existing:
                new_body = existing["body"].rstrip() + "\n" + content.strip()
                title = existing["title"]
                summary = existing["summary"]
                tags = existing["tags"]
                created = existing["created"]
                source_ids = existing["source_ids"]
            else:
                new_body = content.strip()
                title = title_hint or slug.replace("-", " ").title()
                summary = content.strip().lstrip("- ").strip()[:100]
                tags = []
                created = now
                source_ids = []
            fields = {
                "title": title, "type": type_, "slug": slug, "summary": summary,
                "tags": tags, "created": created, "updated": now,
                "source_ids": source_ids,
            }
            self._backup_prev(path)
            self._atomic_write(path, _render_page(fields, new_body))
            self._rebuild_index_locked()
            result = dict(fields)
            result["body"] = new_body
            result["path"] = str(path)
            return result

    def delete_page(self, type_: str, slug: str, rebuild_index: bool = True) -> Optional[Dict]:
        with locked(self._lock_path):
            path = self._page_path(type_, slug)
            page = self._read_page_file(path)
            if page is None:
                return None
            try:
                path.unlink()
            except Exception as e:
                memory_logger.error(f"Error deleting wiki page {path}: {e}")
                return None
            if rebuild_index:
                self._rebuild_index_locked()
            return page

    def delete_line(self, type_: str, slug: str, line_text: str) -> bool:
        """Remove the first body line whose stripped text exactly matches
        `line_text` (forget()'s primitive). Deletes the whole page if the
        body becomes empty. Verbatim-text addressing (not a numeric/hash
        id) so a page lightly re-edited between "list candidates" and
        "delete chosen one" just reports not-found instead of deleting the
        wrong line."""
        with locked(self._lock_path):
            path = self._page_path(type_, slug)
            page = self._read_page_file(path)
            if page is None:
                return False
            lines = page["body"].split("\n")
            target = line_text.strip()
            for i, line in enumerate(lines):
                if line.strip() == target:
                    del lines[i]
                    new_body = "\n".join(lines).strip()
                    if not new_body:
                        path.unlink()
                        self._rebuild_index_locked()
                        return True
                    fields = {k: page[k] for k in _FRONTMATTER_FIELDS if k != "updated"}
                    fields["updated"] = _now()
                    self._backup_prev(path)
                    self._atomic_write(path, _render_page(fields, new_body))
                    return True
            return False

    # -- Index / log --------------------------------------------------------

    def read_index(self) -> str:
        if not self.index_path.exists():
            return "# Wiki Index\n\nNo pages yet.\n"
        return self.index_path.read_text(encoding="utf-8")

    def read_log(self, tail: int = 50) -> str:
        if not self.log_path.exists():
            return ""
        lines = [l for l in self.log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        return "\n".join(lines[-tail:])

    def append_log(self, op: str, message: str) -> None:
        with locked(self._lock_path):
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(f"## [{_now()}] {op} | {message}\n")

    def read_health(self) -> Optional[Dict]:
        """Return the last-persisted lint run's structured findings (see
        MemoryManager.lint_wiki()), or None if lint has never run for this
        user yet."""
        if not self.health_path.exists():
            return None
        try:
            return json.loads(self.health_path.read_text(encoding="utf-8"))
        except Exception as e:
            memory_logger.error(f"Error reading wiki health.json for {self.user_id}: {e}")
            return None

    def write_health(self, data: Dict) -> None:
        """Atomically overwrite the health sidecar with the latest lint
        run's findings. No lock needed beyond the atomic write itself -
        health.json is a snapshot, never read-modify-written."""
        self._atomic_write(self.health_path, json.dumps(data, indent=2))

    def rebuild_index(self) -> None:
        with locked(self._lock_path):
            self._rebuild_index_locked()

    def _rebuild_index_locked(self) -> None:
        pages = self.list_pages()
        lines = ["# Wiki Index", "", f"Last updated: {_now()}"]
        if not pages:
            lines.append("")
            lines.append("No pages yet.")
        for type_ in PAGE_TYPES:
            type_pages = [p for p in pages if p["type"] == type_]
            if not type_pages:
                continue
            lines.append("")
            lines.append(f"## {type_.capitalize()}s")
            lines.append("")
            for p in sorted(type_pages, key=lambda p: p["title"].lower()):
                tags_str = ", ".join(p["tags"]) if p["tags"] else ""
                tag_suffix = f" `{tags_str}`" if tags_str else ""
                lines.append(f"- [{p['title']}]({_rel_path(p['type'], p['slug'])}) — {p['summary']}{tag_suffix}")
        self._atomic_write(self.index_path, "\n".join(lines).rstrip() + "\n")

    # -- Search --------------------------------------------------------------

    def find_matches(self, query: str) -> List[Dict]:
        """Substring match over every page's body lines - forget()'s lookup."""
        term = query.lower()
        matches = []
        for page in self.list_pages():
            for i, line in enumerate(page["body"].split("\n")):
                stripped = line.strip()
                if stripped and term in stripped.lower():
                    matches.append({
                        "type": page["type"], "slug": page["slug"], "title": page["title"],
                        "line_no": i, "line_text": stripped,
                    })
        return matches

    def search_index(self, query: str, top_k: int = 5) -> List[Dict]:
        """Keyword-score pages by query-term hits in title/summary/tags -
        recall()'s primary, embedding-free lookup."""
        terms = [t for t in re.split(r'\s+', query.lower().strip()) if t]
        if not terms:
            return []
        scored: List[Tuple[Dict, float]] = []
        query_lower = query.lower().strip()
        for page in self.list_pages():
            haystack = f"{page['title']} {page['summary']} {' '.join(page['tags'])}".lower()
            score = sum(haystack.count(t) for t in terms)
            if query_lower and query_lower in page["title"].lower():
                score += 10
            if score > 0:
                scored.append((page, score))
        scored.sort(key=lambda pair: (pair[1], pair[0]["updated"]), reverse=True)
        return [p for p, _ in scored[:top_k]]

    def search_pages_fulltext(self, query: str, top_k: int = 5) -> List[Dict]:
        """Grep-style substring search over full page bodies - the small-
        wiki/zero-keyword-hit fallback."""
        term = query.lower()
        matches = [p for p in self.list_pages() if term in p["body"].lower()]
        matches.sort(key=lambda p: p["updated"], reverse=True)
        return matches[:top_k]

    # -- Lint primitives -------------------------------------------------------

    def find_duplicate_pages(self, threshold: float = 0.95) -> List[Tuple[Dict, Dict]]:
        """Near-duplicate page pairs by title+summary similarity. Stricter
        threshold than the old flat-fact dedupe's 0.85, since merging whole
        pages is riskier than deleting one duplicate fact line."""
        pages = self.list_pages()
        pairs = []
        seen = set()
        for i in range(len(pages)):
            key_i = (pages[i]["type"], pages[i]["slug"])
            if key_i in seen:
                continue
            for j in range(i + 1, len(pages)):
                key_j = (pages[j]["type"], pages[j]["slug"])
                if key_j in seen:
                    continue
                ratio = SequenceMatcher(
                    None,
                    f"{pages[i]['title']} {pages[i]['summary']}",
                    f"{pages[j]['title']} {pages[j]['summary']}",
                ).ratio()
                if ratio >= threshold:
                    pairs.append((pages[i], pages[j]))
                    seen.add(key_i)
                    seen.add(key_j)
                    break
        return pairs

    def merge_pages(self, keep: Dict, remove: Dict) -> None:
        """Fold `remove`'s body into `keep` under a 'Merged from' heading,
        then delete `remove`. Caller picks which of a duplicate pair to
        keep (typically the more recently updated one)."""
        with locked(self._lock_path):
            keep_path = self._page_path(keep["type"], keep["slug"])
            current_keep = self._read_page_file(keep_path)
            if current_keep is None:
                return
            merged_body = (
                current_keep["body"].rstrip()
                + f"\n\n## Merged from {remove['title']}\n\n"
                + remove["body"].strip()
            )
            fields = {k: current_keep[k] for k in _FRONTMATTER_FIELDS if k not in ("updated", "source_ids")}
            fields["updated"] = _now()
            fields["source_ids"] = sorted(set(
                (current_keep.get("source_ids") or []) + (remove.get("source_ids") or [])
            ))
            self._backup_prev(keep_path)
            self._atomic_write(keep_path, _render_page(fields, merged_body))

            remove_path = self._page_path(remove["type"], remove["slug"])
            if remove_path.exists():
                remove_path.unlink()

            self._rebuild_index_locked()

    def fix_missing_cross_references(self) -> int:
        """Rewrite a bare literal mention of another page's title into a
        markdown link to that page. Pure syntactic edit - safe to always
        auto-apply. Returns the number of pages edited."""
        pages = self.list_pages()
        fixed = 0
        with locked(self._lock_path):
            for page in pages:
                body = page["body"]
                new_body = body
                for other in pages:
                    if (other["type"], other["slug"]) == (page["type"], page["slug"]):
                        continue
                    title = other["title"]
                    if not title or len(title) < 3:
                        continue
                    link = f"[{title}]({_rel_path(other['type'], other['slug'])})"
                    if title in new_body and link not in new_body:
                        pattern = re.compile(r'(?<!\[)\b' + re.escape(title) + r'\b(?!\])')
                        replaced, n = pattern.subn(link, new_body, count=1)
                        if n:
                            new_body = replaced
                if new_body != body:
                    fields = {k: page[k] for k in _FRONTMATTER_FIELDS}
                    path = self._page_path(page["type"], page["slug"])
                    self._backup_prev(path)
                    self._atomic_write(path, _render_page(fields, new_body))
                    fixed += 1
        return fixed

    def _build_link_index(self, pages: Optional[List[Dict]] = None) -> Dict[Tuple[str, str], List[Tuple[str, str]]]:
        """Map each target (type, slug) page to the list of source (type,
        slug) pages whose body links to it. Shared by find_orphan_pages
        and get_backlinks so both parse every page's links exactly once
        per call rather than duplicating the same regex walk."""
        pages = pages if pages is not None else self.list_pages()
        index: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
        for page in pages:
            src_key = (page["type"], page["slug"])
            for match in _WIKI_LINK_RE.finditer(page["body"]):
                target_match = _PAGE_LINK_TARGET_RE.search(match.group(1))
                if not target_match:
                    continue
                type_dir, slug = target_match.group(1), target_match.group(2)
                type_ = "entity" if type_dir == "entities" else "concept"
                target_key = (type_, slug)
                if target_key != src_key:
                    index.setdefault(target_key, []).append(src_key)
        return index

    def find_orphan_pages(self) -> List[Dict]:
        """Pages with zero inbound links from other pages' bodies (index.md
        doesn't count - every page is trivially listed there)."""
        pages = self.list_pages()
        linked_targets = set(self._build_link_index(pages).keys())
        return [p for p in pages if (p["type"], p["slug"]) not in linked_targets]

    def get_backlinks(self, type_: str, slug: str) -> List[Dict]:
        """Pages whose body links to (type_, slug) - the 'What links here'
        list. Recomputed on demand like the rest of this class (no
        persisted link index); fine at this wiki's expected per-user
        scale (dozens to low hundreds of pages)."""
        pages = self.list_pages()
        by_key = {(p["type"], p["slug"]): p for p in pages}
        sources = self._build_link_index(pages).get((type_, slug), [])
        seen = set()
        result = []
        for key in sources:
            if key in seen:
                continue
            seen.add(key)
            if key in by_key:
                result.append(by_key[key])
        result.sort(key=lambda p: p["title"].lower())
        return result

    # -- Migration from the old flat facts.json format -----------------------

    def _migrate_legacy_facts_if_needed(self) -> None:
        """One-time, idempotent: if facts.json exists and the wiki has no
        pages yet, migrate it into one concept page per category (a
        'dump, don't curate' landing zone - the heartbeat's ingest and lint
        passes organically refile this over subsequent cycles), then
        rename facts.json to facts.json.bak (never deleted)."""
        facts_path = self.long_term_dir / "facts.json"
        if not facts_path.exists():
            return
        if any(self.pages_dir.rglob("*.md")):
            return

        try:
            facts = json.loads(facts_path.read_text(encoding="utf-8"))
        except Exception as e:
            memory_logger.error(f"Error reading legacy facts.json for {self.user_id}: {e}")
            return

        by_category: Dict[str, List[Dict]] = {}
        for fact in facts:
            by_category.setdefault(fact.get("category", "important_facts"), []).append(fact)

        migrated_count = 0
        for category, category_facts in by_category.items():
            slug = _slugify(category)
            body = "\n".join(
                f"- {f['content']} (migrated, originally updated {f.get('updated_at', '')})"
                for f in category_facts
            )
            title = category.replace("_", " ").replace("-", " ").title()
            self.write_page(
                type_="concept", slug=slug, title=title,
                summary="Migrated flat facts not yet split into dedicated pages.",
                body=body, tags=["migration"],
                source_ids=[f["id"] for f in category_facts],
                rebuild_index=False,
            )
            migrated_count += len(category_facts)

        self.rebuild_index()

        if migrated_count != len(facts):
            memory_logger.error(
                f"Wiki migration count mismatch for {self.user_id}: "
                f"migrated {migrated_count} bullet lines from {len(facts)} facts"
            )

        self.append_log(
            "migrate",
            f"Bulk-migrated facts.json ({len(facts)} facts across {len(by_category)} "
            f"categories) into {len(by_category)} concept page(s)",
        )

        try:
            facts_path.rename(facts_path.with_suffix(".json.bak"))
        except Exception as e:
            memory_logger.error(f"Error backing up legacy facts.json for {self.user_id}: {e}")
