"""Tests for DataForSEO Google Trends client wrapper."""

from datetime import datetime
from unittest.mock import MagicMock, patch

from osservatorio_seo.tracker.trends_client import TrendsClient


class TestTrendsClient:
    def test_fetch_interest_returns_keywords_and_points(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "tasks": [
                {
                    "status_code": 20000,
                    "result": [
                        {
                            "items": [
                                {
                                    "type": "google_trends_graph",
                                    "data": [
                                        {
                                            "date_from": "2026-04-06",
                                            "values": [100, 12],
                                        },
                                        {
                                            "date_from": "2026-04-13",
                                            "values": [95, 14],
                                        },
                                    ],
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        with patch("osservatorio_seo.tracker.trends_client.httpx.post", return_value=mock_response):
            client = TrendsClient(api_key="dGVzdDp0ZXN0")
            keywords, points = client.fetch_interest(
                keywords=["ChatGPT", "Claude AI"],
                geo="IT",
            )

        assert keywords == ["ChatGPT", "Claude AI"]
        assert len(points) == 2
        assert points[0]["date"] == datetime(2026, 4, 6)
        assert points[0]["values"]["ChatGPT"] == 100
        assert points[0]["values"]["Claude AI"] == 12

    def test_fetch_interest_returns_empty_on_http_error(self):
        with patch(
            "osservatorio_seo.tracker.trends_client.httpx.post",
            side_effect=Exception("Connection error"),
        ):
            client = TrendsClient(api_key="dGVzdDp0ZXN0")
            keywords, points = client.fetch_interest(keywords=["ChatGPT"], geo="IT")

        assert keywords == []
        assert points == []

    def test_fetch_interest_returns_empty_on_api_error(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "tasks": [{"status_code": 40000, "status_message": "Bad request"}]
        }

        with patch("osservatorio_seo.tracker.trends_client.httpx.post", return_value=mock_response):
            client = TrendsClient(api_key="dGVzdDp0ZXN0")
            keywords, points = client.fetch_interest(keywords=["ChatGPT"], geo="IT")

        assert keywords == []
        assert points == []

    def test_default_keywords(self):
        assert len(TrendsClient.DEFAULT_KEYWORDS) == 5
        assert "ChatGPT" in TrendsClient.DEFAULT_KEYWORDS

    def test_global_fetch_has_no_location(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "tasks": [
                {
                    "status_code": 20000,
                    "result": [
                        {
                            "items": [
                                {
                                    "type": "google_trends_graph",
                                    "data": [
                                        {"date_from": "2026-04-06", "values": [80]},
                                    ],
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        with patch("osservatorio_seo.tracker.trends_client.httpx.post", return_value=mock_response) as mock_post:
            client = TrendsClient(api_key="dGVzdDp0ZXN0")
            client.fetch_interest(keywords=["ChatGPT"], geo="")

        call_payload = mock_post.call_args[1]["json"][0]
        assert "location_code" not in call_payload
