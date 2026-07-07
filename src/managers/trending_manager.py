"""Trending-repo suggestions: Chatty scans GitHub's trending Python/TypeScript/
JavaScript repos, asks an LLM to curate a short list of ideas worth considering
for its own codebase, and stores them as a menu for a human to review.

Unlike src/managers/self_upgrade_manager.py, nothing here ever runs the coding
agent automatically - run_trending_scan() only proposes. A suggestion is only
turned into a FeatureRequest (and thus implemented) when a human picks
"Implement" on the dashboard (see chatty_web_server.py's
/api/chatty/trending-suggestions/{id}/implement endpoint), which reuses the
same feature_requests_manager the manual dashboard queue already uses.

Flow, driven by HeartbeatManager._process_trending_suggestions():
1. _scan_trending_repos() - scrape github.com/trending/{language}?since=weekly
   for each configured language (GitHub has no official "trending" API; this
   mirrors the scraping approach already used by skills/stocks/yahoo_client.py).
2. _curate_ideas() - LLM picks a handful worth integrating, with a rationale
   and a ready-to-use prompt for the coding agent.
3. run_trending_scan() - dedups against every repo ever suggested (so the same
   repo isn't re-proposed every cycle) and stores the rest as pending suggestions.
"""
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import uuid

import httpx
from bs4 import BeautifulSoup

from src.core import config
from src.core.logging_config import get_heartbeat_logger

logger = get_heartbeat_logger()

GITHUB_TRENDING_URL = "https://github.com/trending/{language}"
GITHUB_TRENDING_HEADERS = {"User-Agent": "chatty-trending-scan"}


