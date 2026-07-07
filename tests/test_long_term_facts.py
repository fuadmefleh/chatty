"""Tests for LongTermFactsStore (src/core/long_term_facts.py) and the
embedding-attachment path in MemoryManager.add_long_term_memory."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import config
from src.core.memory import MemoryManager
from src.core.long_term_facts import LongTermFactsStore

USER_ID = "test_user"


@pytest.fixture
def memory_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MEMORY_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def store(memory_dir):
    long_term_dir = memory_dir / USER_ID / "long_term"
    return LongTermFactsStore(USER_ID, long_term_dir)


@pytest.mark.asyncio
async def test_add_fact_stores_embedding(memory_dir, monkeypatch):
    async def fake_get_embedding(text: str):
        return [1.0, 0.0, 0.0]

    monkeypatch.setattr("src.core.embeddings.get_embedding", fake_get_embedding)

    mgr = MemoryManager(USER_ID)
    await mgr.add_long_term_memory("important_facts", "User likes hiking.")

    facts = mgr._facts_store.list_facts(category="important_facts")
    assert len(facts) == 1
    assert facts[0]["embedding"] == [1.0, 0.0, 0.0]


@pytest.mark.asyncio
async def test_add_fact_survives_embedding_failure(memory_dir, monkeypatch):
    async def failing_get_embedding(text: str):
        raise RuntimeError("network error")

    monkeypatch.setattr("src.core.embeddings.get_embedding", failing_get_embedding)

    mgr = MemoryManager(USER_ID)
    await mgr.add_long_term_memory("important_facts", "User likes hiking.")

    facts = mgr._facts_store.list_facts(category="important_facts")
    assert len(facts) == 1
    assert facts[0]["embedding"] is None


def test_semantic_search_ranks_by_similarity(store):
    close = store.add_fact("important_facts", "User likes hiking.")
    far = store.add_fact("important_facts", "User dislikes hiking.")
    store.update_fact_embedding(close["id"], [1.0, 0.0, 0.0])
    store.update_fact_embedding(far["id"], [0.0, 1.0, 0.0])

    results = store.semantic_search([1.0, 0.0, 0.0], top_k=2)

    assert len(results) == 2
    top_fact, top_score = results[0]
    assert top_fact["id"] == close["id"]
    assert top_score > results[1][1]


def test_semantic_search_skips_facts_without_embeddings(store):
    embedded = store.add_fact("important_facts", "User likes hiking.")
    store.update_fact_embedding(embedded["id"], [1.0, 0.0, 0.0])
    store.add_fact("important_facts", "User has no embedding yet.")  # embedding stays None

    results = store.semantic_search([1.0, 0.0, 0.0], top_k=5)

    assert len(results) == 1
    assert results[0][0]["id"] == embedded["id"]


def test_semantic_search_empty_store_returns_nothing(store):
    assert store.semantic_search([1.0, 0.0, 0.0]) == []
