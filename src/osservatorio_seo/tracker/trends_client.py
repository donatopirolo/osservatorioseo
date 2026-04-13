"""Client for Google Trends data via DataForSEO API.

Provides interest-over-time data for AI platform keywords,
comparing Italy vs global search interest.

Docs: https://docs.dataforseo.com/v3/keywords_data/google_trends/explore/live/
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_KEYWORDS = ["ChatGPT", "Claude AI", "Perplexity", "Gemini AI", "DeepSeek"]

# DataForSEO location code for Italy
_LOCATION_IT = 2380


class TrendsClient:
    """Wrapper around DataForSEO Google Trends endpoint."""

    DEFAULT_KEYWORDS = DEFAULT_KEYWORDS

    def __init__(self, api_key: str, timeout_s: int = 30) -> None:
        self._api_key = api_key
        self._timeout = timeout_s

    def fetch_interest(
        self,
        *,
        keywords: list[str] | None = None,
        geo: str = "",
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """Fetch interest-over-time for keywords.

        Args:
            keywords: Up to 5 keywords to compare. Defaults to DEFAULT_KEYWORDS.
            geo: "IT" for Italy, "" for worldwide.

        Returns (keywords_list, points_list) where each point is
        {date: datetime, values: {keyword: int}}.

        On any error returns ([], []).
        """
        kws = keywords or self.DEFAULT_KEYWORDS

        payload: dict[str, Any] = {
            "keywords": kws,
            "type": "web",
            "date_from": (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"),
            "date_to": datetime.now().strftime("%Y-%m-%d"),
        }
        if geo.upper() == "IT":
            payload["location_code"] = _LOCATION_IT
            payload["language_code"] = "it"

        try:
            resp = httpx.post(
                "https://api.dataforseo.com/v3/keywords_data/google_trends/explore/live",
                headers={
                    "Authorization": f"Basic {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=[payload],
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            logger.warning("DataForSEO Trends fetch failed for geo=%s", geo, exc_info=True)
            return [], []

        # Parse response
        try:
            task = data["tasks"][0]
            if task["status_code"] != 20000:
                logger.warning("DataForSEO task error: %s", task.get("status_message"))
                return [], []

            items = task["result"][0]["items"]
            graph_item = next(i for i in items if i["type"] == "google_trends_graph")
            raw_points = graph_item["data"]
        except (KeyError, IndexError, StopIteration):
            logger.warning("DataForSEO unexpected response structure for geo=%s", geo)
            return [], []

        points: list[dict[str, Any]] = []
        for dp in raw_points:
            dt = datetime.fromisoformat(dp["date_from"])
            values = {kw: int(v) for kw, v in zip(kws, dp["values"], strict=False)}
            points.append({"date": dt, "values": values})

        return list(kws), points
