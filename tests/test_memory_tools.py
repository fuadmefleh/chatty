"""Tests for the memory system: MemoryManager (src/core/memory.py) and
MemoryTools (src/core/memory_tools.py), backed by the wiki store
(src/core/wiki_store.py)."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import config
from src.core.memory import MemoryManager
from src.core.memory_tools import MemoryTools

USER_ID = "test_user"


@pytest.fixture
def memory_dir(tmp_path, monkeypatch):
    """Point config.MEMORY_DIR at an isolated tmp directory for this test."""
    monkeypatch.setattr(config, "MEMORY_DIR", tmp_path)
    return tmp_path


class StubLLM:
    """Minimal stand-in for an LLMProvider - only needs an async complete().
    Accepts either a single canned response string (returned for every
    call) or a list of responses returned in call order, for multi-call
    flows like the wiki ingest's triage-then-edit."""

    def __init__(self, content):
        if isinstance(content, list):
            self._responses = content
        else:
            self._responses = None
            self._content = content
        self._call_index = 0

    async def complete(self, messages, *, response_format="text", temperature=None):
        if self._responses is not None:
            response = self._responses[min(self._call_index, len(self._responses) - 1)]
            self._call_index += 1
            return SimpleNamespace(content=response)
        return SimpleNamespace(content=self._content)


class StubAgent:
    """Minimal stand-in for a StagedReACTAgent - consolidate_memories only
    needs agent.llm.complete(), not the full ReACT pipeline."""

    def __init__(self, response):
        self.llm = StubLLM(response)


_EMPTY_LINT_LLM_RESPONSE = json.dumps({"contradictions": [], "coverage_gaps": []})


@pytest.mark.asyncio
async def test_add_interaction_and_get_recent_memory(memory_dir):
    mgr = MemoryManager(USER_ID)
    await mgr.add_interaction("hello there", "hi, how can I help?")

    recent = await mgr.get_recent_memory(days=7)
    assert "hello there" in recent
    assert "hi, how can I help?" in recent


@pytest.mark.asyncio
async def test_add_long_term_memory_creates_wiki_page(memory_dir):
    mgr = MemoryManager(USER_ID)
    await mgr.add_long_term_memory("important_facts", "User's name is Sam.")
    await mgr.add_long_term_memory("important_facts", "User was born in June.")

    page = mgr._wiki_store.get_page("concept", "important-facts")
    assert page is not None
    assert "User's name is Sam." in page["body"]
    assert "User was born in June." in page["body"]


@pytest.mark.asyncio
async def test_save_important_fact_delegates_to_add_long_term_memory(memory_dir):
    """save_important_fact should write via the same MemoryManager path as
    add_long_term_memory (single write path, no duplicated storage)."""
    tools = MemoryTools(USER_ID)
    result = await tools.save_important_fact("facts", "User's favorite color is blue.")
    assert "Successfully saved" in result

    result = await tools.save_important_fact("facts", "User's favorite food is sushi.")
    assert "Successfully saved" in result

    page = tools._wiki_store.get_page("concept", "important-facts")
    assert "User's favorite color is blue." in page["body"]
    assert "User's favorite food is sushi." in page["body"]


@pytest.mark.asyncio
async def test_save_important_fact_category_mapping(memory_dir):
    tools = MemoryTools(USER_ID)
    await tools.save_important_fact("family", "Has a sister named Jane.")

    page = tools._wiki_store.get_page("concept", "relationships")
    assert page is not None
    assert "Has a sister named Jane." in page["body"]


@pytest.mark.asyncio
async def test_save_important_fact_unmapped_category_passes_through(memory_dir):
    """An unrecognized category should be stored under its own page, not
    silently collapsed into 'important_facts'."""
    tools = MemoryTools(USER_ID)
    await tools.save_important_fact("hobbies", "Plays guitar.")

    page = tools._wiki_store.get_page("concept", "hobbies")
    assert page is not None
    assert "Plays guitar." in page["body"]
    assert tools._wiki_store.get_page("concept", "important-facts") is None


