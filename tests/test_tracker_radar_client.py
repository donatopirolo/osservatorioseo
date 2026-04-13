"""Tests for Cloudflare Radar API client (v2 endpoints)."""

import json
import re
from pathlib import Path

import pytest

from osservatorio_seo.tracker.radar_client import RadarClient, RadarClientError


@pytest.fixture
def api_token() -> str:
    return "test-token-not-real"


@pytest.fixture
def client(api_token: str) -> RadarClient:
    return RadarClient(api_token=api_token)


@pytest.fixture
def radar_ranking_top(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "radar_v2_ranking_top.json").read_text())


@pytest.fixture
def radar_domain_detail(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "radar_v2_domain_detail.json").read_text())


@pytest.fixture
def radar_timeseries(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "radar_v2_timeseries.json").read_text())


@pytest.fixture
def radar_bot_class(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "radar_v2_bot_class.json").read_text())


@pytest.fixture
def radar_ai_bots_ua(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "radar_v2_ai_bots_ua.json").read_text())


@pytest.fixture
def radar_crawl_purpose(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "radar_v2_crawl_purpose.json").read_text())


@pytest.fixture
def radar_industry(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "radar_v2_industry.json").read_text())


@pytest.fixture
def radar_device_type(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "radar_v3_device_type.json").read_text())


@pytest.fixture
def radar_os(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "radar_v3_os.json").read_text())


# ---------------------------------------------------------------------------
# ranking_top
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ranking_top_returns_list(httpx_mock, client, radar_ranking_top):
    httpx_mock.add_response(
        url=re.compile(r".*radar/ranking/top.*"),
        json=radar_ranking_top,
    )

    result = await client.ranking_top(location="IT", limit=3)

    assert len(result) == 3
    assert result[0]["rank"] == 1
    assert result[0]["domain"] == "google.com"
    assert result[2]["domain"] == "chatgpt.com"
    # categories list preserved
    assert isinstance(result[0]["categories"], list)
    assert result[0]["categories"][0] == "Search Engines"


@pytest.mark.asyncio
async def test_ranking_top_no_location(httpx_mock, client, radar_ranking_top):
    """When location is None the param must not be sent (global data)."""
    httpx_mock.add_response(
        url=re.compile(r".*radar/ranking/top.*"),
        json=radar_ranking_top,
    )

    result = await client.ranking_top(limit=3)
    assert len(result) == 3


# ---------------------------------------------------------------------------
# domain_detail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_domain_detail_rank_and_bucket(httpx_mock, client, radar_domain_detail):
    httpx_mock.add_response(
        url=re.compile(r".*radar/ranking/domain/google\.com.*"),
        json=radar_domain_detail,
    )

    result = await client.domain_detail(domain="google.com")

    assert result["rank"] == 10
    # bucket must always be a string
    assert isinstance(result["bucket"], str)
    assert result["bucket"] == "200"


@pytest.mark.asyncio
async def test_domain_detail_bucket_string_passthrough(httpx_mock, client):
    """Bucket already a string (e.g. '>200000') must pass through as-is."""
    payload = {
        "success": True,
        "result": {
            "meta": {},
            "details_0": {"rank": None, "bucket": ">200000", "categories": []},
        },
    }
    httpx_mock.add_response(
        url=re.compile(r".*radar/ranking/domain/.*"),
        json=payload,
    )

    result = await client.domain_detail(domain="obscure.example")
    assert result["rank"] is None
    assert result["bucket"] == ">200000"


# ---------------------------------------------------------------------------
# domain_timeseries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_domain_timeseries_points(httpx_mock, client, radar_timeseries):
    httpx_mock.add_response(
        url=re.compile(r".*radar/ranking/timeseries_groups.*"),
        json=radar_timeseries,
    )

    result = await client.domain_timeseries(domain="google.com")

    assert len(result) == 3
    assert result[0]["date"] == "2026-03-30T00:00:00Z"
    assert result[0]["rank"] == 1


# ---------------------------------------------------------------------------
# bot_human_timeseries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bot_human_timeseries(httpx_mock, client, radar_bot_class):
    httpx_mock.add_response(
        url=re.compile(r".*radar/http/timeseries_groups/bot_class.*"),
        json=radar_bot_class,
    )

    result = await client.bot_human_timeseries(location="IT")

    assert len(result) == 2
    assert result[0]["date"] == "2026-03-30T00:00:00Z"
    assert result[0]["human_pct"] == pytest.approx(83.3)
    assert result[0]["bot_pct"] == pytest.approx(16.7)
    assert result[1]["human_pct"] == pytest.approx(82.8)
    assert result[1]["bot_pct"] == pytest.approx(17.2)