class TrendingSuggestion:
    """A single curated idea from a GitHub trending scan."""

    def __init__(
        self,
        suggestion_id: str,
        repo: str,
        repo_url: str,
        description: str,
        language: str,
        stars: str,
        rationale: str,
        integration_prompt: str,
        status: str,
        created_at: str,
        updated_at: str,
        request_id: Optional[str] = None,
    ):
        self.id = suggestion_id
        self.repo = repo
        self.repo_url = repo_url
        self.description = description
        self.language = language
        self.stars = stars
        self.rationale = rationale
        self.integration_prompt = integration_prompt
        self.status = status  # pending | implemented | dismissed
        self.created_at = created_at
        self.updated_at = updated_at
        self.request_id = request_id  # set once "Implement" creates a FeatureRequest

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "repo": self.repo,
            "repo_url": self.repo_url,
            "description": self.description,
            "language": self.language,
            "stars": self.stars,
            "rationale": self.rationale,
            "integration_prompt": self.integration_prompt,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "request_id": self.request_id,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "TrendingSuggestion":
        return cls(
            suggestion_id=data["id"],
            repo=data["repo"],
            repo_url=data["repo_url"],
            description=data.get("description", ""),
            language=data.get("language", ""),
            stars=data.get("stars", ""),
            rationale=data.get("rationale", ""),
            integration_prompt=data.get("integration_prompt", ""),
            status=data.get("status", "pending"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            request_id=data.get("request_id"),
        )


class TrendingSuggestionsManager:
    """Manages GitHub-trending suggestions with persistent JSON storage.

    Mirrors skills/pi_agent/requests_manager.py's whole-file load/save pattern.
    """

    def __init__(self, data_dir: str = str(config.BASE_DIR / "data" / "trending_suggestions")):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._file = self.data_dir / "suggestions.json"

    def _load(self) -> List[TrendingSuggestion]:
        if not self._file.exists():
            return []
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [TrendingSuggestion.from_dict(s) for s in data]
        except Exception as e:
            logger.error(f"Error loading trending suggestions: {e}")
            return []

    def _save(self, suggestions: List[TrendingSuggestion]) -> None:
        try:
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump([s.to_dict() for s in suggestions], f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving trending suggestions: {e}")
            raise

    def create(
        self,
        repo: str,
        repo_url: str,
        description: str,
        language: str,
        stars: str,
        rationale: str,
        integration_prompt: str,
    ) -> TrendingSuggestion:
        suggestions = self._load()
        now = datetime.now().isoformat()
        new_suggestion = TrendingSuggestion(
            suggestion_id=str(uuid.uuid4()),
            repo=repo,
            repo_url=repo_url,
            description=description,
            language=language,
            stars=stars,
            rationale=rationale,
            integration_prompt=integration_prompt,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        suggestions.append(new_suggestion)
        self._save(suggestions)
        return new_suggestion

    def list(self) -> List[TrendingSuggestion]:
        """All suggestions, newest first."""
        suggestions = self._load()
        return sorted(suggestions, key=lambda s: s.created_at, reverse=True)

    def list_by_status(self, status: str) -> List[TrendingSuggestion]:
        return [s for s in self.list() if s.status == status]

    def get(self, suggestion_id: str) -> Optional[TrendingSuggestion]:
        for s in self._load():
            if s.id == suggestion_id:
                return s
        return None

    def update(self, suggestion_id: str, **fields) -> Optional[TrendingSuggestion]:
        suggestions = self._load()
        for s in suggestions:
            if s.id == suggestion_id:
                for key, value in fields.items():
                    setattr(s, key, value)
                s.updated_at = datetime.now().isoformat()
                self._save(suggestions)
                return s
        return None

    def delete(self, suggestion_id: str) -> bool:
        suggestions = self._load()
        original_count = len(suggestions)
        suggestions = [s for s in suggestions if s.id != suggestion_id]
        if len(suggestions) < original_count:
            self._save(suggestions)
            return True
        return False

    def seen_repos(self) -> set:
        """Every repo ("owner/repo") ever suggested, so a scan never proposes
        the same repo twice regardless of its current status."""
        return {s.repo for s in self._load()}


async def _scan_trending_repos(languages: List[str], per_language: int) -> List[Dict]:
    """Scrape github.com/trending/{language}?since=weekly for each language.

    GitHub has no official "trending" API - this mirrors the HTML-scraping
    approach already used by skills/stocks/yahoo_client.py for Yahoo Finance.
    """
    repos: List[Dict] = []
    async with httpx.AsyncClient(timeout=15.0, headers=GITHUB_TRENDING_HEADERS) as client:
        for language in languages:
            try:
                resp = await client.get(
                    GITHUB_TRENDING_URL.format(language=language),
                    params={"since": "weekly"},
                )
                if resp.status_code != 200:
                    logger.warning(f"Trending scan for '{language}' got status {resp.status_code}")
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                for article in soup.select("article.Box-row")[:per_language]:
                    link = article.select_one("h2 a")
                    if not link or not link.get("href"):
                        continue
                    full_name = link["href"].strip("/")
                    if "/" not in full_name:
                        continue

                    desc_el = article.select_one("p")
                    description = desc_el.get_text(strip=True) if desc_el else ""

                    stars_el = article.select_one('a[href$="/stargazers"]')
                    stars = stars_el.get_text(strip=True) if stars_el else "?"

                    repos.append({
                        "repo": full_name,
                        "repo_url": f"https://github.com/{full_name}",
                        "description": description,
                        "language": language,
                        "stars": stars,
                    })
            except Exception as e:
                logger.error(f"Trending scan failed for '{language}': {e}", exc_info=True)

    return repos


_README_CANDIDATES = ("README.md", "readme.md", "Readme.md", "README.rst")
_README_EXCERPT_MAX_CHARS = 600


async def _fetch_readme_excerpt(repo: str) -> str:
    """Best-effort fetch of a repo's README so curated ideas can reference
    real concepts/approaches from the project's own code, not just the
    one-line blurb scraped off the trending page. "HEAD" resolves to the
    default branch on raw.githubusercontent.com regardless of whether it's
    main/master, so no separate branch lookup is needed. Truncated hard -
    with up to TRENDING_REPOS_PER_LANGUAGE * len(languages) new repos in one
    scan, an untruncated README per repo would blow up the curation prompt."""
    async with httpx.AsyncClient(timeout=10.0, headers=GITHUB_TRENDING_HEADERS) as client:
        for filename in _README_CANDIDATES:
            try:
                resp = await client.get(f"https://raw.githubusercontent.com/{repo}/HEAD/{filename}")
                if resp.status_code == 200 and resp.text.strip():
                    return resp.text.strip()[:_README_EXCERPT_MAX_CHARS]
            except Exception as e:
                logger.warning(f"Could not fetch README for {repo}: {e}")
                break
    return ""


def _extract_json_array(text: str) -> Optional[list]:
    """Best-effort JSON-array parse: try the whole reply first, then fall back
    to the first [...] substring in case the model wrapped it in prose or a
    code fence."""
    text = text.strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return None


async def _curate_ideas(repos: List[Dict], skills_manager) -> List[Dict]:
    """Ask the LLM to pick a handful of scanned repos worth integrating into
    Chatty, each with a rationale and a ready-to-use coding-agent prompt."""
    if not repos:
        return []

    try:
        from openai import AsyncOpenAI

        skills_summary = "\n".join(
            f"- {s.name}: {s.description} ({len(s.tools)} tools)"
            for s in skills_manager.get_all_skills()
        ) or "(no skills loaded)"

        repos_text = "\n\n".join(
            f"- {r['repo']} ({r['language']}, {r['stars']} stars): {r['description']}"
            + (f"\n  README excerpt: {r['readme_excerpt']}" if r.get("readme_excerpt") else "")
            for r in repos
        )

        max_ideas = config.TRENDING_MAX_SUGGESTIONS_PER_SCAN

        prompt = f"""You are Chatty, a personal AI assistant, looking outward for ideas as part of
your autonomous heartbeat. Below is a list of repositories currently trending on GitHub (past
week) across Python, TypeScript, and JavaScript, each with a README excerpt where one was found.

Your current skills:
{skills_summary}

Trending repositories:
{repos_text}

Pick at most {max_ideas} of these repos that are genuinely worth considering integrating into
your own codebase - not every trending repo is relevant, and it's fine to pick fewer than
{max_ideas} or none at all.

Each idea MUST be a whole feature with both backend and frontend integration, not just a bare
`skills/` tool exposed only through chat. Chatty's web dashboard (order_explorer_site/frontend/)
already has plenty of precedent for this shape - a dedicated page wired through chattyApi.ts and
added to the nav, backed by REST endpoints in chatty_web_server.py (or a skill's own module): the
Webcams page, the Video Production page (skills/video_production/ + its job-history UI), the
Storage Breakdown panel on Server Health, and inline generated-image rendering in Chat. A new idea
should follow that same pattern - propose the dashboard page/panel alongside the backend piece,
not backend alone.

Ground the idea in the README excerpt's actual concepts/approach (an algorithm, a data model, a
specific capability the project demonstrates) rather than a generic "wraps <repo>'s API" - if a
repo has no README excerpt or nothing concrete to draw on, skip it rather than guessing.

Reply with ONLY a JSON array (no prose, no code fences), where each element is:
{{"repo": "<owner/repo, exactly as listed above>",
  "rationale": "<one or two sentences on why this is worth considering, citing the concept from
  the README you're drawing on>",
  "integration_prompt": "<a direct instruction to a coding agent describing the concrete backend
  AND frontend change to make, e.g. 'Add a <Name> page to the dashboard (nav entry + component in
  order_explorer_site/frontend/src/pages/, wired through chattyApi.ts) backed by a new
  /api/chatty/<name> endpoint in chatty_web_server.py that <does X, using <repo>'s approach to
  Y>.'>"}}

If nothing listed is worth suggesting, reply with exactly: []"""

        client = AsyncOpenAI(api_key=config.CHAT_API_KEY, base_url=config.CHAT_BASE_URL)
        response = await client.chat.completions.create(
            model=config.CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )

        text = (response.choices[0].message.content or "").strip()
        ideas = _extract_json_array(text)
        if not ideas:
            return []

        repos_by_name = {r["repo"]: r for r in repos}
        curated = []
        for idea in ideas[:max_ideas]:
            if not isinstance(idea, dict):
                continue
            repo_name = idea.get("repo")
            if repo_name not in repos_by_name:
                continue
            curated.append({
                **repos_by_name[repo_name],
                "rationale": idea.get("rationale", ""),
                "integration_prompt": idea.get("integration_prompt", ""),
            })
        return curated

    except Exception as e:
        logger.error(f"Error curating trending ideas: {e}", exc_info=True)
        return []


async def run_trending_scan(skills_manager, suggestions_manager: TrendingSuggestionsManager) -> Optional[str]:
    """Scan GitHub trending, curate ideas, and store any new ones as pending
    suggestions. Returns a one-line summary, or None if nothing new was found."""
    languages = [lang.strip() for lang in config.TRENDING_LANGUAGES.split(",") if lang.strip()]
    repos = await _scan_trending_repos(languages, config.TRENDING_REPOS_PER_LANGUAGE)

    already_seen = suggestions_manager.seen_repos()
    new_repos = [r for r in repos if r["repo"] not in already_seen]
    if not new_repos:
        return None

    # Ground curation in each repo's actual README rather than just the
    # one-line trending-page blurb - fetched concurrently since this is a
    # handful of independent HTTP calls, not a hot path (runs at most once
    # per TRENDING_SCAN_INTERVAL_HOURS).
    readme_excerpts = await asyncio.gather(*(_fetch_readme_excerpt(r["repo"]) for r in new_repos))
    for r, excerpt in zip(new_repos, readme_excerpts):
        r["readme_excerpt"] = excerpt

    ideas = await _curate_ideas(new_repos, skills_manager)
    if not ideas:
        return None

    for idea in ideas:
        suggestions_manager.create(
            repo=idea["repo"],
            repo_url=idea["repo_url"],
            description=idea["description"],
            language=idea["language"],
            stars=idea["stars"],
            rationale=idea["rationale"],
            integration_prompt=idea["integration_prompt"],
        )

    repo_names = ", ".join(idea["repo"] for idea in ideas)
    return f"Found {len(ideas)} new self-improve suggestion(s) from GitHub trending: {repo_names}."