@pytest.mark.asyncio
async def test_get_short_term_files_for_consolidation_cutoff(memory_dir):
    mgr = MemoryManager(USER_ID)
    old_file = mgr.short_term_dir / "2020-01-01.md"
    old_file.write_text("# old\n")
    recent_file = mgr._get_today_file()
    recent_file.write_text("# today\n")

    to_consolidate = await mgr.get_short_term_files_for_consolidation(days_old=7)

    assert old_file in to_consolidate
    assert recent_file not in to_consolidate


@pytest.mark.asyncio
async def test_archive_short_term_memory_moves_file(memory_dir):
    mgr = MemoryManager(USER_ID)
    file_path = mgr.short_term_dir / "2020-01-01.md"
    file_path.write_text("# old\n")

    await mgr.archive_short_term_memory(file_path)

    assert not file_path.exists()
    assert (mgr.short_term_dir / "archived" / "2020-01-01.md").exists()


@pytest.mark.asyncio
async def test_consolidate_memories_writes_long_term_and_archives(memory_dir):
    mgr = MemoryManager(USER_ID)
    old_file = mgr.short_term_dir / "2020-01-01.md"
    old_file.write_text("# Memory Log - 2020-01-01\n\n**User**: My birthday is June 1st.\n")

    triage_response = json.dumps({
        "update_pages": [],
        "create_pages": [{"type": "concept", "slug": "important-facts", "title": "Important Facts"}],
    })
    edit_response = json.dumps({
        "pages": [{
            "type": "concept", "slug": "important-facts", "title": "Important Facts",
            "summary": "Key facts about the user.", "tags": [],
            "body": "- User's birthday is June 1st.",
        }],
    })
    result = await mgr.consolidate_memories(StubAgent([triage_response, edit_response]))

    assert "Successfully consolidated" in result
    assert not old_file.exists()
    assert (mgr.short_term_dir / "archived" / "2020-01-01.md").exists()
    page = mgr._wiki_store.get_page("concept", "important-facts")
    assert page is not None
    assert "June 1st" in page["body"]


@pytest.mark.asyncio
async def test_consolidate_memories_nothing_memory_worthy_still_archives(memory_dir):
    mgr = MemoryManager(USER_ID)
    old_file = mgr.short_term_dir / "2020-01-01.md"
    old_file.write_text("# Memory Log - 2020-01-01\n\n**User**: just saying hi.\n")

    triage_response = json.dumps({"update_pages": [], "create_pages": []})
    result = await mgr.consolidate_memories(StubAgent(triage_response))

    # Matches the pre-existing contract: a successful ingest run archives
    # the processed files regardless of whether anything memory-worthy was
    # actually found in them.
    assert "Successfully consolidated" in result
    assert not old_file.exists()
    assert (mgr.short_term_dir / "archived" / "2020-01-01.md").exists()


@pytest.mark.asyncio
async def test_get_long_term_memory_no_truncation_by_default(memory_dir):
    mgr = MemoryManager(USER_ID)
    long_content = "x" * 5000
    await mgr.add_long_term_memory("important_facts", long_content)

    result = await mgr.get_long_term_memory()
    assert long_content in result


@pytest.mark.asyncio
async def test_get_long_term_memory_fair_budget_across_pages(memory_dir):
    mgr = MemoryManager(USER_ID)
    # "relationships" sorts first alphabetically among page slugs and is
    # made large enough that a naive "truncate the joined blob" approach
    # would starve "important_facts" out entirely.
    await mgr.add_long_term_memory("relationships", "R" * 2000)
    await mgr.add_long_term_memory("important_facts", "IMPORTANT_MARKER")

    result = await mgr.get_long_term_memory(max_chars=1000)
    assert "IMPORTANT_MARKER" in result


