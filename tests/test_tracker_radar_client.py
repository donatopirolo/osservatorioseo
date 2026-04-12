"""Tests for Cloudflare Radar API client."""

import json
import re
from pathlib import Path

import pytest

from osservatorio_seo.tracker.radar_client import RadarClient, RadarClientError


@pytest.fixture
def api_token() -> str:
    return "test-token-not-real"


@pytest.fixture
def radar_top_ai(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "radar_ranking_top_ai_it.json").read_text())


@pytest.fixture
def radar_timeseries_ai(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "radar_ranking_timeseries_ai_it.json").read_text())


@pytest.mark.asyncio
async def test_top_domains_ai_italy(httpx_mock, api_token, radar_top_ai):
    httpx_mock.add_response(
        url="https://api.cloudflare.com/client/v4/radar/ranking/top?limit=10&location=IT&name=ai&dateRange=1w",
        json=radar_top_ai,
    )

    client = RadarClient(api_token=api_token)
    result = await client.top_domains(category="ai", location="IT", limit=10)

    assert len(result) == 5
    assert result[0].domain == "chat.openai.com"
    assert result[0].rank == 1
    assert result[2].domain == "claude.ai"


@pytest.mark.asyncio
async def test_ranking_timeseries(httpx_mock, api_token, radar_timeseries_ai):
    httpx_mock.add_response(
        url=re.compile(r".*radar/ranking/timeseries_groups.*"),
        json=radar_timeseries_ai,
    )

    client = RadarClient(api_token=api_token)
    result = await client.category_timeseries(category="ai", location="IT", date_range="2y")

    assert result.label == "ai"
    assert len(result.points) == 3
    assert result.points[0].value == 100.0
    assert result.points[2].value == 105.1


@pytest.mark.asyncio
async def test_client_error_on_non_200(httpx_mock, api_token):
    httpx_mock.add_response(
        url=re.compile(r".*radar/ranking/top.*"),
        status_code=500,
        json={"success": False, "errors": [{"message": "server error"}]},
    )

    client = RadarClient(api_token=api_token)
    with pytest.raises(RadarClientError) as exc_info:
        await client.top_domains(category="ai", location="IT")
    assert "500" in str(exc_info.value)


@pytest.mark.asyncio
async def test_client_error_on_non_success(httpx_mock, api_token):
    httpx_mock.add_response(
        url=re.compile(r".*radar/ranking/top.*"),
        json={"success": False, "errors": [{"message": "bad request"}]},
    )

    client = RadarClient(api_token=api_token)
    with pytest.raises(RadarClientError) as exc_info:
        await client.top_domains(category="ai", location="IT")
    assert "bad request" in str(exc_info.value)
