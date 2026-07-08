"""Tests for MemoryRouter (src/core/memory_router.py) - the 4-tool
recall/remember/forget/browse_wiki LLM-facing memory surface, backed by the
wiki store (src/core/wiki_store.py). Index-first: no embeddings involved."""
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


@pytest.mark.asyncio
async def test_recall_ranks_pages_by_keyword_match(memory_dir):
    router = MemoryRouter(USER_ID)
    await router.remember("User likes sushi and other Japanese food.", category="food")
    await router.remember("User dislikes cold weather.", category="weather")

    result = await router.recall("food")

    assert "sushi" in result
    assert "cold weather" not in result


@pytest.mark.asyncio
async def test_recall_falls_back_to_fulltext_when_no_keyword_hits(memory_dir):
    router = MemoryRouter(USER_ID)
    wiki_store = router.memory_tools._wiki_store
    wiki_store.write_page(
        type_="entity", slug="sarah", title="Sarah", summary="User's sister.",
        body="- Lives in Austin, TX.",
    )

    # "Austin" appears only in the page body, not its title/summary/tags -
    # keyword scoring alone finds nothing, so this exercises the small-wiki
    # full-text fallback.
    result = await router.recall("Austin")

    assert "Austin" in result


@pytest.mark.asyncio
async def test_recall_includes_short_term_excerpts(memory_dir):
    from src.core.memory import MemoryManager

    mgr = MemoryManager(USER_ID)
    await mgr.add_interaction("I just adopted a cat named Whiskers", "That's wonderful!")

    router = MemoryRouter(USER_ID)
    result = await router.recall("Whiskers")

    assert "Whiskers" in result


@pytest.mark.asyncio
async def test_recall_empty_when_nothing_found(memory_dir):
    router = MemoryRouter(USER_ID)

    result = await router.recall("something that was never mentioned")

    assert "No memory found" in result


@pytest.mark.asyncio
async def test_remember_defaults_to_important_facts(memory_dir):
    router = MemoryRouter(USER_ID)
    await router.remember("User's name is Sam.")

    page = router.memory_tools._wiki_store.get_page("concept", "important-facts")
    assert page is not None
    assert "User's name is Sam." in page["body"]


@pytest.mark.asyncio
async def test_remember_passes_through_arbitrary_category(memory_dir):
    router = MemoryRouter(USER_ID)
    await router.remember("Plays guitar.", category="hobbies")

    page = router.memory_tools._wiki_store.get_page("concept", "hobbies")
    assert page is not None
    assert "Plays guitar." in page["body"]


@pytest.mark.asyncio
async def test_forget_auto_deletes_single_match(memory_dir):
    router = MemoryRouter(USER_ID)
    await router.remember("User likes sushi.")

    result = await router.forget("sushi")

    assert "Forgot" in result
    assert router.memory_tools._wiki_store.get_page("concept", "important-facts") is None


@pytest.mark.asyncio
async def test_forget_multiple_matches_suggests_calling_forget_again(memory_dir):
    router = MemoryRouter(USER_ID)
    await router.remember("User likes sushi.")
    await router.remember("User's coworker also likes sushi.")

    result = await router.forget("sushi")

    assert "Found 2 matching facts" in result
    assert "delete_fact_by_id" not in result
    assert "Call forget again" in result
    # nothing deleted yet - ambiguous
    page = router.memory_tools._wiki_store.get_page("concept", "important-facts")
    assert page is not None
    assert page["body"].count("sushi") == 2


@pytest.mark.asyncio
async def test_forget_no_match(memory_dir):
    router = MemoryRouter(USER_ID)

    result = await router.forget("nonexistent topic")

    assert "No matching" in result


@pytest.mark.asyncio
async def test_browse_wiki_returns_index_catalog(memory_dir):
    router = MemoryRouter(USER_ID)
    await router.remember("Plays guitar.", category="hobbies")

    result = await router.browse_wiki()

    assert "Hobbies" in result


@pytest.mark.asyncio
async def test_browse_wiki_empty_wiki_message(memory_dir):
    router = MemoryRouter(USER_ID)

    result = await router.browse_wiki()

    assert "empty" in result.lower()


@pytest.mark.asyncio
async def test_recall_includes_backlinks_when_present(memory_dir):
    router = MemoryRouter(USER_ID)
    wiki_store = router.memory_tools._wiki_store
    wiki_store.write_page(type_="entity", slug="sarah", title="Sarah", summary="User's sister.", body="- Lives in Austin.")
    wiki_store.write_page(
        type_="concept", slug="family-trip", title="Family Trip", summary="A recent trip.",
        body="- Went hiking with [Sarah](pages/entities/sarah.md).",
    )

    result = await router.recall("Sarah")

    assert "_Related: Family Trip" in result


def test_get_tool_definitions_returns_exactly_four_schemas():
    tool_defs = get_tool_definitions()
    names = {t["function"]["name"] for t in tool_defs}
    assert names == {"recall", "remember", "forget", "browse_wiki"}

    by_name = {t["function"]["name"]: t for t in tool_defs}
    assert by_name["recall"]["function"]["parameters"]["required"] == ["query"]
    assert by_name["remember"]["function"]["parameters"]["required"] == ["content"]
    assert by_name["forget"]["function"]["parameters"]["required"] == ["query"]
    assert by_name["browse_wiki"]["function"]["parameters"]["required"] == []
