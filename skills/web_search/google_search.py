"""Google Custom Search API integration using API key.

Requires:
1. GOOGLE_API_KEY in .env
2. GOOGLE_CSE_ID in .env (Custom Search Engine ID from programmablesearchengine.google.com)
3. Custom Search API enabled in Google Cloud Console

Documentation: https://developers.google.com/custom-search/v1/overview
"""
import json
from typing import Dict, Any, Optional
import asyncio

try:
    import httpx
except ImportError:
    httpx = None

from src.core import config
from src.core.logging_config import get_skills_logger

logger = get_skills_logger()

GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"


class GoogleSearchClient:
    """Client for Google Custom Search API using API key."""
    
    def __init__(self, api_key: str = None, cse_id: str = None):
        """Initialize the Google Search client.
        
        Args:
            api_key: Google API key
            cse_id: Custom Search Engine ID
        """
        self.api_key = api_key or config.GOOGLE_API_KEY
        self.cse_id = cse_id or config.GOOGLE_CSE_ID
        
        if not self.api_key or not self.cse_id:
            logger.warning("Google Search not configured. Set GOOGLE_API_KEY and GOOGLE_CSE_ID in .env")
    
    def is_configured(self) -> bool:
        """Check if the search client is properly configured."""
        return bool(self.api_key and self.cse_id)
    
    async def search(
        self, 
        query: str, 
        num_results: int = 5,
        search_type: str = None,
        date_restrict: str = None
    ) -> Dict[str, Any]:
        """Perform a web search using Google Custom Search API.
        
        Args:
            query: Search query string
            num_results: Number of results to return (max 10)
            search_type: Optional - "image" for image search
            date_restrict: Optional - Restrict to recent results (e.g., "d1" for past day, "w1" for past week)
            
        Returns:
            Dict with search results or error information
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Google Search API not configured. Please set GOOGLE_API_KEY and GOOGLE_CSE_ID in your .env file."
            }
        
        if httpx is None:
            return {
                "success": False,
                "error": "httpx library not installed. Run: pip install httpx"
            }
        
        # Build query parameters
        params = {
            "key": self.api_key,
            "cx": self.cse_id,
            "q": query,
            "num": min(num_results, 10)  # Google CSE max is 10
        }
        
        if search_type:
            params["searchType"] = search_type
        
        if date_restrict:
            params["dateRestrict"] = date_restrict
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(GOOGLE_SEARCH_URL, params=params)
                
                # Check for errors
                if response.status_code != 200:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "Unknown error")
                    
                    if response.status_code == 403:
                        if "This project does not have the access" in error_msg:
                            return {
                                "success": False,
                                "error": "Custom Search API is not enabled. Go to Google Cloud Console > APIs & Services > Library > Search for 'Custom Search API' and enable it."
                            }
                        else:
                            return {
                                "success": False,
                                "error": "API key invalid or quota exceeded. Check your API key in Google Cloud Console."
                            }
                    elif response.status_code == 400:
                        return {
                            "success": False,
                            "error": f"Invalid request: {error_msg}"
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status_code}: {error_msg}"
                        }
                
                data = response.json()
            
            # Parse the results
            results = []
            for item in data.get("items", []):
                result = {
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "display_link": item.get("displayLink", "")
                }
                
                # Add image info if available
                if "pagemap" in item and "cse_image" in item["pagemap"]:
                    result["image"] = item["pagemap"]["cse_image"][0].get("src", "")
                
                results.append(result)
            
            return {
                "success": True,
                "query": query,
                "total_results": data.get("searchInformation", {}).get("totalResults", "0"),
                "search_time": data.get("searchInformation", {}).get("searchTime", 0),
                "results": results
            }
            
        except httpx.TimeoutException:
            logger.error("Google Search API timeout")
            return {
                "success": False,
                "error": "Search request timed out. Please try again."
            }
        except Exception as e:
            logger.error(f"Google Search error: {e}", exc_info=True)
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
            Search results filtered to recent content
        """
        return await self.search(
            query=f"{query} news",
            num_results=num_results,
            date_restrict="w1"
        )
    
    async def search_images(self, query: str, num_results: int = 5) -> Dict[str, Any]:
        """Search for images.
        
        Args:
            query: Search query
            num_results: Number of results
            
        Returns:
            Image search results
        """
        return await self.search(
            query=query,
            num_results=num_results,
            search_type="image"
        )


# Module-level client instance
_search_client: Optional[GoogleSearchClient] = None


def get_search_client() -> GoogleSearchClient:
    """Get or create the search client singleton."""
    global _search_client
    if _search_client is None:
        _search_client = GoogleSearchClient()
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
