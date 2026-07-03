"""SearXNG integration for web search.

Requires a running SearXNG instance with JSON output enabled
(search.formats includes "json" in its settings.yml). See docker-compose.yml
and docker/searxng/settings.yml at the repo root - start it with:

    docker compose up -d searxng

Configure the instance URL via SEARXNG_BASE_URL in .env (defaults to
http://localhost:8080).
"""
import json
from urllib.parse import urlparse
from typing import Dict, Any, Optional
import asyncio

try:
    import httpx
except ImportError:
    httpx = None

from src.core import config
from src.core.logging_config import get_skills_logger

logger = get_skills_logger()


class SearxngClient:
    """Client for a self-hosted SearXNG instance's JSON search API."""

    def __init__(self, base_url: str = None):
        """Initialize the SearXNG client.

        Args:
            base_url: Base URL of the SearXNG instance (e.g. http://localhost:8080)
        """
        self.base_url = (base_url or config.SEARXNG_BASE_URL or "").rstrip("/")

        if not self.base_url:
            logger.warning("SearXNG not configured. Set SEARXNG_BASE_URL in .env")

    def is_configured(self) -> bool:
        """Check if the search client is properly configured."""
        return bool(self.base_url)

    async def search(
        self,
        query: str,
        num_results: int = 5,
        categories: str = None,
        time_range: str = None
    ) -> Dict[str, Any]:
        """Perform a web search using the SearXNG JSON API.

        Args:
            query: Search query string
            num_results: Number of results to return (sliced client-side)
            categories: Optional SearXNG category filter (e.g. "news")
            time_range: Optional recency filter ("day", "week", "month", "year")

        Returns:
            Dict with search results or error information
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "SearXNG not configured. Set SEARXNG_BASE_URL in your .env file."
            }

        if httpx is None:
            return {
                "success": False,
                "error": "httpx library not installed. Run: pip install httpx"
            }

        params = {
            "q": query,
            "format": "json",
        }
        if categories:
            params["categories"] = categories
        if time_range:
            params["time_range"] = time_range

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}/search", params=params)

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": (
                            f"HTTP {response.status_code} from SearXNG. Check that the "
                            "searxng Docker container is running and that search.formats "
                            "includes 'json' in docker/searxng/settings.yml."
                        )
                    }

                data = response.json()

            results = []
            for item in data.get("results", [])[:num_results]:
                link = item.get("url", "")
                results.append({
                    "title": item.get("title", ""),
                    "link": link,
                    "snippet": item.get("content", ""),
                    "display_link": urlparse(link).netloc,
                })

            return {
                "success": True,
                "query": query,
                "total_results": str(len(results)),
                "results": results,
            }

        except httpx.ConnectError:
            logger.error("SearXNG connection error - is the container running?")
            return {
                "success": False,
                "error": (
                    "Could not connect to SearXNG. Run `docker compose up -d searxng` "
                    "and verify SEARXNG_BASE_URL in .env."
                )
            }
        except httpx.TimeoutException:
            logger.error("SearXNG request timeout")
            return {
                "success": False,
                "error": "Search request timed out. Please try again."
            }
        except Exception as e:
            logger.error(f"SearXNG search error: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Search failed: {str(e)}"
            }

    async def search_news(self, query: str, num_results: int = 5) -> Dict[str, Any]:
        """Search for recent news articles.

        Args:
            query: Search query
            num_results: Number of results

        Returns:
            Search results filtered to the news category
        """
        return await self.search(query, num_results, categories="news")


# Module-level client instance
_search_client: Optional[SearxngClient] = None


def get_search_client() -> SearxngClient:
    """Get or create the search client singleton."""
    global _search_client
    if _search_client is None:
        _search_client = SearxngClient()
    return _search_client


async def web_search(query: str, num_results: int = 5) -> Dict[str, Any]:
    """Perform a web search."""
    client = get_search_client()
    return await client.search(query, num_results)


if __name__ == "__main__":
    # Test the search
    async def test():
        result = await web_search("Python programming latest news", 3)
        print(json.dumps(result, indent=2))

    asyncio.run(test())
