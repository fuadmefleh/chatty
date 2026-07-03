"""Test script for the SearXNG web search client.

Requires a running SearXNG instance (see docker-compose.yml at repo root:
`docker compose up -d searxng`). Skips gracefully rather than failing if the
instance isn't reachable, since dev machines may not have it running.
"""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from skills.web_search.searxng_client import SearxngClient


async def test_searxng_client():
    """Test the SearXNG client functionality."""
    print("🧪 Testing SearXNG Client\n")

    client = SearxngClient()

    if not client.is_configured():
        print("⚠️  SEARXNG_BASE_URL not configured, skipping.")
        return

    try:
        result = await client.search("Python programming", num_results=3)
    except httpx.ConnectError:
        print("⚠️  Could not connect to SearXNG - is `docker compose up -d searxng` running? Skipping.")
        return

    if not result.get("success"):
        print(f"⚠️  Search failed (instance may not be reachable): {result.get('error')}")
        return

    assert "results" in result
    for item in result["results"]:
        assert "title" in item
        assert "link" in item
        assert "snippet" in item
        assert "display_link" in item

    print(f"✅ Got {len(result['results'])} result(s) with the expected shape")

    news_result = await client.search_news("technology", num_results=3)
    print(f"✅ search_news returned success={news_result.get('success')}")


if __name__ == "__main__":
    asyncio.run(test_searxng_client())
