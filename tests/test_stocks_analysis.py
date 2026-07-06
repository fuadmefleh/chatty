"""Tests for skills/stocks/analysis.py — LLM-powered market analysis pipeline.

Covers daily market summary generation, news sentiment analysis, and
watchlist alert checks. All LLM calls are mocked to avoid network I/O.
"""
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.stocks import analysis


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_llm_response(content: str, finish_reason: str = "stop"):
    """Build a fake OpenAI-shaped response with the given content."""
    fake_response = MagicMock()
    fake_response.usage = None
    fake_response.choices = [MagicMock(
        message=MagicMock(content=content),
        finish_reason=finish_reason,
    )]
    return fake_response


def _mock_provider_with_content(content: str):
    """Return a mock LLMProvider that returns the given content."""
    provider = MagicMock()
    provider.complete = AsyncMock(return_value=MagicMock(
        content=content,
        tool_calls=[],
        stop_reason="stop",
    ))
    return provider


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


def test_format_stock_rows_basic():
    stocks = [
        {"symbol": "AAPL", "price": 175.50, "change": 2.30, "change_percent": 1.33, "volume": 50000000},
        {"symbol": "TSLA", "price": 240.00, "change": -5.00, "change_percent": -2.04, "volume": 80000000},
    ]
    result = analysis._format_stock_rows(stocks)
    assert "AAPL: $175.50 (+2.30) (+1.33%)" in result
    assert "TSLA: $240.00 (-5.00) (-2.04%)" in result


def test_format_stock_rows_empty():
    assert analysis._format_stock_rows([]) == "(no data)"


def test_format_stock_rows_missing_keys():
    stocks = [{"symbol": "XYZ"}]
    result = analysis._format_stock_rows(stocks)
    assert "XYZ: $0.00 (+0.00) (+0.00%)" in result


def test_format_news_items_basic():
    articles = [
        {"title": "AAPL Soars", "snippet": "Apple shares rally on earnings beat", "source": "CNBC"},
        {"title": "TSLA Slips", "snippet": "Tesla stock drops after delivery miss", "source": "Bloomberg"},
    ]
    result = analysis._format_news_items(articles)
    assert "- AAPL Soars (CNBC): Apple shares rally on earnings beat" in result
    assert "- TSLA Slips (Bloomberg): Tesla stock drops after delivery miss" in result


def test_format_news_items_empty():
    assert analysis._format_news_items([]) == "(no articles)"


def test_format_news_items_snippet_truncation():
    long_snippet = "A" * 300
    articles = [{"title": "Long", "snippet": long_snippet, "source": "X"}]
    result = analysis._format_news_items(articles)
    # Snippet should be truncated to 200 chars
    assert len(result.split(": ", 1)[1]) <= 210  # title + source prefix + 200


def test_extract_json_plain_object():
    text = '{"sentiment": "positive", "confidence": 0.9}'
    result = analysis._extract_json(text)
    assert result == {"sentiment": "positive", "confidence": 0.9}


def test_extract_json_wrapped_in_prose():
    text = "Here's the result: {\"sentiment\": \"negative\", \"confidence\": 0.8} Hope that helps!"
    result = analysis._extract_json(text)
    assert result == {"sentiment": "negative", "confidence": 0.8}


def test_extract_json_code_fence():
    text = '```json\n{"sentiment": "neutral"}\n```'
    result = analysis._extract_json(text)
    assert result == {"sentiment": "neutral"}


def test_extract_json_garbage():
    assert analysis._extract_json("not json at all") is None


def test_extract_json_list_rejected():
    # _extract_json expects a dict, not a list
    assert analysis._extract_json('["a", "b"]') is None


# ---------------------------------------------------------------------------
# _extract_json_array
# ---------------------------------------------------------------------------


def test_extract_json_array_plain():
    assert analysis._extract_json_array('["a", "b"]') == ["a", "b"]


def test_extract_json_array_wrapped_in_prose():
    text = 'Here: [{"symbol": "AAPL"}] done.'
    result = analysis._extract_json_array(text)
    assert result == [{"symbol": "AAPL"}]


def test_extract_json_array_code_fence():
    text = '```json\n[1, 2, 3]\n```'
    assert analysis._extract_json_array(text) == [1, 2, 3]


