"""Tests for the memory system: MemoryManager (src/core/memory.py) and
MemoryTools (src/core/memory_tools.py)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import config
from src.core.memory import MemoryManager
from src.core.memory_tools import MemoryTools

USER_ID = "test_user"

FAKE_EMBEDDING = [0.1, 0.2, 0.3]


@pytest.fixture
def memory_dir(tmp_path, monkeypatch):
    """Point config.MEMORY_DIR at an isolated tmp directory for this test,
    and stub out embedding generation so add_long_term_memory() (called by
    most tests here) never makes a live OpenAI API call."""
    monkeypatch.setattr(config, "MEMORY_DIR", tmp_path)

    async def _fake_get_embedding(text: str):
        return FAKE_EMBEDDING

    monkeypatch.setattr("src.core.embeddings.get_embedding", _fake_get_embedding)
    return tmp_path


class StubAgent:
    """Minimal stand-in for a ReACTAgent - only needs an async think()."""

    def __init__(self, response: str):
        self._response = response

    async def think(self, prompt: str, history) -> str:
        return self._response


@pytest.mark.asyncio
async def test_add_interaction_and_get_recent_memory(memory_dir):
    mgr = MemoryManager(USER_ID)
    await mgr.add_interaction("hello there", "hi, how can I help?")

    recent = await mgr.get_recent_memory(days=7)
    assert "hello there" in recent
    assert "hi, how can I help?" in recent


@pytest.mark.asyncio
async def test_add_long_term_memory_creates_fact_records(memory_dir):
    mgr = MemoryManager(USER_ID)
    await mgr.add_long_term_memory("important_facts", "User's name is Sam.")
    await mgr.add_long_term_memory("important_facts", "User was born in June.")

    facts = mgr._facts_store.list_facts(category="important_facts")
    assert len(facts) == 2
    contents = [f["content"] for f in facts]
    assert "User's name is Sam." in contents
    assert "User was born in June." in contents
    assert len({f["id"] for f in facts}) == 2  # distinct ids


@pytest.mark.asyncio
async def test_save_important_fact_delegates_to_add_long_term_memory(memory_dir):
    """save_important_fact should write via the same MemoryManager path as
    add_long_term_memory (single write path, no duplicated storage)."""
    tools = MemoryTools(USER_ID)
    result = await tools.save_important_fact("facts", "User's favorite color is blue.")
    assert "Successfully saved" in result

    result = await tools.save_important_fact("facts", "User's favorite food is sushi.")
    assert "Successfully saved" in result

    facts = tools._facts_store.list_facts(category="important_facts")
    contents = [f["content"] for f in facts]
    assert "User's favorite color is blue." in contents
    assert "User's favorite food is sushi." in contents


@pytest.mark.asyncio
async def test_save_important_fact_category_mapping(memory_dir):
    tools = MemoryTools(USER_ID)
    await tools.save_important_fact("family", "Has a sister named Jane.")

    facts = tools._facts_store.list_facts(category="relationships")
    assert len(facts) == 1
    assert facts[0]["content"] == "Has a sister named Jane."


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

    stub_response = "CATEGORY: Important Facts\nCONTENT: User's birthday is June 1st."
    result = await mgr.consolidate_memories(StubAgent(stub_response))

    assert "Successfully consolidated" in result
    assert not old_file.exists()
    assert (mgr.short_term_dir / "archived" / "2020-01-01.md").exists()
    facts = mgr._facts_store.list_facts(category="important_facts")
    assert any("June 1st" in f["content"] for f in facts)


@pytest.mark.asyncio
async def test_read_memory_file_rejects_path_traversal(memory_dir):
    tools = MemoryTools(USER_ID)
    tools.short_term_dir.mkdir(parents=True, exist_ok=True)
    (tools.short_term_dir / "2026-01-01.md").write_text("legit content")

    # Escapes short_term_dir via ../ - should not read files outside it.
    result = await tools.read_memory_file("../../etc/passwd", "short_term")
    assert "not found" in result.lower()

    # Absolute path should also be rejected, not read from the filesystem root.
    result = await tools.read_memory_file("/etc/passwd", "short_term")
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_read_memory_file_reads_legitimate_file(memory_dir):
    tools = MemoryTools(USER_ID)
    tools.short_term_dir.mkdir(parents=True, exist_ok=True)
    (tools.short_term_dir / "2026-01-01.md").write_text("legit content")

    result = await tools.read_memory_file("2026-01-01.md", "short_term")
    assert result == "legit content"


@pytest.mark.asyncio
async def test_dedupe_facts_removes_near_duplicate_and_keeps_newer(memory_dir):
    mgr = MemoryManager(USER_ID)
    await mgr.add_long_term_memory("important_facts", "User's favorite color is blue.")
    await mgr.add_long_term_memory("important_facts", "User's favorite color is blue!")  # near-duplicate

    result = await mgr.dedupe_facts()

    assert "Removed 1" in result
    remaining = mgr._facts_store.list_facts(category="important_facts")
    assert len(remaining) == 1
    assert remaining[0]["content"] == "User's favorite color is blue!"  # the newer one survives


@pytest.mark.asyncio
async def test_dedupe_facts_keeps_dissimilar_facts(memory_dir):
    mgr = MemoryManager(USER_ID)
    await mgr.add_long_term_memory("important_facts", "User's name is Sam.")
    await mgr.add_long_term_memory("important_facts", "User lives in Seattle.")

    result = await mgr.dedupe_facts()

    assert "Removed 0" in result
    remaining = mgr._facts_store.list_facts(category="important_facts")
    assert len(remaining) == 2


@pytest.mark.asyncio
async def test_get_long_term_memory_no_truncation_by_default(memory_dir):
    mgr = MemoryManager(USER_ID)
    long_content = "x" * 5000
    await mgr.add_long_term_memory("important_facts", long_content)

    result = await mgr.get_long_term_memory()
    assert long_content in result


@pytest.mark.asyncio
async def test_get_long_term_memory_fair_budget_across_categories(memory_dir):
    mgr = MemoryManager(USER_ID)
    # relationships.md sorts first (reverse-alphabetical) and is made large
    # enough that a naive "truncate the joined blob" approach would starve
    # important_facts.md out entirely.
    await mgr.add_long_term_memory("relationships", "R" * 2000)
    await mgr.add_long_term_memory("important_facts", "IMPORTANT_MARKER")

    result = await mgr.get_long_term_memory(max_chars=1000)
    # The core regression check: under the OLD behavior (truncate the
    # concatenated, reverse-alpha-sorted blob to 1000 chars) this would fail,
    # since "relationships" content alone consumes the whole budget.
    assert "IMPORTANT_MARKER" in result


@pytest.mark.asyncio
async def test_legacy_markdown_migrates_to_facts_json(memory_dir):
    from src.core.long_term_facts import LongTermFactsStore

    long_term_dir = memory_dir / USER_ID / "long_term"
    long_term_dir.mkdir(parents=True)
    (long_term_dir / "important_facts.md").write_text(
        "# Long-Term Memory: important_facts\n\n"
        "Created: 2026-01-01 10:00:00\n\n"
        "User's name is Sam.\n"
        "\n\n## Updated: 2026-01-02 10:00:00\n\n"
        "User was born in June.\n"
    )

    store = LongTermFactsStore(USER_ID, long_term_dir)

    facts = store.list_facts(category="important_facts")
    contents = [f["content"] for f in facts]
    assert "User's name is Sam." in contents
    assert "User was born in June." in contents
    assert (long_term_dir / "important_facts.md.bak").exists()
    assert not (long_term_dir / "important_facts.md").exists()
    assert (long_term_dir / "facts.json").exists()


@pytest.mark.asyncio
async def test_forget_fact_auto_deletes_single_match(memory_dir):
    tools = MemoryTools(USER_ID)
    await tools.save_important_fact("facts", "User likes sushi.")

    result = await tools.forget_fact("sushi")

    assert "Forgot" in result
    assert tools._facts_store.list_facts(category="important_facts") == []


@pytest.mark.asyncio
async def test_forget_fact_lists_candidates_on_multiple_matches(memory_dir):
    tools = MemoryTools(USER_ID)
    await tools.save_important_fact("facts", "User likes sushi.")
    await tools.save_important_fact("facts", "User's coworker also likes sushi.")

    result = await tools.forget_fact("sushi")

    assert "Found 2 matching facts" in result
    remaining = tools._facts_store.list_facts(category="important_facts")
    assert len(remaining) == 2  # nothing deleted yet - ambiguous

    # Follow-up: parse an id out of the disambiguation text and delete it.
    fact_id = remaining[0]["id"]
    delete_result = await tools.delete_fact_by_id(fact_id)
    assert "Forgot" in delete_result
    assert len(tools._facts_store.list_facts(category="important_facts")) == 1


@pytest.mark.asyncio
async def test_forget_fact_no_match(memory_dir):
    tools = MemoryTools(USER_ID)
    result = await tools.forget_fact("nonexistent topic")
    assert "No matching" in result


@pytest.mark.asyncio
async def test_delete_fact_by_id_unknown_id(memory_dir):
    tools = MemoryTools(USER_ID)
    result = await tools.delete_fact_by_id("not-a-real-id")
    assert "No fact found" in result
