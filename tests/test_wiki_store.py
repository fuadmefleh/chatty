"""Tests for WikiStore (src/core/wiki_store.py) - the Karpathy-style
markdown wiki that replaced the flat facts.json long-term memory store."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.wiki_store import WikiStore

USER_ID = "test_wiki_user"


@pytest.fixture
def long_term_dir(tmp_path):
    return tmp_path / "long_term"


def test_write_page_creates_and_reads_back(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(
        type_="entity", slug="sarah", title="Sarah (sister)",
        summary="User's younger sister.", body="- Lives in Austin.",
        tags=["family"],
    )

    page = store.get_page("entity", "sarah")
    assert page is not None
    assert page["title"] == "Sarah (sister)"
    assert page["summary"] == "User's younger sister."
    assert page["tags"] == ["family"]
    assert "Lives in Austin" in page["body"]


def test_write_page_preserves_created_on_update(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(type_="concept", slug="budgeting", title="Budgeting", summary="s1", body="- a")
    first = store.get_page("concept", "budgeting")

    store.write_page(type_="concept", slug="budgeting", title="Budgeting", summary="s2", body="- a\n- b")
    second = store.get_page("concept", "budgeting")

    assert second["created"] == first["created"]
    assert second["updated"] != first["created"] or second["summary"] == "s2"
    assert second["summary"] == "s2"
    assert "- b" in second["body"]


def test_append_section_creates_page_if_missing(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.append_section(type_="concept", slug="hobbies", content="- Plays guitar.", title_hint="Hobbies")

    page = store.get_page("concept", "hobbies")
    assert page is not None
    assert page["title"] == "Hobbies"
    assert "Plays guitar." in page["body"]


def test_append_section_appends_to_existing_page(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.append_section(type_="concept", slug="hobbies", content="- Plays guitar.", title_hint="Hobbies")
    store.append_section(type_="concept", slug="hobbies", content="- Also enjoys hiking.")

    page = store.get_page("concept", "hobbies")
    assert "Plays guitar." in page["body"]
    assert "Also enjoys hiking." in page["body"]


def test_list_pages_filters_by_type(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(type_="entity", slug="sarah", title="Sarah", summary="s", body="- a")
    store.write_page(type_="concept", slug="budgeting", title="Budgeting", summary="s", body="- a")

    entities = store.list_pages(type="entity")
    concepts = store.list_pages(type="concept")

    assert [p["slug"] for p in entities] == ["sarah"]
    assert [p["slug"] for p in concepts] == ["budgeting"]
    assert len(store.list_pages()) == 2


def test_delete_page(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(type_="concept", slug="budgeting", title="Budgeting", summary="s", body="- a")

    deleted = store.delete_page("concept", "budgeting")
    assert deleted is not None
    assert store.get_page("concept", "budgeting") is None


def test_delete_line_removes_one_line_keeps_page(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(type_="concept", slug="budgeting", title="Budgeting", summary="s",
                      body="- Monthly budget is $2000\n- Saves 10% of income")

    result = store.delete_line("concept", "budgeting", "- Monthly budget is $2000")

    assert result is True
    page = store.get_page("concept", "budgeting")
    assert "Monthly budget is $2000" not in page["body"]
    assert "Saves 10% of income" in page["body"]


def test_delete_line_removes_whole_page_when_body_empties(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(type_="concept", slug="budgeting", title="Budgeting", summary="s",
                      body="- Monthly budget is $2000")

    result = store.delete_line("concept", "budgeting", "- Monthly budget is $2000")

    assert result is True
    assert store.get_page("concept", "budgeting") is None


def test_delete_line_no_match_returns_false(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(type_="concept", slug="budgeting", title="Budgeting", summary="s", body="- a")

    assert store.delete_line("concept", "budgeting", "- nonexistent line") is False
    assert store.delete_line("concept", "nonexistent-slug", "- a") is False


def test_find_matches_across_pages(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(type_="concept", slug="food", title="Food", summary="s", body="- Likes sushi.")
    store.write_page(type_="entity", slug="coworker", title="Coworker", summary="s", body="- Also likes sushi.")

    matches = store.find_matches("sushi")

    assert len(matches) == 2
    titles = {m["title"] for m in matches}
    assert titles == {"Food", "Coworker"}


def test_search_index_ranks_title_match_highest(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(type_="concept", slug="budgeting", title="Budgeting", summary="Tracks monthly spend.", body="- a")
    store.write_page(type_="concept", slug="unrelated", title="Unrelated", summary="Nothing to do with money.", body="- b")

    results = store.search_index("budgeting")

    assert results
    assert results[0]["slug"] == "budgeting"


def test_search_index_no_terms_returns_empty(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(type_="concept", slug="budgeting", title="Budgeting", summary="s", body="- a")

    assert store.search_index("   ") == []


def test_search_pages_fulltext(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(type_="entity", slug="sarah", title="Sarah", summary="s", body="- Lives in Austin, TX.")

    results = store.search_pages_fulltext("Austin")

    assert len(results) == 1
    assert results[0]["slug"] == "sarah"


def test_rebuild_index_reflects_all_pages(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(type_="entity", slug="sarah", title="Sarah (sister)", summary="A sister.", body="- a", tags=["family"])
    store.write_page(type_="concept", slug="budgeting", title="Budgeting", summary="Tracks spend.", body="- a")

    index_text = store.read_index()

    assert "Sarah (sister)" in index_text
    assert "pages/entities/sarah.md" in index_text
    assert "Budgeting" in index_text
    assert "pages/concepts/budgeting.md" in index_text
    assert "family" in index_text


def test_log_append_format(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.append_log("remember", "Budgeting — appended fact via remember()")

    log_text = store.read_log()

    assert "remember" in log_text
    assert "Budgeting" in log_text
    assert log_text.startswith("## [")


def test_find_duplicate_pages_above_threshold(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(type_="concept", slug="budgeting", title="Budgeting", summary="Tracks monthly spending goals.", body="- a")
    store.write_page(type_="concept", slug="budget", title="Budget", summary="Tracks monthly spending goals!", body="- b")

    pairs = store.find_duplicate_pages(threshold=0.9)

    assert len(pairs) == 1


def test_find_duplicate_pages_keeps_dissimilar_pages(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(type_="concept", slug="budgeting", title="Budgeting", summary="Tracks monthly spend.", body="- a")
    store.write_page(type_="entity", slug="sarah", title="Sarah", summary="A sister.", body="- b")

    assert store.find_duplicate_pages(threshold=0.9) == []


def test_merge_pages_folds_body_and_deletes_old(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    keep = store.write_page(type_="concept", slug="budgeting", title="Budgeting", summary="s", body="- Monthly budget $2000")
    remove = store.write_page(type_="concept", slug="budget", title="Budget", summary="s", body="- Saves 10%")

    store.merge_pages(keep, remove)

    merged = store.get_page("concept", "budgeting")
    assert "Monthly budget $2000" in merged["body"]
    assert "Saves 10%" in merged["body"]
    assert "Merged from Budget" in merged["body"]
    assert store.get_page("concept", "budget") is None


def test_redirect_links_rewrites_other_pages_after_merge(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    keep = store.write_page(type_="concept", slug="budgeting", title="Budgeting", summary="s", body="- Monthly budget $2000")
    remove = store.write_page(type_="concept", slug="budget", title="Budget", summary="s", body="- Saves 10%")
    store.write_page(
        type_="concept", slug="family-trip", title="Family Trip", summary="s",
        body="- Paid for with the [Budget](pages/concepts/budget.md).",
    )

    store.merge_pages(keep, remove)
    fixed = store.redirect_links("concept", "budget", "concept", "budgeting")

    assert fixed == 1
    trip = store.get_page("concept", "family-trip")
    assert "[Budget](pages/concepts/budgeting.md)" in trip["body"]
    assert "pages/concepts/budget.md" not in trip["body"]


def test_fix_missing_cross_references_links_bare_mentions(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(type_="entity", slug="sarah", title="Sarah", summary="s", body="- Sister.")
    store.write_page(type_="concept", slug="family-trip", title="Family Trip", summary="s",
                      body="- Went hiking with Sarah last month.")

    fixed = store.fix_missing_cross_references()

    assert fixed == 1
    page = store.get_page("concept", "family-trip")
    assert "[Sarah](pages/entities/sarah.md)" in page["body"]


def test_find_orphan_pages(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(type_="entity", slug="sarah", title="Sarah", summary="s", body="- Sister.")
    store.write_page(type_="concept", slug="family-trip", title="Family Trip", summary="s",
                      body="- Went hiking with [Sarah](pages/entities/sarah.md).")
    store.write_page(type_="concept", slug="isolated", title="Isolated Topic", summary="s", body="- Nothing links here.")

    orphans = store.find_orphan_pages()
    orphan_slugs = {p["slug"] for p in orphans}

    # "sarah" is linked-to from family-trip's body, so it's not an orphan.
    # "family-trip" links out but nothing links to it, so it IS an orphan.
    # "isolated" has no links either way, so it IS an orphan.
    assert "sarah" not in orphan_slugs
    assert "family-trip" in orphan_slugs
    assert "isolated" in orphan_slugs


def test_get_backlinks_returns_pages_linking_to_target(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(type_="entity", slug="sarah", title="Sarah", summary="s", body="- Sister.")
    store.write_page(type_="concept", slug="family-trip", title="Family Trip", summary="s",
                      body="- Went hiking with [Sarah](pages/entities/sarah.md).")

    backlinks = store.get_backlinks("entity", "sarah")

    assert len(backlinks) == 1
    assert backlinks[0]["slug"] == "family-trip"
    assert backlinks[0]["type"] == "concept"


def test_get_backlinks_empty_when_no_inbound_links(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(type_="concept", slug="isolated", title="Isolated Topic", summary="s", body="- Nothing links here.")

    assert store.get_backlinks("concept", "isolated") == []


def test_get_backlinks_deduplicates_multiple_links_from_same_page(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(type_="entity", slug="sarah", title="Sarah", summary="s", body="- Sister.")
    store.write_page(
        type_="concept", slug="family-trip", title="Family Trip", summary="s",
        body="- Went hiking with [Sarah](pages/entities/sarah.md).\n- Called [Sarah](pages/entities/sarah.md) after.",
    )

    backlinks = store.get_backlinks("entity", "sarah")

    assert len(backlinks) == 1
    assert backlinks[0]["slug"] == "family-trip"


def test_read_health_returns_none_when_never_written(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    assert store.read_health() is None


def test_write_health_then_read_health_roundtrips(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    data = {
        "generated_at": "2026-01-01T00:00:00",
        "total_pages": 3,
        "auto_fixed": {"cross_references_added": 1, "duplicates_merged": 0},
        "orphans": [{"type": "concept", "slug": "isolated", "title": "Isolated Topic"}],
        "contradictions": [],
        "coverage_gaps": [],
    }

    store.write_health(data)

    assert store.read_health() == data


def test_migration_from_legacy_facts_json(long_term_dir):
    long_term_dir.mkdir(parents=True)
    facts = [
        {"id": "id-1", "category": "important_facts", "content": "User's name is Sam.",
         "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00", "embedding": None},
        {"id": "id-2", "category": "important_facts", "content": "User was born in June.",
         "created_at": "2026-01-02T00:00:00", "updated_at": "2026-01-02T00:00:00", "embedding": None},
        {"id": "id-3", "category": "relationships", "content": "Has a sister named Jane.",
         "created_at": "2026-01-03T00:00:00", "updated_at": "2026-01-03T00:00:00", "embedding": None},
    ]
    (long_term_dir / "facts.json").write_text(json.dumps(facts), encoding="utf-8")

    store = WikiStore(USER_ID, long_term_dir)

    important_facts_page = store.get_page("concept", "important-facts")
    assert important_facts_page is not None
    assert "User's name is Sam." in important_facts_page["body"]
    assert "User was born in June." in important_facts_page["body"]
    assert set(important_facts_page["source_ids"]) == {"id-1", "id-2"}

    relationships_page = store.get_page("concept", "relationships")
    assert relationships_page is not None
    assert "Has a sister named Jane." in relationships_page["body"]

    assert (long_term_dir / "facts.json.bak").exists()
    assert not (long_term_dir / "facts.json").exists()

    log_text = store.read_log()
    assert "migrate" in log_text


def test_migration_is_idempotent(long_term_dir):
    long_term_dir.mkdir(parents=True)
    facts = [{"id": "id-1", "category": "important_facts", "content": "User's name is Sam.",
              "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00", "embedding": None}]
    (long_term_dir / "facts.json").write_text(json.dumps(facts), encoding="utf-8")

    WikiStore(USER_ID, long_term_dir)
    # Re-constructing should not re-migrate or duplicate content, since
    # facts.json is already renamed away and pages already exist.
    store2 = WikiStore(USER_ID, long_term_dir)

    page = store2.get_page("concept", "important-facts")
    assert page["body"].count("User's name is Sam.") == 1


def test_no_pages_yet_recall_friendly_index(long_term_dir):
    store = WikiStore(USER_ID, long_term_dir)
    assert "No pages yet" in store.read_index()
    assert store.list_pages() == []


def test_write_page_uses_file_lock(long_term_dir, monkeypatch):
    """Concurrency smoke test: write_page must acquire the wiki-wide lock."""
    calls = []
    from src.core import wiki_store as wiki_store_module
    original_locked = wiki_store_module.locked

    def spy_locked(path):
        calls.append(path)
        return original_locked(path)

    monkeypatch.setattr(wiki_store_module, "locked", spy_locked)

    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(type_="concept", slug="budgeting", title="Budgeting", summary="s", body="- a")

    assert any(str(p).endswith(".wiki.lock") for p in calls)


def test_list_pages_uses_cache_when_unchanged(long_term_dir, monkeypatch):
    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(type_="concept", slug="a", title="A", summary="s", body="- x")
    store.write_page(type_="concept", slug="b", title="B", summary="s", body="- y")

    first = store.list_pages()
    assert len(first) == 2

    read_calls = []
    original_read_text = Path.read_text

    def spy_read_text(self, *args, **kwargs):
        read_calls.append(self)
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", spy_read_text)

    second = store.list_pages()
    assert second == first
    assert read_calls == []


def test_list_pages_type_filter_reuses_cache(long_term_dir, monkeypatch):
    store = WikiStore(USER_ID, long_term_dir)
    store.write_page(type_="entity", slug="sarah", title="Sarah", summary="s", body="- a")
    store.write_page(type_="concept", slug="budgeting", title="Budgeting", summary="s", body="- a")
    store.list_pages()  # populate cache

    read_calls = []
    original_read_text = Path.read_text

    def spy_read_text(self, *args, **kwargs):
        read_calls.append(self)
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", spy_read_text)

    assert [p["slug"] for p in store.list_pages(type="concept")] == ["budgeting"]
    assert read_calls == []


def test_list_pages_detects_write_from_a_different_wikistore_instance(long_term_dir):
    """Proves cache invalidation is a stat-based diff against disk state,
    not a self-tracked dirty flag - store2 never writes anything itself
    but must still notice store1's writes on its next list_pages() call."""
    store1 = WikiStore(USER_ID, long_term_dir)
    store2 = WikiStore(USER_ID, long_term_dir)

    store1.write_page(type_="concept", slug="a", title="A", summary="s", body="- x")
    assert {p["slug"] for p in store2.list_pages()} == {"a"}

    store1.write_page(type_="concept", slug="b", title="B", summary="s", body="- y")
    assert {p["slug"] for p in store2.list_pages()} == {"a", "b"}

    store1.delete_page("concept", "a")
    assert {p["slug"] for p in store2.list_pages()} == {"b"}
