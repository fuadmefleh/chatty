"""Live smoke tests for src/managers/watch_sources.py checkers.

These hit real external APIs (Yahoo Finance, GitHub, SearXNG). Skips
gracefully rather than failing on network errors, since dev machines may be
offline or rate-limited.
"""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers import watch_sources


async def test_check_stock():
    print("🧪 Testing check_stock\n")

    result = await watch_sources.check_stock("AAPL", threshold_percent=0.0)
    if result is None:
        print("⚠️  Stock lookup failed (network/API issue?), skipping assertions.")
        return

    assert "notable" in result
    if result["notable"]:
        assert "summary" in result
        assert "sources" in result
    print(f"✅ check_stock returned notable={result['notable']}")

    # A threshold no real move will ever exceed should never be notable.
    never_notable = await watch_sources.check_stock("AAPL", threshold_percent=999)
    assert never_notable is not None
    assert never_notable["notable"] is False
    print("✅ Extreme threshold correctly not notable")


async def test_check_github():
    print("\n🧪 Testing check_github\n")

    first = await watch_sources.check_github("anthropics/claude-code", seen_markers=[])
    if first is None:
        print("⚠️  GitHub lookup failed (network/rate-limit?), skipping assertions.")
        return

    assert "new_markers" in first
    assert "new_items" in first
    print(f"✅ First check found {len(first['new_items'])} new item(s)")

    # Re-checking with those same markers already "seen" should find nothing new.
    second = await watch_sources.check_github("anthropics/claude-code", seen_markers=first["new_markers"])
    assert second is not None
    assert second["new_items"] == []
    print("✅ Dedup works - no new items on second check with same markers")

    # Malformed repo string should fail cleanly, not raise.
    bad = await watch_sources.check_github("not-a-valid-repo-string", seen_markers=[])
    assert bad is None
    print("✅ Malformed repo string handled gracefully")


async def test_check_news():
    print("\n🧪 Testing check_news\n")

    result = await watch_sources.check_news("technology", seen_markers=[])
    if result is None:
        print("⚠️  News search failed (SearXNG unreachable?), skipping assertions.")
        return

    assert "all_markers" in result
    assert "new_items" in result
    print(f"✅ check_news found {len(result['new_items'])} new item(s)")


async def main():
    await test_check_stock()
    await test_check_github()
    await test_check_news()
    print("\n✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
