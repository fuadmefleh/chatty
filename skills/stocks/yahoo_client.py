"""Yahoo Finance client wrapper using yfinance."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional, Callable
import yfinance as yf


# Thread pool for running blocking yfinance calls
_thread_pool: Optional[ThreadPoolExecutor] = None


def _get_thread_pool() -> ThreadPoolExecutor:
    global _thread_pool
    if _thread_pool is None:
        _thread_pool = ThreadPoolExecutor(max_workers=4)
    return _thread_pool


async def _run_in_thread(func: Callable, *args, **kwargs) -> Any:
    """Run a blocking function in the thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_get_thread_pool(), func, *args, **kwargs)


async def get_market_movers(category: str = "gainers", limit: int = 10) -> Dict[str, Any]:
    """Get top market movers from Yahoo Finance.
    
    Args:
        category: One of 'gainers', 'losers', 'most_active'
        limit: Number of results to return
        
    Returns:
        Dict with stock data
    """
    try:
        # Use Yahoo Finance's predefined views
        ticker = yf.Ticker("^DJI")  # Dow Jones as anchor for market data
        
        # Scrape trending/movers from Yahoo Finance
        movers_data = await _run_in_thread(_fetch_movers, category, limit)
        return movers_data
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "category": category
        }


def _fetch_movers(category: str, limit: int) -> Dict[str, Any]:
    """Fetch market movers by scraping Yahoo Finance."""
    import requests
    from bs4 import BeautifulSoup
    
    url_map = {
        "gainers": "https://finance.yahoo.com/trending-tickers/",
        "losers": "https://finance.yahoo.com/trending-tickers/",
        "most_active": "https://finance.yahoo.com/trending-tickers/",
    }
    
    # Try to use yfinance's built-in capabilities first
    try:
        # Fetch trending tickers from Yahoo
        quotes = yf.download(
            tickers="^DJI ^SPY ^IXIC AAPL MSFT GOOGL AMZN NVDA TSLA META",
            period="1d",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
        )
        
        # Build a summary of today's performance
        stocks_data = []
        for symbol in quotes.columns.get_level_values(0).unique():
            try:
                close = quotes[symbol]["Close"].dropna()
                open_price = quotes[symbol]["Open"].dropna()
                
                if len(close) > 0 and len(open_price) > 0:
                    current_price = close.iloc[-1]
                    opening_price = open_price.iloc[-1] if len(open_price) > 0 else current_price
                    
                    change = current_price - opening_price
                    pct_change = (change / opening_price * 100) if opening_price else 0
                    
                    # Try to get the last day's close for day-over-day change
                    if len(close) >= 2:
                        prev_close = close.iloc[-2]
                        change = current_price - prev_close
                        pct_change = (change / prev_close * 100) if prev_close else 0
                    
                    stocks_data.append({
                        "symbol": symbol,
                        "price": round(float(current_price), 2),
                        "change": round(float(change), 2),
                        "change_percent": round(float(pct_change), 2),
                    })
            except Exception:
                continue
        
        if not stocks_data:
            raise Exception("No data retrieved")
        
        # Sort based on category
        if category == "gainers":
            stocks_data.sort(key=lambda x: x["change_percent"], reverse=True)
        elif category == "losers":
            stocks_data.sort(key=lambda x: x["change_percent"])
        else:  # most_active - default sort by absolute change
            stocks_data.sort(key=lambda x: abs(x["change_percent"]), reverse=True)
        
        return {
            "success": True,
            "category": category,
            "count": len(stocks_data[:limit]),
            "stocks": stocks_data[:limit]
        }
    
    except Exception as primary_error:
        # Fallback: fetch from Yahoo trending page
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36"
            }
            response = requests.get("https://finance.yahoo.com/trending-tickers/", 
                                    headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            rows = soup.find_all("tr", class_=lambda c: c and "js-row-row" in c)
            
            if not rows:
                # Try alternative selector
                rows = soup.find_all("tr")
                rows = [r for r in rows[1:] if r.find("a")]
            
            trending = []
            for row in rows[:limit]:
                cols = row.find_all(["td", "th"])
                if len(cols) >= 3:
                    try:
                        symbol_text = cols[0].get_text(strip=True)
                        name_text = cols[1].get_text(strip=True) if len(cols) > 1 else ""
                        price_text = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                        
                        trending.append({
                            "symbol": symbol_text,
                            "name": name_text,
                            "price": price_text,
                        })
                    except Exception:
                        continue
            
            if trending:
                return {
                    "success": True,
                    "category": "trending",
                    "count": len(trending),
                    "stocks": trending
                }
            else:
                raise Exception("No trending stocks found")
                
        except Exception as fallback_error:
            return {
                "success": False,
                "error": f"Primary: {primary_error}, Fallback: {fallback_error}",
                "category": category
            }


async def get_ticker_info(symbol: str) -> Dict[str, Any]:
    """Get detailed info for a specific stock ticker.
    
    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'MSFT')
        
    Returns:
        Dict with stock details
    """
    try:
        def _fetch():
            ticker = yf.Ticker(symbol)
            
            # Get basic info
            info = ticker.info
            
            # Get today's price data
            hist = ticker.history(period="1d")
            
            current_price = None
            day_change = 0
            day_change_pct = 0
            
            if not hist.empty:
                current_price = round(float(hist["Close"].iloc[-1]), 2)
                if len(hist) >= 2:
                    prev_close = float(hist["Close"].iloc[-2])
                    day_change = round(current_price - prev_close, 2)
                    day_change_pct = round((day_change / prev_close * 100), 2) if prev_close else 0
                elif "Open" in hist.columns:
                    open_price = float(hist["Open"].iloc[-1])
                    day_change = round(current_price - open_price, 2)
                    day_change_pct = round((day_change / open_price * 100), 2) if open_price else 0
            
            return {
                "symbol": info.get("symbol", symbol.upper()),
                "name": info.get("shortName", info.get("longName", symbol.upper())),
                "price": current_price or info.get("currentPrice", info.get("regularMarketPrice")),
                "day_change": day_change or info.get("regularMarketChange", 0),
                "day_change_percent": day_change_pct or info.get("regularMarketChangePercent", 0),
                "open": info.get("open", info.get("regularMarketOpen")),
                "high": info.get("dayHigh", info.get("regularMarketDayHigh")),
                "low": info.get("dayLow", info.get("regularMarketDayLow")),
                "previous_close": info.get("previousClose", info.get("regularMarketPreviousClose")),
                "volume": info.get("volume", info.get("regularMarketVolume")),
                "avg_volume": info.get("averageVolume", info.get("averageVolume10days")),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE", info.get("forwardPE")),
                "dividend_yield": info.get("dividendYield"),
                "52_week_high": info.get("fiftyTwoWeekHigh"),
                "52_week_low": info.get("fiftyTwoWeekLow"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
            }
        
        result = await _run_in_thread(_fetch)
        return {"success": True, **result}
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol
        }


async def get_top_stocks() -> Dict[str, Any]:
    """Get a comprehensive overview of today's top stocks.
    
    Returns:
        Dict with gainers, losers, and most active stocks
    """
    try:
        # Fetch performance data for a broad set of popular stocks
        tickers = "AAPL MSFT GOOGL AMZN NVDA TSLA META NFLX AVGO AMD QCOM INTC COST WMT JPM JNJ V PG UNH XOM HD MA DIS PYPL BA SPGI"

        def _fetch():
            quotes = yf.download(
                tickers=tickers,
                period="5d",
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                progress=False,
            )

            stocks_data = []
            for symbol in quotes.columns.get_level_values(0).unique():
                try:
                    close = quotes[symbol]["Close"].dropna()
                    if len(close) >= 2:
                        current = float(close.iloc[-1])
                        prev_close = float(close.iloc[-2])
                        change = current - prev_close
                        pct = (change / prev_close * 100) if prev_close else 0

                        volume = 0
                        if "Volume" in quotes[symbol].columns:
                            vol = quotes[symbol]["Volume"].dropna()
                            if len(vol) > 0:
                                volume = int(vol.iloc[-1])

                        stocks_data.append({
                            "symbol": symbol,
                            "price": round(current, 2),
                            "change": round(change, 2),
                            "change_percent": round(pct, 2),
                            "volume": volume,
                        })
                    elif len(close) == 1:
                        # Fallback: use ticker.info for current price
                        try:
                            t = yf.Ticker(symbol)
                            info = t.info
                            current = info.get("regularMarketPrice", float(close.iloc[-1]))
                            prev_close = info.get("regularMarketPreviousClose", 0)
                            change = current - prev_close if prev_close else 0
                            pct = (change / prev_close * 100) if prev_close else 0
                            volume = info.get("regularMarketVolume", 0) or 0
                        except Exception:
                            current = float(close.iloc[-1])
                            change = 0
                            pct = 0
                            volume = 0

                        stocks_data.append({
                            "symbol": symbol,
                            "price": round(current, 2),
                            "change": round(change, 2),
                            "change_percent": round(pct, 2),
                            "volume": volume,
                        })
                except Exception:
                    continue

            return stocks_data
        
        all_stocks = await _run_in_thread(_fetch)
        
        if not all_stocks:
            return {
                "success": False,
                "error": "No stock data retrieved"
            }
        
        # Sort into categories
        sorted_by_gain = sorted(all_stocks, key=lambda x: x["change_percent"], reverse=True)
        sorted_by_volume = sorted(all_stocks, key=lambda x: x["volume"], reverse=True)
        
        return {
            "success": True,
            "timestamp": __import__('datetime').datetime.now().isoformat(),
            "gainers": sorted_by_gain[:8],
            "losers": sorted(all_stocks, key=lambda x: x["change_percent"])[:8],
            "most_active": sorted_by_volume[:8],
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
