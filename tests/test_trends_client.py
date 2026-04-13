"""Tests for Google Trends client wrapper."""

import sys
import types
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# Inject a stub trendspy module so the lazy import inside TrendsClient works
# even when trendspy is not installed in the current environment.
if "trendspy" not in sys.modules:
    _stub = types.ModuleType("trendspy")
    _stub.Trends = MagicMock()
    sys.modules["trendspy"] = _stub

from osservatorio_seo.tracker.trends_client import TrendsClient


class TestTrendsClient:
    def test_fetch_interest_returns_keywords_and_points(self):
        mock_df = MagicMock()
        mock_df.columns = ["ChatGPT", "Claude AI", "isPartial"]
        mock_df.__len__ = lambda self: 2
        mock_df.iterrows.return_value = iter([
            (datetime(2026, 4, 6), {"ChatGPT": 100, "Claude AI": 12}),
            (datetime(2026, 4, 13), {"ChatGPT": 95, "Claude AI": 14}),
        ])

        with patch("trendspy.Trends") as MockTrends:
            mock_instance = MockTrends.return_value
            mock_instance.interest_over_time.return_value = mock_df

            client = TrendsClient(request_delay=0.0)
            keywords, points = client.fetch_interest(
                keywords=["ChatGPT", "Claude AI"],
                geo="IT",
                timeframe="today 12-m",
            )

        assert keywords == ["ChatGPT", "Claude AI"]
        assert len(points) == 2
        assert points[0]["date"] == datetime(2026, 4, 6)
        assert points[0]["values"]["ChatGPT"] == 100
        assert points[0]["values"]["Claude AI"] == 12

    def test_fetch_interest_returns_empty_on_error(self):
        with patch("trendspy.Trends") as MockTrends:
            mock_instance = MockTrends.return_value
            mock_instance.interest_over_time.side_effect = Exception("429 Too Many Requests")

            client = TrendsClient(request_delay=0.0)
            keywords, points = client.fetch_interest(
                keywords=["ChatGPT"],
                geo="IT",
            )

        assert keywords == []
        assert points == []

    def test_default_keywords(self):
        assert len(TrendsClient.DEFAULT_KEYWORDS) == 5
        assert "ChatGPT" in TrendsClient.DEFAULT_KEYWORDS