@pytest.mark.asyncio
async def test_forget_fact_auto_deletes_single_match(memory_dir):
    tools = MemoryTools(USER_ID)
    await tools.save_important_fact("facts", "User likes sushi.")

    result = await tools.forget_fact("sushi")

    assert "Forgot" in result
    assert tools._wiki_store.get_page("concept", "important-facts") is None


@pytest.mark.asyncio
async def test_forget_fact_lists_candidates_on_multiple_matches(memory_dir):
    tools = MemoryTools(USER_ID)
    await tools.save_important_fact("facts", "User likes sushi.")
    await tools.save_important_fact("facts", "User's coworker also likes sushi.")

    result = await tools.forget_fact("sushi")

    assert "Found 2 matching facts" in result
    page = tools._wiki_store.get_page("concept", "important-facts")
    assert page is not None
    assert page["body"].count("sushi") == 2  # nothing deleted yet - ambiguous

    # Follow-up: find the matches again (as the LLM/Telegram caller would)
    # and delete one via forget_match.
    matches = tools._wiki_store.find_matches("sushi")
    delete_result = await tools.forget_match(matches[0])
    assert "Forgot" in delete_result
    remaining = tools._wiki_store.get_page("concept", "important-facts")
    assert remaining is not None
    assert remaining["body"].count("sushi") == 1


@pytest.mark.asyncio
async def test_forget_fact_no_match(memory_dir):
    tools = MemoryTools(USER_ID)
    result = await tools.forget_fact("nonexistent topic")
    assert "No matching" in result


@pytest.mark.asyncio
async def test_forget_match_unknown_line_returns_not_found(memory_dir):
    tools = MemoryTools(USER_ID)
    await tools.save_important_fact("facts", "User likes sushi.")

    result = await tools.forget_match({
        "type": "concept", "slug": "important-facts", "title": "Important Facts",
        "line_text": "- nonexistent line",
    })

    assert "No fact found" in result


@pytest.mark.asyncio
async def test_lint_wiki_merges_near_duplicate_pages(memory_dir, monkeypatch):
    mgr = MemoryManager(USER_ID)
    mgr._wiki_store.write_page(type_="concept", slug="budgeting", title="Budgeting",
                                summary="Tracks monthly spending goals for the user.", body="- a")
    mgr._wiki_store.write_page(type_="concept", slug="budget", title="Budgeting",
                                summary="Tracks monthly spending goals for the user!", body="- b")

    monkeypatch.setattr("src.core.memory.get_llm_provider", lambda: StubLLM(_EMPTY_LINT_LLM_RESPONSE))

    result = await mgr.lint_wiki()

    assert "duplicate page(s) merged" in result
    assert len(mgr._wiki_store.list_pages()) == 1


@pytest.mark.asyncio
async def test_lint_wiki_auto_links_cross_references(memory_dir, monkeypatch):
    mgr = MemoryManager(USER_ID)
    mgr._wiki_store.write_page(type_="entity", slug="sarah", title="Sarah", summary="s", body="- Sister.")
    mgr._wiki_store.write_page(type_="concept", slug="family-trip", title="Family Trip", summary="s",
                                body="- Went hiking with Sarah last month.")

    monkeypatch.setattr("src.core.memory.get_llm_provider", lambda: StubLLM(_EMPTY_LINT_LLM_RESPONSE))

    result = await mgr.lint_wiki()

    assert "cross-reference(s) added" in result
    page = mgr._wiki_store.get_page("concept", "family-trip")
    assert "[Sarah](pages/entities/sarah.md)" in page["body"]


