"""Client wrapper for Google Trends via trendspy.

Provides a simple interface to fetch interest-over-time data
for AI platform keywords, with graceful error handling.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_KEYWORDS = ["ChatGPT", "Claude AI", "Perplexity", "Gemini AI", "DeepSeek"]


class TrendsClient:
    """Wrapper around trendspy for fetching Google Trends data."""

    DEFAULT_KEYWORDS = DEFAULT_KEYWORDS

    def __init__(self, request_delay: float = 5.0) -> None:
        self._request_delay = request_delay

    def fetch_interest(
        self,
        *,
        keywords: list[str] | None = None,
        geo: str = "",
        timeframe: str = "today 12-m",
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """Fetch interest-over-time for keywords.

        Returns (keywords_list, points_list) where each point is
        {date: datetime, values: {keyword: int}}.

        On any error (rate limit, network, etc.) returns ([], []).
        """
        from trendspy import Trends

        kws = keywords or self.DEFAULT_KEYWORDS

        try:
            tr = Trends(request_delay=self._request_delay)
            df = tr.interest_over_time(kws, geo=geo, timeframe=timeframe)
        except Exception:
            logger.warning("Google Trends fetch failed for geo=%s", geo, exc_info=True)
            return [], []

        if len(df) == 0:
            return [], []

        value_cols = [c for c in df.columns if c != "isPartial"]
        points: list[dict[str, Any]] = []
        for date_idx, row in df.iterrows():
            dt = date_idx if isinstance(date_idx, datetime) else datetime.fromisoformat(str(date_idx))
            values = {col: int(row[col]) for col in value_cols}
            points.append({"date": dt, "values": values})

        return value_cols, points