def test_extract_json_array_garbage():
    assert analysis._extract_json_array("not json at all") is None


def test_extract_json_array_dict_rejected():
    assert analysis._extract_json_array('{"a": 1}') is None


# ---------------------------------------------------------------------------
# generate_daily_market_summary
# ---------------------------------------------------------------------------


async def test_generate_daily_market_summary_success():
    fake_summary = (
        "Today's market showed mixed signals. Tech stocks led gains with AAPL "
        "up 2%. Meanwhile, energy stocks declined. Volume was above average."
    )
    mock_provider = _mock_provider_with_content(fake_summary)

    stocks_data = {
        "timestamp": "2026-01-15T10:00:00",
        "gainers": [
            {"symbol": "AAPL", "price": 180.0, "change": 3.5, "change_percent": 2.0, "volume": 60000000},
        ],
        "losers": [
            {"symbol": "XOM", "price": 100.0, "change": -2.0, "change_percent": -2.0, "volume": 20000000},
        ],
        "most_active": [
            {"symbol": "TSLA", "price": 250.0, "change": 1.0, "change_percent": 0.4, "volume": 90000000},
        ],
    }

    with patch("skills.stocks.analysis.get_llm_provider", return_value=mock_provider):
        result = await analysis.generate_daily_market_summary(stocks_data)

    assert result["success"] is True
    assert result["summary"] == fake_summary
    assert "generated_at" in result
    assert result["stock_count"] == 3


async def test_generate_daily_market_summary_error():
    mock_provider = MagicMock()
    mock_provider.complete = AsyncMock(side_effect=Exception("API timeout"))

    with patch("skills.stocks.analysis.get_llm_provider", return_value=mock_provider):
        result = await analysis.generate_daily_market_summary({
            "gainers": [], "losers": [], "most_active": []
        })

    assert result["success"] is False
    assert "API timeout" in result["error"]


async def test_generate_daily_market_summary_empty_data():
    fake_summary = "Market data is limited today."
    mock_provider = _mock_provider_with_content(fake_summary)

    with patch("skills.stocks.analysis.get_llm_provider", return_value=mock_provider):
        result = await analysis.generate_daily_market_summary({})

    assert result["success"] is True
    assert result["summary"] == fake_summary
    assert result["stock_count"] == 0


async def test_generate_daily_market_summary_empty_llm_response():
    mock_provider = _mock_provider_with_content("")

    with patch("skills.stocks.analysis.get_llm_provider", return_value=mock_provider):
        result = await analysis.generate_daily_market_summary({
            "gainers": [], "losers": [], "most_active": []
        })

    assert result["success"] is True
    assert result["summary"] == "Unable to generate market summary."


# ---------------------------------------------------------------------------
# analyze_news_sentiment
# ---------------------------------------------------------------------------


async def test_analyze_news_sentiment_success_with_price():
    llm_output = json.dumps({
        "sentiment": "positive",
        "confidence": 0.85,
        "summary": "News sentiment is strongly positive driven by earnings beat.",
        "key_themes": ["earnings", "growth"],
        "price_correlation": "Sentiment aligns with the 3% price increase."
    })
    mock_provider = _mock_provider_with_content(llm_output)

    articles = [
        {"title": "AAPL Beats Earnings", "snippet": "Apple reports record revenue", "source": "CNBC", "link": "http://x"},
    ]
    price_data = {"price": 180.0, "change": 5.0, "change_percent": 2.86}

    with patch("skills.stocks.analysis.get_llm_provider", return_value=mock_provider):
        result = await analysis.analyze_news_sentiment("AAPL", articles, price_data=price_data)

    assert result["success"] is True
    assert result["ticker"] == "AAPL"
    assert result["sentiment"] == "positive"
    assert result["confidence"] == 0.85
    assert "positive" in result["summary"]
    assert "earnings" in result["key_themes"]
    assert result["article_count"] == 1


