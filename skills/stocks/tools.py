"""Stocks skill tools using Yahoo Finance (yfinance)."""
import json
import importlib.util
from pathlib import Path
from src.core.skill_tool import SkillTool

# Load yahoo_client module from this skill folder
_skill_dir = Path(__file__).parent
_yahoo_path = _skill_dir / "yahoo_client.py"
_spec = importlib.util.spec_from_file_location("yahoo_client_module", _yahoo_path)
_yahoo_client = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_yahoo_client)


class GetTopStocksTool(SkillTool):
    """Get today's top stocks: gainers, losers, and most active."""
    
    name = "get_top_stocks"
    description = "Get today's top performing stocks including biggest gainers, biggest losers, and most actively traded stocks. Shows price, change, and volume data."
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    async def execute(self) -> str:
        result = await _yahoo_client.get_top_stocks()
        return json.dumps(result, indent=2)


class GetMarketMoversTool(SkillTool):
    """Get top gainers, losers, or most active stocks."""
    
    name = "get_market_movers"
    description = "Get top market movers by category: gainers (biggest % increase), losers (biggest % decrease), or most_active (highest volume)."
    parameters = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["gainers", "losers", "most_active"],
                "description": "Category of movers to fetch",
                "default": "gainers"
            },
            "limit": {
                "type": "integer",
                "description": "Number of results to return (1-20)",
                "default": 10
            }
        },
        "required": ["category"]
    }
    
    async def execute(self, category: str = "gainers", limit: int = 10) -> str:
        result = await _yahoo_client.get_market_movers(category, min(max(limit, 1), 20))
        return json.dumps(result, indent=2)


class GetTickerInfoTool(SkillTool):
    """Get detailed information for a specific stock ticker."""
    
    name = "get_ticker_info"
    description = "Get detailed stock information for a specific ticker symbol including price, day change, market cap, P/E ratio, 52-week range, volume, sector, and industry."
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Stock ticker symbol (e.g., AAPL, MSFT, TSLA)"
            }
        },
        "required": ["symbol"]
    }
    
    async def execute(self, symbol: str) -> str:
        result = await _yahoo_client.get_ticker_info(symbol.upper().strip())
        return json.dumps(result, indent=2)