# ---------------------------------------------------------------------------
# ai_bots_user_agent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ai_bots_user_agent(httpx_mock, client, radar_ai_bots_ua):
    httpx_mock.add_response(
        url=re.compile(r".*radar/ai/bots/timeseries_groups/user_agent.*"),
        json=radar_ai_bots_ua,
    )

    agents, points = await client.ai_bots_user_agent(location="IT")

    assert set(agents) == {"Googlebot", "GPTBot", "ClaudeBot"}
    assert len(points) == 2
    assert points[0]["date"] == "2026-03-30T00:00:00Z"
    assert points[0]["values"]["Googlebot"] == pytest.approx(32.0)
    assert points[0]["values"]["GPTBot"] == pytest.approx(8.9)
    assert points[0]["values"]["ClaudeBot"] == pytest.approx(11.9)
    assert points[1]["values"]["Googlebot"] == pytest.approx(33.3)


# ---------------------------------------------------------------------------
# crawl_purpose
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crawl_purpose(httpx_mock, client, radar_crawl_purpose):
    httpx_mock.add_response(
        url=re.compile(r".*radar/ai/bots/timeseries_groups/crawl_purpose.*"),
        json=radar_crawl_purpose,
    )

    purposes, points = await client.crawl_purpose(location="IT")

    assert set(purposes) == {"Training", "Mixed Purpose", "Search", "User Action", "Undeclared"}
    assert len(points) == 2
    assert points[0]["date"] == "2026-03-30T00:00:00Z"
    assert points[0]["values"]["Training"] == pytest.approx(50.7)
    assert points[1]["values"]["Training"] == pytest.approx(48.2)


# ---------------------------------------------------------------------------
# industry_summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_industry_summary_sorted_desc_other_last(httpx_mock, client, radar_industry):
    httpx_mock.add_response(
        url=re.compile(r".*radar/ai/bots/summary/industry.*"),
        json=radar_industry,
    )

    result = await client.industry_summary(location="IT")

    # "other" must be last
    assert result[-1]["industry"] == "other"
    # remaining entries sorted descending by pct
    non_other = [r for r in result if r["industry"] != "other"]
    pcts = [r["pct"] for r in non_other]
    assert pcts == sorted(pcts, reverse=True)
    # first entry is Retail
    assert non_other[0]["industry"] == "Retail"
    assert abs(non_other[0]["pct"] - 28.709574) < 1e-5


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_error_on_non_200(httpx_mock, client):
    httpx_mock.add_response(
        url=re.compile(r".*radar/ranking/top.*"),
        status_code=500,
        json={"success": False, "errors": [{"message": "internal server error"}]},
    )

    with pytest.raises(RadarClientError) as exc_info:
        await client.ranking_top(limit=5)
    assert "500" in str(exc_info.value)


@pytest.mark.asyncio
async def test_error_on_success_false(httpx_mock, client):
    httpx_mock.add_response(
        url=re.compile(r".*radar/ranking/top.*"),
        json={"success": False, "errors": [{"message": "bad token"}]},
    )

    with pytest.raises(RadarClientError) as exc_info:
        await client.ranking_top()
    assert "bad token" in str(exc_info.value)


# ---------------------------------------------------------------------------
# device_type_timeseries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_device_type_timeseries(httpx_mock, client, radar_device_type):
    httpx_mock.add_response(
        url=re.compile(r".*radar/http/timeseries_groups/device_type.*"),
        json=radar_device_type,
    )

    result = await client.device_type_timeseries(location="IT")

    assert len(result) == 2
    assert result[0]["date"] == "2026-03-30T00:00:00Z"
    assert result[0]["mobile_pct"] == pytest.approx(51.2)
    assert result[0]["desktop_pct"] == pytest.approx(48.8)
    assert result[1]["mobile_pct"] == pytest.approx(50.1)
    assert result[1]["desktop_pct"] == pytest.approx(49.9)


@pytest.mark.asyncio
async def test_device_type_timeseries_no_location(httpx_mock, client, radar_device_type):
    httpx_mock.add_response(
        url=re.compile(r".*radar/http/timeseries_groups/device_type.*"),
        json=radar_device_type,
    )

    result = await client.device_type_timeseries()
    assert len(result) == 2


# ---------------------------------------------------------------------------
# os_summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_os_summary_sorted_desc_other_last(httpx_mock, client, radar_os):
    httpx_mock.add_response(
        url=re.compile(r".*radar/http/summary/os.*"),
        json=radar_os,
    )

    result = await client.os_summary(location="IT")

    # "other" must be last
    assert result[-1]["os"] == "other"
    assert result[-1]["pct"] == pytest.approx(0.4)
    # remaining entries sorted descending by pct
    non_other = [r for r in result if r["os"] != "other"]
    pcts = [r["pct"] for r in non_other]
    assert pcts == sorted(pcts, reverse=True)
    # top entry is ANDROID
    assert non_other[0]["os"] == "ANDROID"
    assert non_other[0]["pct"] == pytest.approx(38.5)


@pytest.mark.asyncio
async def test_os_summary_no_location(httpx_mock, client, radar_os):
    httpx_mock.add_response(
        url=re.compile(r".*radar/http/summary/os.*"),
        json=radar_os,
    )

    result = await client.os_summary()
    assert len(result) == 6  # 5 named OSes + "other"
