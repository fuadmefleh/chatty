"""Stocks skill tools using Yahoo Finance (yfinance).

Includes LLM-powered analysis tools for daily market summaries, news
sentiment correlation, and watchlist trend alerts.
"""
import json
import importlib.util
from pathlib import Path
from typing import Any, Dict, List
from src.core.skill_tool import SkillTool

# Load yahoo_client module from this skill folder
_skill_dir = Path(__file__).parent
_yahoo_path = _skill_dir / "yahoo_client.py"
_spec = importlib.util.spec_from_file_location("yahoo_client_module", _yahoo_path)
_yahoo_client = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_yahoo_client)

# Load analysis module from this skill folder
_analysis_path = _skill_dir / "analysis.py"
_analysis_spec = importlib.util.spec_from_file_location(
    "stocks_analysis", _analysis_path
)
_analysis = importlib.util.module_from_spec(_analysis_spec)
_analysis_spec.loader.exec_module(_analysis)


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


class GetDailyMarketSummaryTool(SkillTool):
    """Generate an LLM-powered daily market summary from current stock data."""

    name = "get_daily_market_summary"
    description = (
        "Generate a natural-language daily market summary using AI analysis. "
        "Fetches current market data (gainers, losers, most active) and produces "
        "a concise 3-5 paragraph summary covering market sentiment, standout "
        "movers, and volume highlights. Use this for daily briefings or when "
        "the user asks for a market overview."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }

    async def execute(self) -> str:
        # Fetch raw stock data first
        stocks_data = await _yahoo_client.get_top_stocks()

        if not stocks_data.get("success"):
            return json.dumps({
                "success": False,
                "error": f"Could not fetch stock data: {stocks_data.get('error')}",
            })

        # Generate LLM summary
        result = await _analysis.generate_daily_market_summary(stocks_data)
        return json.dumps(result, indent=2)


class GetNewsSentimentTool(SkillTool):
    """Analyze news sentiment for a ticker and correlate with price data."""

    name = "get_news_sentiment"
    description = (
        "Analyze news sentiment for a specific stock ticker using AI. "
        "Fetches recent news articles about the ticker, determines overall "
        "sentiment (positive/neutral/negative), identifies key themes, and "
        "correlates the sentiment with current price movement. "
        "Use this when the user asks about market sentiment for a stock "
        "or wants to understand why a stock is moving."
    )
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Stock ticker symbol (e.g., AAPL, MSFT, TSLA)"
            },
            "num_articles": {
                "type": "integer",
                "description": "Number of news articles to analyze (1-10, default: 5)",
                "default": 5
            }
        },
        "required": ["symbol"]
    }

    async def execute(self, symbol: str, num_articles: int = 5) -> str:
        symbol = symbol.upper().strip()
        num_articles = min(max(num_articles, 1), 10)

        # Fetch price data for correlation
        price_result = await _yahoo_client.get_ticker_info(symbol)
        price_data = None
        if price_result.get("success"):
            price_data = {
                "price": price_result.get("price"),
                "change": price_result.get("day_change", 0),
                "change_percent": price_result.get("day_change_percent", 0),
            }

        # Fetch news articles
        from skills.web_search.searxng_client import get_search_client
        search_client = get_search_client()

        if not search_client.is_configured():
            # Fall back to analysis without news (using price data only)
            result = await _analysis.analyze_news_sentiment(
                symbol, [], price_data=price_data
            )
            result["warning"] = (
                "Web search not configured - sentiment analysis based on price "
                "data only. Configure SEARXNG_BASE_URL for news analysis."
            )
            return json.dumps(result, indent=2)

        news_result = await search_client.search_news(
            f"{symbol} stock news", num_results=num_articles
        )

        articles = []
        if news_result.get("success"):
            articles = news_result.get("results", [])

        if not articles and not price_data:
            return json.dumps({
                "success": False,
                "error": f"No news articles or price data found for {symbol}",
                "ticker": symbol,
            })

        # Generate LLM sentiment analysis
        result = await _analysis.analyze_news_sentiment(
            symbol, articles, price_data=price_data
        )
        return json.dumps(result, indent=2)


class GetWatchlistAlertsTool(SkillTool):
    """Check a list of tickers for significant market movement alerts."""

    name = "get_watchlist_alerts"
    description = (
        "Check a list of stock tickers for significant daily movements and "
        "generate AI-powered alert messages. Flags stocks that move beyond a "
        "threshold (default 5%) or show unusual volume activity (2x average). "
        "Use this for proactive watchlist monitoring or when the user asks "
        "if any of their watched stocks are moving significantly."
    )
    parameters = {
        "type": "object",
        "properties": {
            "symbols": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of ticker symbols to check (e.g., [\"AAPL\", \"MSFT\", \"TSLA\"])"
            },
            "threshold_percent": {
                "type": "number",
                "description": "Minimum absolute daily change % to flag (default: 5.0)",
                "default": 5.0
            }
        },
        "required": ["symbols"]
    }

    async def execute(
        self, symbols: List[str], threshold_percent: float = 5.0
    ) -> str:
        if not symbols:
            return json.dumps({
                "success": False,
                "error": "No symbols provided to check",
            })

        # Fetch price data for each symbol
        watchlist_items: List[Dict[str, Any]] = []
        for symbol in symbols:
            info = await _yahoo_client.get_ticker_info(symbol.upper().strip())
            if info.get("success"):
                watchlist_items.append({
                    "symbol": info.get("symbol", symbol.upper()),
                    "name": info.get("name", symbol.upper()),
                    "price": info.get("price"),
                    "change": info.get("day_change", 0),
                    "change_percent": info.get("day_change_percent", 0),
                    "volume": info.get("volume", 0) or 0,
                    "avg_volume": info.get("avg_volume", 0) or 0,
                })

        if not watchlist_items:
            return json.dumps({
                "success": False,
                "error": f"Could not fetch data for any of: {', '.join(symbols)}",
            })

        # Run watchlist alert analysis
        result = await _analysis.check_watchlist_alerts(
            watchlist_items, threshold_percent
        )
        return json.dumps(result, indent=2)