async def test_analyze_news_sentiment_negative():
    llm_output = json.dumps({
        "sentiment": "negative",
        "confidence": 0.72,
        "summary": "Bearish sentiment due to regulatory concerns.",
        "key_themes": ["regulation", "risk"],
        "price_correlation": "Sentiment diverges from recent price gains."
    })
    mock_provider = _mock_provider_with_content(llm_output)

    with patch("skills.stocks.analysis.get_llm_provider", return_value=mock_provider):
        result = await analysis.analyze_news_sentiment(
            "TSLA",
            [{"title": "TSLA Faces Probe", "snippet": "SEC investigates Tesla", "source": "Reuters", "link": "http://y"}],
        )

    assert result["success"] is True
    assert result["sentiment"] == "negative"
    assert result["confidence"] == 0.72


async def test_analyze_news_sentiment_no_articles_no_price():
    mock_provider = _mock_provider_with_content('{"sentiment": "neutral"}')

    with patch("skills.stocks.analysis.get_llm_provider", return_value=mock_provider):
        result = await analysis.analyze_news_sentiment("XYZ", [])

    assert result["success"] is True
    assert result["ticker"] == "XYZ"
    assert result["article_count"] == 0


async def test_analyze_news_sentiment_json_parse_fallback():
    # When the LLM returns prose instead of JSON, we fall back gracefully
    mock_provider = _mock_provider_with_content(
        "The sentiment seems mostly positive based on the articles."
    )

    with patch("skills.stocks.analysis.get_llm_provider", return_value=mock_provider):
        result = await analysis.analyze_news_sentiment(
            "AAPL",
            [{"title": "Test", "snippet": "Test", "source": "X", "link": "http://x"}],
        )

    assert result["success"] is True
    assert result["sentiment"] == "neutral"  # fallback default
    assert "positive" in result["summary"]
    assert "raw_llm_response" in result


