"""Tests for MemoryRouter (src/core/memory_router.py) - the 3-tool
recall/remember/forget LLM-facing memory surface."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import config
from src.core.memory_router import MemoryRouter, get_tool_definitions

USER_ID = "test_user_router"


@pytest.fixture
def memory_dir(tmp_path, monkeypatch):
    """Point config.MEMORY_DIR at an isolated tmp directory for this test."""
    monkeypatch.setattr(config, "MEMORY_DIR", tmp_path)
    return tmp_path


def _stub_embedding(monkeypatch, vector):
    async def _fake_get_embedding(text: str):
        return vector

    monkeypatch.setattr("src.core.embeddings.get_embedding", _fake_get_embedding)


def _stub_embedding_failure(monkeypatch):
    async def _fake_get_embedding(text: str):
        raise RuntimeError("no API key")

    monkeypatch.setattr("src.core.embeddings.get_embedding", _fake_get_embedding)


@pytest.mark.asyncio
async def test_recall_ranks_semantic_hits_by_similarity(memory_dir, monkeypatch):
    router = MemoryRouter(USER_ID)

    # Store two facts with distinct embeddings, then query with an embedding
    # closer to one of them.
    _stub_embedding(monkeypatch, [1.0, 0.0])
    await router.remember("User likes sushi.", category="important_facts")
    _stub_embedding(monkeypatch, [0.0, 1.0])
    await router.remember("User dislikes cold weather.", category="important_facts")

    _stub_embedding(monkeypatch, [1.0, 0.0])
    result = await router.recall("food preferences")

    lines = result.split("\n")
    assert "sushi" in lines[1]


@pytest.mark.asyncio
async def test_recall_falls_back_to_substring_search_on_embedding_failure(memory_dir, monkeypatch):
    router = MemoryRouter(USER_ID)

    _stub_embedding(monkeypatch, [1.0, 0.0])
    await router.remember("User's favorite color is blue.")

    _stub_embedding_failure(monkeypatch)
    result = await router.recall("favorite color")

    assert "favorite color" in result


@pytest.mark.asyncio
async def test_recall_includes_short_term_excerpts(memory_dir, monkeypatch):
    from src.core.memory import MemoryManager

    mgr = MemoryManager(USER_ID)
    await mgr.add_interaction("I just adopted a cat named Whiskers", "That's wonderful!")

    _stub_embedding_failure(monkeypatch)  # no long-term facts, and no embedding needed
    router = MemoryRouter(USER_ID)
    result = await router.recall("Whiskers")

    assert "Whiskers" in result


@pytest.mark.asyncio
async def test_recall_empty_when_nothing_found(memory_dir, monkeypatch):
    _stub_embedding_failure(monkeypatch)
    router = MemoryRouter(USER_ID)

    result = await router.recall("something that was never mentioned")

    assert "No memory found" in result


@pytest.mark.asyncio
async def test_remember_defaults_to_important_facts(memory_dir, monkeypatch):
    _stub_embedding_failure(monkeypatch)
    router = MemoryRouter(USER_ID)

    await router.remember("User's name is Sam.")

    facts = router.memory_tools._facts_store.list_facts(category="important_facts")
    assert any(f["content"] == "User's name is Sam." for f in facts)


@pytest.mark.asyncio
async def test_remember_passes_through_arbitrary_category(memory_dir, monkeypatch):
    _stub_embedding_failure(monkeypatch)
    router = MemoryRouter(USER_ID)

    await router.remember("Plays guitar.", category="hobbies")

    facts = router.memory_tools._facts_store.list_facts(category="hobbies")
    assert any(f["content"] == "Plays guitar." for f in facts)


@pytest.mark.asyncio
async def test_forget_auto_deletes_single_match(memory_dir, monkeypatch):
    _stub_embedding_failure(monkeypatch)
    router = MemoryRouter(USER_ID)
    await router.remember("User likes sushi.")

    result = await router.forget("sushi")

    assert "Forgot" in result
    assert router.memory_tools._facts_store.list_facts(category="important_facts") == []


@pytest.mark.asyncio
async def test_forget_multiple_matches_suggests_calling_forget_again(memory_dir, monkeypatch):
    _stub_embedding_failure(monkeypatch)
    router = MemoryRouter(USER_ID)
    await router.remember("User likes sushi.")
    await router.remember("User's coworker also likes sushi.")

    result = await router.forget("sushi")

    assert "Found 2 matching facts" in result
    assert "delete_fact_by_id" not in result
    assert "Call forget again" in result
    # nothing deleted yet - ambiguous
    assert len(router.memory_tools._facts_store.list_facts(category="important_facts")) == 2


@pytest.mark.asyncio
async def test_forget_no_match(memory_dir, monkeypatch):
    _stub_embedding_failure(monkeypatch)
    router = MemoryRouter(USER_ID)

    result = await router.forget("nonexistent topic")

    assert "No matching" in result


def test_get_tool_definitions_returns_exactly_three_schemas():
    tool_defs = get_tool_definitions()
    names = {t["function"]["name"] for t in tool_defs}
    assert names == {"recall", "remember", "forget"}

    by_name = {t["function"]["name"]: t for t in tool_defs}
    assert by_name["recall"]["function"]["parameters"]["required"] == ["query"]
    assert by_name["remember"]["function"]["parameters"]["required"] == ["content"]
    assert by_name["forget"]["function"]["parameters"]["required"] == ["query"]