@pytest.mark.asyncio
async def test_lint_wiki_flags_orphans_contradictions_and_gaps_without_applying(memory_dir, monkeypatch):
    mgr = MemoryManager(USER_ID)
    mgr._wiki_store.write_page(type_="concept", slug="topic-a", title="Topic A", summary="s", body="- claim one")
    mgr._wiki_store.write_page(type_="concept", slug="topic-b", title="Topic B", summary="s", body="- claim two")

    stub_response = json.dumps({
        "contradictions": [{"page_a": "concept/topic-a", "page_b": "concept/topic-b", "description": "conflict"}],
        "coverage_gaps": [{"suggested_title": "New Topic", "suggested_type": "concept", "description": "gap"}],
    })
    monkeypatch.setattr("src.core.memory.get_llm_provider", lambda: StubLLM(stub_response))

    result = await mgr.lint_wiki()

    assert "orphan page(s)" in result
    assert "1 contradiction" in result
    assert "1 coverage gap" in result
    # Flag-only: nothing auto-applied for these, page count/content unchanged.
    assert len(mgr._wiki_store.list_pages()) == 2
    log_text = mgr._wiki_store.read_log()
    assert "Contradiction flagged" in log_text
    assert "Coverage gap flagged" in log_text
    assert "Orphan page flagged" in log_text


@pytest.mark.asyncio
async def test_lint_wiki_persists_health_json(memory_dir, monkeypatch):
    mgr = MemoryManager(USER_ID)
    mgr._wiki_store.write_page(type_="concept", slug="topic-a", title="Topic A", summary="s", body="- claim one")
    mgr._wiki_store.write_page(type_="concept", slug="topic-b", title="Topic B", summary="s", body="- claim two")

    stub_response = json.dumps({
        "contradictions": [{"page_a": "concept/topic-a", "page_b": "concept/topic-b", "description": "conflict"}],
        "coverage_gaps": [{"suggested_title": "New Topic", "suggested_type": "concept", "description": "gap"}],
    })
    monkeypatch.setattr("src.core.memory.get_llm_provider", lambda: StubLLM(stub_response))

    assert mgr._wiki_store.read_health() is None

    await mgr.lint_wiki()

    health = mgr._wiki_store.read_health()
    assert health is not None
    assert health["generated_at"]
    assert health["total_pages"] == 2
    assert len(health["orphans"]) == 2
    assert {o["slug"] for o in health["orphans"]} == {"topic-a", "topic-b"}
    assert health["contradictions"] == [{
        "page_a": {"type": "concept", "slug": "topic-a", "title": "Topic A"},
        "page_b": {"type": "concept", "slug": "topic-b", "title": "Topic B"},
        "description": "conflict",
    }]
    assert health["coverage_gaps"] == [
        {"suggested_title": "New Topic", "suggested_type": "concept", "description": "gap"}
    ]


@pytest.mark.asyncio
async def test_get_long_term_memory_reuses_cache(memory_dir, monkeypatch):
    mgr = MemoryManager(USER_ID)
    await mgr.add_long_term_memory("important_facts", "User's name is Sam.")
    first = await mgr.get_long_term_memory()

    read_calls = []
    original_read_text = Path.read_text

    def spy_read_text(self, *args, **kwargs):
        read_calls.append(self)
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", spy_read_text)

    second = await mgr.get_long_term_memory()
    assert second == first
    assert read_calls == []


@pytest.mark.asyncio
async def test_get_recent_memory_skips_reread_of_unchanged_files(memory_dir, monkeypatch):
    mgr = MemoryManager(USER_ID)
    await mgr.add_interaction("hello", "hi")
    first = await mgr.get_recent_memory(days=7)

    import aiofiles
    open_calls = []
    original_open = aiofiles.open

    def spy_open(*args, **kwargs):
        open_calls.append(args)
        return original_open(*args, **kwargs)

    monkeypatch.setattr(aiofiles, "open", spy_open)

    second = await mgr.get_recent_memory(days=7)
    assert second == first
    assert open_calls == []


@pytest.mark.asyncio
async def test_get_recent_memory_rereads_after_file_changes(memory_dir):
    mgr = MemoryManager(USER_ID)
    await mgr.add_interaction("first message", "reply one")
    first = await mgr.get_recent_memory(days=7)
    assert "first message" in first

    await mgr.add_interaction("second message", "reply two")
    second = await mgr.get_recent_memory(days=7)
    assert "second message" in second
    assert "first message" in second