async def test_analyze_news_sentiment_error():
    mock_provider = MagicMock()
    mock_provider.complete = AsyncMock(side_effect=Exception("network error"))

    with patch("skills.stocks.analysis.get_llm_provider", return_value=mock_provider):
        result = await analysis.analyze_news_sentiment("AAPL", [])

    assert result["success"] is False
    assert "network error" in result["error"]
    assert result["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# check_watchlist_alerts
# ---------------------------------------------------------------------------


async def test_check_watchlist_alerts_flags_large_move():
    watchlist = [
        {
            "symbol": "AAPL", "name": "Apple Inc",
            "price": 180.0, "change": 10.0, "change_percent": 5.88,
            "volume": 60000000, "avg_volume": 50000000,
        },
        {
            "symbol": "MSFT", "name": "Microsoft",
            "price": 400.0, "change": 1.0, "change_percent": 0.25,
            "volume": 20000000, "avg_volume": 18000000,
        },
    ]

    # LLM returns alert messages as a JSON array
    llm_output = json.dumps([
        {"symbol": "AAPL", "alert": "Apple surges 5.9% on strong earnings guidance."}
    ])
    mock_provider = _mock_provider_with_content(llm_output)

    with patch("skills.stocks.analysis.get_llm_provider", return_value=mock_provider):
        result = await analysis.check_watchlist_alerts(watchlist, threshold_percent=5.0)

    assert result["success"] is True
    assert result["flagged_count"] == 1
    assert result["checked_count"] == 2
    assert len(result["alerts"]) == 1
    assert result["alerts"][0]["symbol"] == "AAPL"
    assert "surges" in result["alerts"][0]["alert"].lower()


async def test_check_watchlist_alerts_flags_unusual_volume():
    watchlist = [
        {
            "symbol": "TSLA", "name": "Tesla",
            "price": 250.0, "change": 2.0, "change_percent": 0.8,
            "volume": 100000000, "avg_volume": 40000000,
        },
    ]

    llm_output = json.dumps([
        {"symbol": "TSLA", "alert": "Tesla sees heavy trading volume."}
    ])
    mock_provider = _mock_provider_with_content(llm_output)

    with patch("skills.stocks.analysis.get_llm_provider", return_value=mock_provider):
        result = await analysis.check_watchlist_alerts(watchlist, threshold_percent=5.0)

    # Volume is 2.5x avg, so it should be flagged even though price move < 5%
    assert result["success"] is True
    assert result["flagged_count"] == 1
    assert len(result["alerts"]) == 1
    assert result["alerts"][0]["symbol"] == "TSLA"


async def test_check_watchlist_alerts_no_flags():
    watchlist = [
        {
            "symbol": "AAPL", "name": "Apple Inc",
            "price": 180.0, "change": 0.5, "change_percent": 0.28,
            "volume": 50000000, "avg_volume": 48000000,
        },
    ]

    with patch("skills.stocks.analysis.get_llm_provider"):
        result = await analysis.check_watchlist_alerts(watchlist, threshold_percent=5.0)

    assert result["success"] is True
    assert result["alerts"] == []
    assert result["checked_count"] == 1
    # Should not call LLM when nothing is flagged
    # (no mock_provider needed since it short-circuits)


async def test_check_watchlist_alerts_both_reasons():
    watchlist = [
        {
            "symbol": "NVDA", "name": "NVIDIA",
            "price": 800.0, "change": -50.0, "change_percent": -5.88,
            "volume": 90000000, "avg_volume": 30000000,
        },
    ]

    llm_output = json.dumps([
        {"symbol": "NVDA", "alert": "NVIDIA plunges 5.9% on chip shortage fears amid heavy volume."}
    ])
    mock_provider = _mock_provider_with_content(llm_output)

    with patch("skills.stocks.analysis.get_llm_provider", return_value=mock_provider):
        result = await analysis.check_watchlist_alerts(watchlist, threshold_percent=5.0)

    assert result["flagged_count"] == 1
    alert = result["alerts"][0]
    assert len(alert["reasons"]) == 2  # price threshold + unusual volume
    assert any("Price moved" in r for r in alert["reasons"])
    assert any("Unusual volume" in r for r in alert["reasons"])


async def test_check_watchlist_alerts_custom_threshold():
    watchlist = [
        {
            "symbol": "AAPL", "name": "Apple Inc",
            "price": 180.0, "change": 3.0, "change_percent": 1.67,
            "volume": 50000000, "avg_volume": 48000000,
        },
    ]

    llm_output = json.dumps([
        {"symbol": "AAPL", "alert": "Apple up 1.7%."}
    ])
    mock_provider = _mock_provider_with_content(llm_output)

    with patch("skills.stocks.analysis.get_llm_provider", return_value=mock_provider):
        result = await analysis.check_watchlist_alerts(watchlist, threshold_percent=1.5)

    assert result["flagged_count"] == 1


async def test_check_watchlist_alerts_llm_parse_fallback():
    """When LLM returns unparseable output, we generate simple alerts."""
    watchlist = [
        {
            "symbol": "AAPL", "name": "Apple Inc",
            "price": 180.0, "change": 10.0, "change_percent": 5.88,
            "volume": 60000000, "avg_volume": 50000000,
        },
    ]

    # LLM returns prose, not JSON array
    mock_provider = _mock_provider_with_content("Apple is really up today!")

    with patch("skills.stocks.analysis.get_llm_provider", return_value=mock_provider):
        result = await analysis.check_watchlist_alerts(watchlist, threshold_percent=5.0)

    assert result["success"] is True
    assert len(result["alerts"]) == 1
    assert result["alerts"][0]["symbol"] == "AAPL"
    # Fallback alert should contain the symbol and direction
    assert "up" in result["alerts"][0]["alert"].lower()


async def test_check_watchlist_alerts_empty_watchlist():
    with patch("skills.stocks.analysis.get_llm_provider"):
        result = await analysis.check_watchlist_alerts([])

    assert result["success"] is True
    assert result["alerts"] == []
    assert result["checked_count"] == 0


async def test_check_watchlist_alerts_error():
    mock_provider = MagicMock()
    mock_provider.complete = AsyncMock(side_effect=Exception("boom"))

    watchlist = [
        {
            "symbol": "AAPL", "name": "Apple Inc",
            "price": 180.0, "change": 10.0, "change_percent": 5.88,
            "volume": 60000000, "avg_volume": 50000000,
        },
    ]

    with patch("skills.stocks.analysis.get_llm_provider", return_value=mock_provider):
        result = await analysis.check_watchlist_alerts(watchlist, threshold_percent=5.0)

    assert result["success"] is False
    assert "boom" in result["error"]
    assert result["checked_count"] == 1
