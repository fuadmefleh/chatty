"""SQLite-backed tracking of LLM token usage across every provider and call site.

LLM providers (src/core/llm/*_provider.py) call record() directly whenever a
response carries usage data, so every caller - the Telegram bot's
StagedReACTAgent, the web dashboard's WebChatAgent, vision analysis - is
covered automatically without each of them needing to know about tracking.
"""
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# USD per 1M tokens (input, output). Best-effort estimates for cost display -
# unknown models simply show no cost rather than a wrong one.
_PRICING_PER_MILLION = {
    "claude-fable-5": (10.00, 50.00),
    "claude-mythos-5": (10.00, 50.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-opus-4-6": (5.00, 25.00),
    "claude-opus-4-5": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "gpt-4-turbo-preview": (10.00, 30.00),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}


def _estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> Optional[float]:
    pricing = _PRICING_PER_MILLION.get(model)
    if pricing is None:
        return None
    input_price, output_price = pricing
    return (prompt_tokens / 1_000_000) * input_price + (completion_tokens / 1_000_000) * output_price


class TokenUsageManager:
    """SQLite log of every LLM request's token usage, with cheap aggregate queries."""

    def __init__(self, db_path: str = "data/token_usage/token_usage.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._create_tables()

    def _create_tables(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL
            )
        """)
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_token_usage_timestamp ON token_usage(timestamp)"
        )
        self.conn.commit()

    def record(self, provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        self.conn.execute(
            """INSERT INTO token_usage
               (timestamp, provider, model, prompt_tokens, completion_tokens, total_tokens)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                provider,
                model,
                prompt_tokens,
                completion_tokens,
                prompt_tokens + completion_tokens,
            ),
        )
        self.conn.commit()

    def get_summary(self, days: int = 30) -> Dict[str, Any]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        today = datetime.now(timezone.utc).date().isoformat()

        prompt_total, completion_total, total_total, request_count = self.conn.execute(
            """SELECT COALESCE(SUM(prompt_tokens), 0), COALESCE(SUM(completion_tokens), 0),
                      COALESCE(SUM(total_tokens), 0), COUNT(*)
               FROM token_usage WHERE timestamp >= ?""",
            (cutoff,),
        ).fetchone()

        today_total, today_count = self.conn.execute(
            """SELECT COALESCE(SUM(total_tokens), 0), COUNT(*)
               FROM token_usage WHERE date(timestamp) = ?""",
            (today,),
        ).fetchone()

        by_model_rows = self.conn.execute(
            """SELECT provider, model, COALESCE(SUM(prompt_tokens), 0), COALESCE(SUM(completion_tokens), 0),
                      COALESCE(SUM(total_tokens), 0), COUNT(*)
               FROM token_usage WHERE timestamp >= ?
               GROUP BY provider, model ORDER BY 5 DESC""",
            (cutoff,),
        ).fetchall()

        by_day_rows = self.conn.execute(
            """SELECT date(timestamp) AS day, COALESCE(SUM(prompt_tokens), 0),
                      COALESCE(SUM(completion_tokens), 0), COALESCE(SUM(total_tokens), 0)
               FROM token_usage WHERE timestamp >= ?
               GROUP BY day ORDER BY day""",
            (cutoff,),
        ).fetchall()

        by_model = []
        total_cost_usd = 0.0
        unpriced_model_count = 0
        for provider, model, prompt_tokens, completion_tokens, total_tokens, count in by_model_rows:
            cost = _estimate_cost_usd(model, prompt_tokens, completion_tokens)
            if cost is None:
                unpriced_model_count += 1
            else:
                total_cost_usd += cost
            by_model.append({
                "provider": provider,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "request_count": count,
                "estimated_cost_usd": cost,
            })

        return {
            "range_days": days,
            "total_prompt_tokens": prompt_total,
            "total_completion_tokens": completion_total,
            "total_tokens": total_total,
            "request_count": request_count,
            "today_total_tokens": today_total,
            "today_request_count": today_count,
            "total_estimated_cost_usd": total_cost_usd,
            "unpriced_model_count": unpriced_model_count,
            "by_model": by_model,
            "by_day": [
                {"day": day, "prompt_tokens": p, "completion_tokens": c, "total_tokens": t}
                for day, p, c, t in by_day_rows
            ],
        }

    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT timestamp, provider, model, prompt_tokens, completion_tokens, total_tokens
               FROM token_usage ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [
            {
                "timestamp": timestamp,
                "provider": provider,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
            for timestamp, provider, model, prompt_tokens, completion_tokens, total_tokens in rows
        ]


_manager_singleton: Optional[TokenUsageManager] = None


def get_token_usage_manager() -> TokenUsageManager:
    global _manager_singleton
    if _manager_singleton is None:
        _manager_singleton = TokenUsageManager()
    return _manager_singleton