class StubThinkAgent:
    """Minimal stand-in for a StagedReACTAgent - resolve_contradiction only
    needs agent.think(), unlike consolidate_memories' StubAgent (which only
    needs agent.llm.complete). Records every prompt it's called with so
    tests can assert on wording without a real ReACT tool loop."""

    def __init__(self, response: str = "Fixed it."):
        self.response = response
        self.prompts: list = []

    async def think(self, user_message: str, conversation_history=None):
        self.prompts.append(user_message)
        return self.response


@pytest.mark.asyncio
async def test_resolve_contradiction_prompts_agent_with_context_and_guidance(memory_dir):
    mgr = MemoryManager(USER_ID)
    agent = StubThinkAgent("Updated both pages to say two children.")

    result = await mgr.resolve_contradiction(
        page_a={"type": "concept", "slug": "important-facts", "title": "Important Facts"},
        page_b={"type": "concept", "slug": "relationships", "title": "Relationships"},
        description="Important Facts lists 3 children; Relationships lists 2.",
        guidance="There are only 2 children, Nedal and Rayyan - fix Important Facts.",
        agent=agent,
    )

    assert result == "Updated both pages to say two children."
    assert len(agent.prompts) == 1
    prompt = agent.prompts[0]
    assert "Important Facts (concept/important-facts)" in prompt
    assert "Relationships (concept/relationships)" in prompt
    assert "Important Facts lists 3 children; Relationships lists 2." in prompt
    assert "There are only 2 children, Nedal and Rayyan - fix Important Facts." in prompt


@pytest.mark.asyncio
async def test_resolve_contradiction_falls_back_to_slug_when_title_missing(memory_dir):
    mgr = MemoryManager(USER_ID)
    agent = StubThinkAgent()

    await mgr.resolve_contradiction(
        page_a={"type": "concept", "slug": "topic-a", "title": ""},
        page_b={"type": "concept", "slug": "topic-b", "title": ""},
        description="conflict",
        guidance="pick topic-a",
        agent=agent,
    )

    assert "topic-a (concept/topic-a)" in agent.prompts[0]
    assert "topic-b (concept/topic-b)" in agent.prompts[0]


@pytest.mark.asyncio
async def test_propose_reorganization_empty_wiki_returns_empty_plan(memory_dir):
    mgr = MemoryManager(USER_ID)

    result = await mgr.propose_reorganization()

    assert result == {"target_pages": []}


@pytest.mark.asyncio
async def test_propose_reorganization_retries_once_on_empty_llm_response(memory_dir, monkeypatch):
    """The local LLM backend has been observed to occasionally return an
    empty/unparseable response under load; propose_reorganization should
    recover by retrying the same call once rather than failing outright."""
    mgr = MemoryManager(USER_ID)
    mgr._wiki_store.write_page(type_="concept", slug="topic", title="Topic", summary="s", body="- a")

    valid_response = json.dumps({"target_pages": []})
    monkeypatch.setattr("src.core.memory.get_llm_provider", lambda: StubLLM(["", valid_response]))

    result = await mgr.propose_reorganization()

    assert result == {"target_pages": []}
    assert "error" not in result


@pytest.mark.asyncio
async def test_propose_reorganization_reports_error_after_exhausting_retries(memory_dir, monkeypatch):
    mgr = MemoryManager(USER_ID)
    mgr._wiki_store.write_page(type_="concept", slug="topic", title="Topic", summary="s", body="- a")

    monkeypatch.setattr("src.core.memory.get_llm_provider", lambda: StubLLM(["", ""]))

    result = await mgr.propose_reorganization()

    assert result["target_pages"] == []
    assert "error" in result


