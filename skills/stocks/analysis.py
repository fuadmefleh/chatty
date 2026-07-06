"""LLM-driven market analysis pipeline for the Stocks skill.

Generates daily market summaries, correlates news sentiment with price
movements, and evaluates watchlist items for significant trend alerts.
"""
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.llm import get_llm_provider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort JSON-object parse: try the whole reply first, then fall
    back to the first { ... } substring in case the model wrapped it in prose
    or a code fence."""
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        return None


def _extract_json_array(text: str) -> Optional[List[Any]]:
    """Best-effort JSON-array parse: try the whole reply first, then fall
    back to the first [ ... ] substring."""
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, ValueError):
        return None


def _format_stock_rows(stocks: List[Dict]) -> str:
    """Format a list of stock dicts into a readable table string for the LLM."""
    if not stocks:
        return "(no data)"
    lines = []
    for s in stocks:
        symbol = s.get("symbol", "?")
        price = s.get("price", 0)
        change = s.get("change", 0)
        pct = s.get("change_percent", 0)
        vol = s.get("volume", 0)
        lines.append(
            f"{symbol}: ${price:.2f} "
            f"({'+' if change >= 0 else ''}{change:.2f}) "
            f"({'+' if pct >= 0 else ''}{pct:.2f}%) "
            f"vol={vol}"
        )
    return "\n".join(lines)


def _format_news_items(articles: List[Dict]) -> str:
    """Format news articles into a readable block for the LLM."""
    if not articles:
        return "(no articles)"
    lines = []
    for a in articles:
        title = a.get("title", "?")
        snippet = a.get("snippet", "")
        source = a.get("source", a.get("display_link", ""))
        lines.append(f"- {title} ({source}): {snippet[:200]}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public analysis functions
# ---------------------------------------------------------------------------

async def generate_daily_market_summary(
    stocks_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate a daily market summary using the LLM.

    Takes raw stock data (as returned by get_top_stocks or similar) and
    produces a concise natural-language summary covering:
    - Overall market direction
    - Top gainers and losers with brief commentary
    - Notable volume activity

    Args:
        stocks_data: Dict with keys like 'gainers', 'losers', 'most_active',
                     each a list of stock dicts (symbol, price, change,
                     change_percent, volume).

    Returns:
        Dict with 'summary' (str) and 'raw_stocks' (echoed input).
    """
    try:
        gainers = stocks_data.get("gainers", [])
        losers = stocks_data.get("losers", [])
        most_active = stocks_data.get("most_active", [])
        timestamp = stocks_data.get("timestamp", datetime.now().isoformat())

        provider = get_llm_provider()

        prompt = (
            f"You are a financial market analyst. Generate a concise daily "
            f"market summary based on the following stock data.\n\n"
            f"Date: {timestamp}\n\n"
            f"Top Gainers:\n{_format_stock_rows(gainers)}\n\n"
            f"Top Losers:\n{_format_stock_rows(losers)}\n\n"
            f"Most Active (by volume):\n{_format_stock_rows(most_active)}\n\n"
            f"Write a 3-5 paragraph summary covering:\n"
            f"1. Overall market sentiment and direction\n"
            f"2. Standout gainers and why they might be moving\n"
            f"3. Notable decliners\n"
            f"4. Volume highlights\n\n"
            f"Be factual, avoid speculation beyond the data, and keep it "
            f"concise. Use $ for prices and % for percentages."
        )

        response = await provider.complete(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        summary = response.content or "Unable to generate market summary."

        return {
            "success": True,
            "summary": summary,
            "generated_at": datetime.now().isoformat(),
            "stock_count": (
                len(gainers) + len(losers) + len(most_active)
            ),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def analyze_news_sentiment(
    ticker: str,
    news_articles: List[Dict],
    price_data: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Correlate news sentiment with price movements for a ticker.

    Args:
        ticker: Stock symbol (e.g., 'AAPL').
        news_articles: List of article dicts with 'title', 'snippet',
                       'source', 'link' keys.
        price_data: Optional stock price info dict with keys like
                    'price', 'change', 'change_percent'.

    Returns:
        Dict with 'sentiment' (positive/neutral/negative), 'summary',
        'price_correlation', and 'articles' (echoed).
    """
    try:
        provider = get_llm_provider()

        news_text = _format_news_items(news_articles)

        price_context = ""
        if price_data:
            price = price_data.get("price", "?")
            change = price_data.get("change", 0)
            pct = price_data.get("change_percent", 0)
            price_context = (
                f"\n\nCurrent Price Data:\n"
                f"{ticker}: ${price} "
                f"({'+' if change >= 0 else ''}{change:.2f}) "
                f"({'+' if pct >= 0 else ''}{pct:.2f}%)"
            )

        prompt = (
            "You are a financial analyst. Analyze the sentiment of the "
            f"following news articles about {ticker}{price_context}\n\n"
            "News Articles:\n"
            f"{news_text}\n\n"
            'Return ONLY a JSON object (no prose, no code fences) with:\n'
            '{"sentiment": "positive" | "neutral" | "negative",\n'
            ' "confidence": <float 0-1>,\n'
            ' "summary": "<2-3 sentence sentiment analysis>",\n'
            ' "key_themes": ["<theme1>", "<theme2>", ...],\n'
            ' "price_correlation": "<does sentiment align with or diverge from '
            'price movement? one sentence>"}\n'
            'If no price data was provided, set price_correlation to '
            '"N/A - no price data provided"'
        )

        response = await provider.complete(
            [{"role": "user", "content": prompt}],
            temperature=0.2,
        )

        parsed = _extract_json(response.content or "")

        if parsed:
            return {
                "success": True,
                "ticker": ticker,
                "sentiment": parsed.get("sentiment", "neutral"),
                "confidence": parsed.get("confidence", 0.5),
                "summary": parsed.get("summary", "Unable to analyze sentiment."),
                "key_themes": parsed.get("key_themes", []),
                "price_correlation": parsed.get("price_correlation", "N/A"),
                "article_count": len(news_articles),
                "generated_at": datetime.now().isoformat(),
            }
        else:
            # Fallback: return raw text if JSON parsing fails
            return {
                "success": True,
                "ticker": ticker,
                "sentiment": "neutral",
                "confidence": 0.3,
                "summary": response.content or "Unable to analyze sentiment.",
                "key_themes": [],
                "price_correlation": "N/A",
                "article_count": len(news_articles),
                "generated_at": datetime.now().isoformat(),
                "raw_llm_response": response.content,
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "ticker": ticker,
        }


async def check_watchlist_alerts(
    watchlist_items: List[Dict],
    threshold_percent: float = 5.0,
) -> Dict[str, Any]:
    """Check watchlist stocks for significant trends and generate alert summaries.

    Evaluates each watchlist item for notable price movements, unusual volume,
    and generates LLM-powered alert messages for items that cross thresholds.

    Args:
        watchlist_items: List of dicts with 'symbol', 'price', 'change',
                         'change_percent', 'volume', 'avg_volume', 'name'.
        threshold_percent: Minimum absolute daily change % to trigger an alert.

    Returns:
        Dict with 'alerts' (list of alert dicts) and 'checked_count'.
    """
    try:
        flagged: List[Dict] = []
        for item in watchlist_items:
            pct = abs(item.get("change_percent", 0))
            volume = item.get("volume", 0)
            avg_volume = item.get("avg_volume", 0)

            reasons: List[str] = []

            # Price movement threshold
            if pct >= threshold_percent:
                direction = "up" if item.get("change_percent", 0) > 0 else "down"
                reasons.append(
                    f"Price moved {direction} {pct:.1f}% "
                    f"(threshold: {threshold_percent:.0f}%)"
                )

            # Unusual volume (2x average)
            if avg_volume and volume > avg_volume * 2:
                reasons.append(
                    f"Unusual volume: {volume:,} vs avg {avg_volume:,}"
                )

            if reasons:
                flagged.append({
                    "symbol": item.get("symbol", "?"),
                    "name": item.get("name", item.get("symbol", "?")),
                    "price": item.get("price"),
                    "change": item.get("change", 0),
                    "change_percent": item.get("change_percent", 0),
                    "volume": volume,
                    "avg_volume": avg_volume,
                    "reasons": reasons,
                })

        if not flagged:
            return {
                "success": True,
                "alerts": [],
                "checked_count": len(watchlist_items),
                "threshold_percent": threshold_percent,
                "generated_at": datetime.now().isoformat(),
            }

        # Generate LLM-powered alert messages
        provider = get_llm_provider()

        flagged_text = "\n".join(
            f"- {f['symbol']} ({f['name']}): ${f['price']} "
            f"({'+' if f['change_percent'] >= 0 else ''}{f['change_percent']:.2f}%), "
            f"reasons: {'; '.join(f['reasons'])}"
            for f in flagged
        )

        prompt = (
            f"You are a financial alert system. Generate concise alert "
            f"messages for the following notable stock movements.\n\n"
            f"Flagged stocks:\n{flagged_text}\n\n"
            f"Return ONLY a JSON array (no prose, no code fences) where each "
            f"element is:\n"
            f'{{"symbol": "<ticker>",\n'
            f' "alert": "<1-2 sentence alert message for a user watchlist>"}}'
        )

        response = await provider.complete(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        # Parse LLM response and merge with flagged data
        alerts: List[Dict] = []
        parsed = _extract_json_array(response.content or "")

        if parsed is not None:
            llm_alerts = {
                item.get("symbol", "").upper(): item.get("alert", "")
                for item in parsed
                if isinstance(item, dict)
            }

            for f in flagged:
                symbol = f["symbol"].upper()
                alerts.append({
                    "symbol": symbol,
                    "name": f["name"],
                    "price": f["price"],
                    "change_percent": f["change_percent"],
                    "alert": llm_alerts.get(
                        symbol,
                        f"{f['name']} ({symbol}) is up {f['change_percent']:.1f}% today at ${f['price']}.",
                    ),
                    "reasons": f["reasons"],
                })
        else:
            # Fallback: generate simple alerts without LLM parsing
            for f in flagged:
                alerts.append({
                    "symbol": f["symbol"].upper(),
                    "name": f["name"],
                    "price": f["price"],
                    "change_percent": f["change_percent"],
                    "alert": (
                        f"{f['name']} ({f['symbol']}) "
                        f"{'up' if f['change_percent'] >= 0 else 'down'} "
                        f"{abs(f['change_percent']):.1f}% today at ${f['price']}. "
                        f"{' | '.join(f['reasons'])}"
                    ),
                    "reasons": f["reasons"],
                })

        return {
            "success": True,
            "alerts": alerts,
            "checked_count": len(watchlist_items),
            "flagged_count": len(flagged),
            "threshold_percent": threshold_percent,
            "generated_at": datetime.now().isoformat(),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "checked_count": len(watchlist_items),
        }
