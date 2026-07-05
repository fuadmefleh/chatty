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


@pytest.fixture
def memory_dir(tmp_path, monkeypatch):
    """Point config.MEMORY_DIR at an isolated tmp directory for this test."""
    monkeypatch.setattr(config, "MEMORY_DIR", tmp_path)
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
async def test_add_long_term_memory_append_format(memory_dir):
    mgr = MemoryManager(USER_ID)
    await mgr.add_long_term_memory("important_facts", "User's name is Sam.")
    await mgr.add_long_term_memory("important_facts", "User was born in June.")

    content = (mgr.long_term_dir / "important_facts.md").read_text()
    assert "# Long-Term Memory: important_facts" in content
    assert "User's name is Sam." in content
    assert "## Updated:" in content
    assert "User was born in June." in content


@pytest.mark.asyncio
async def test_save_important_fact_delegates_to_add_long_term_memory(memory_dir):
    """save_important_fact should write in the same format as
    MemoryManager.add_long_term_memory (single write path, no duplicated
    file I/O with a divergent header format)."""
    tools = MemoryTools(USER_ID)
    result = await tools.save_important_fact("facts", "User's favorite color is blue.")
    assert "Successfully saved" in result

    # Second call appends via the same MemoryManager.add_long_term_memory
    # path, producing the "## Updated:" format instead of a divergent one.
    result = await tools.save_important_fact("facts", "User's favorite food is sushi.")
    assert "Successfully saved" in result

    content = (tools.long_term_dir / "important_facts.md").read_text()
    assert "# Long-Term Memory: important_facts" in content
    assert "## Updated:" in content
    assert "User's favorite color is blue." in content
    assert "User's favorite food is sushi." in content


@pytest.mark.asyncio
async def test_save_important_fact_category_mapping(memory_dir):
    tools = MemoryTools(USER_ID)
    await tools.save_important_fact("family", "Has a sister named Jane.")

    assert (tools.long_term_dir / "relationships.md").exists()


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
    long_term_content = (mgr.long_term_dir / "important_facts.md").read_text()
    assert "June 1st" in long_term_content


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