@pytest.mark.asyncio
async def test_propose_reorganization_returns_target_pages_with_exists_flag(memory_dir, monkeypatch):
    mgr = MemoryManager(USER_ID)
    mgr._wiki_store.write_page(
        type_="concept", slug="relationships", title="Relationships", summary="s",
        body="- Spouse: Jane.\n- Child: Sam.",
    )
    mgr._wiki_store.write_page(type_="entity", slug="jane", title="Jane", summary="s", body="- Spouse.")

    stub_response = json.dumps({
        "target_pages": [
            {"type": "entity", "slug": "jane", "title": "Jane", "summary": "Spouse.", "source_pages": ["concept/relationships"]},
            {"type": "entity", "slug": "sam", "title": "Sam", "summary": "Child.", "source_pages": ["concept/relationships"]},
        ],
    })
    monkeypatch.setattr("src.core.memory.get_llm_provider", lambda: StubLLM(stub_response))

    result = await mgr.propose_reorganization()

    by_slug = {t["slug"]: t for t in result["target_pages"]}
    assert by_slug["jane"]["already_exists"] is True
    assert by_slug["sam"]["already_exists"] is False
    assert by_slug["sam"]["source_pages"] == ["concept/relationships"]


@pytest.mark.asyncio
async def test_apply_reorganization_empty_plan_returns_message(memory_dir):
    mgr = MemoryManager(USER_ID)

    result = await mgr.apply_reorganization([])

    assert result == "Nothing to reorganize."


@pytest.mark.asyncio
async def test_apply_reorganization_writes_new_pages_and_keeps_sources(memory_dir, monkeypatch):
    mgr = MemoryManager(USER_ID)
    mgr._wiki_store.write_page(
        type_="concept", slug="relationships", title="Relationships", summary="s",
        body="- Spouse: Jane.\n- Child: Sam.",
    )

    edit_response = json.dumps({
        "pages": [
            {"type": "entity", "slug": "jane", "title": "Jane", "summary": "Spouse", "tags": [], "body": "- Spouse: Jane."},
            {"type": "entity", "slug": "sam", "title": "Sam", "summary": "Child", "tags": [], "body": "- Child: Sam."},
        ],
    })
    monkeypatch.setattr("src.core.memory.get_llm_provider", lambda: StubLLM(edit_response))

    result = await mgr.apply_reorganization([
        {"type": "entity", "slug": "jane", "title": "Jane", "summary": "", "source_pages": ["concept/relationships"], "already_exists": False},
        {"type": "entity", "slug": "sam", "title": "Sam", "summary": "", "source_pages": ["concept/relationships"], "already_exists": False},
    ])

    assert "Reorganized into 2 page(s)" in result
    assert mgr._wiki_store.get_page("entity", "jane")["body"] == "- Spouse: Jane."
    assert mgr._wiki_store.get_page("entity", "sam")["body"] == "- Child: Sam."
    # Source page is untouched - reorganization never deletes/edits sources.
    source = mgr._wiki_store.get_page("concept", "relationships")
    assert source is not None
    assert "Spouse: Jane" in source["body"]
    assert "Child: Sam" in source["body"]


@pytest.mark.asyncio
async def test_apply_reorganization_rejects_suspicious_shrink_on_existing_page(memory_dir, monkeypatch):
    mgr = MemoryManager(USER_ID)
    long_body = "\n".join(f"- Detail line {i} with enough content to matter." for i in range(10))
    mgr._wiki_store.write_page(type_="entity", slug="jane", title="Jane", summary="s", body=long_body)

    edit_response = json.dumps({
        "pages": [{"type": "entity", "slug": "jane", "title": "Jane", "summary": "s", "tags": [], "body": "- one line"}],
    })
    monkeypatch.setattr("src.core.memory.get_llm_provider", lambda: StubLLM(edit_response))

    result = await mgr.apply_reorganization([
        {"type": "entity", "slug": "jane", "title": "Jane", "summary": "", "source_pages": [], "already_exists": True},
    ])

    assert result == "No pages were created."
    assert mgr._wiki_store.get_page("entity", "jane")["body"] == long_body
