"""Web search skill tools using a self-hosted SearXNG instance."""
import json
import importlib.util
from pathlib import Path
from src.core.skill_tool import SkillTool

# Load searxng_client module from this skill folder
_skill_dir = Path(__file__).parent
_searxng_client_path = _skill_dir / "searxng_client.py"
_spec = importlib.util.spec_from_file_location("searxng_client_module", _searxng_client_path)
_searxng_client = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_searxng_client)

SearxngClient = _searxng_client.SearxngClient
get_search_client = _searxng_client.get_search_client


class WebSearchTool(SkillTool):
    """Search the web for information."""
    
    name = "web_search"
    description = "Search the web for current information, news, facts, or any topic. Returns relevant web pages with titles, snippets, and links."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query - be specific for better results"
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (1-10, default: 5)",
                "default": 5
            }
        },
        "required": ["query"]
    }
    
    async def execute(self, query: str, num_results: int = 5) -> str:
        client = get_search_client()

        if not client.is_configured():
            return json.dumps({
                "success": False,
                "error": "Web search not configured. Set SEARXNG_BASE_URL in .env file and run `docker compose up -d searxng`."
            })

        result = await client.search(query, num_results)

        if result["success"]:
            # Format results in a more readable way
            formatted = {
                "success": True,
                "query": query,
                "result_count": len(result["results"]),
                "results": []
            }
            
            for i, r in enumerate(result["results"], 1):
                formatted["results"].append({
                    "rank": i,
                    "title": r["title"],
                    "url": r["link"],
                    "snippet": r["snippet"],
                    "source": r["display_link"]
                })
            
            return json.dumps(formatted, indent=2)
        else:
            return json.dumps(result)


class SearchNewsTool(SkillTool):
    """Search for recent news articles."""
    
    name = "search_news"
    description = "Search for recent news articles on a topic. Returns news from the past week."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The news topic to search for"
            },
            "num_results": {
                "type": "integer",
                "description": "Number of news articles to return (1-10, default: 5)",
                "default": 5
            }
        },
        "required": ["query"]
    }
    
    async def execute(self, query: str, num_results: int = 5) -> str:
        client = get_search_client()

        if not client.is_configured():
            return json.dumps({
                "success": False,
                "error": "Web search not configured. Set SEARXNG_BASE_URL in .env file and run `docker compose up -d searxng`."
            })

        result = await client.search_news(query, num_results)
        
        if result["success"]:
            formatted = {
                "success": True,
                "query": query,
                "type": "news",
                "result_count": len(result["results"]),
                "articles": []
            }
            
            for i, r in enumerate(result["results"], 1):
                formatted["articles"].append({
                    "rank": i,
                    "title": r["title"],
                    "url": r["link"],
                    "snippet": r["snippet"],
                    "source": r["display_link"]
                })
            
            return json.dumps(formatted, indent=2)
        else:
            return json.dumps(result)


class SearchRecentTool(SkillTool):
    """Search for content from a specific time period."""
    
    name = "search_recent"
    description = "Search for web content from a specific recent time period. Useful for finding current events or recent updates."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query"
            },
            "time_period": {
                "type": "string",
                "enum": ["day", "week", "month", "year"],
                "description": "How recent the results should be",
                "default": "week"
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results (1-10, default: 5)",
                "default": 5
            }
        },
        "required": ["query"]
    }
    
    async def execute(self, query: str, time_period: str = "week", num_results: int = 5) -> str:
        client = get_search_client()

        if not client.is_configured():
            return json.dumps({
                "success": False,
                "error": "Web search not configured. Set SEARXNG_BASE_URL in .env file and run `docker compose up -d searxng`."
            })

        # SearXNG's time_range param already accepts these values directly
        result = await client.search(query, num_results, time_range=time_period)
        
        if result["success"]:
            formatted = {
                "success": True,
                "query": query,
                "time_period": time_period,
                "result_count": len(result["results"]),
                "results": []
            }
            
            for i, r in enumerate(result["results"], 1):
                formatted["results"].append({
                    "rank": i,
                    "title": r["title"],
                    "url": r["link"],
                    "snippet": r["snippet"],
                    "source": r["display_link"]
                })
            
            return json.dumps(formatted, indent=2)
        else:
            return json.dumps(result)
