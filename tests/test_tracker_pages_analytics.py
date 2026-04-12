"""Tests for Cloudflare Pages Analytics GraphQL client."""

import json
from pathlib import Path

import pytest

from osservatorio_seo.tracker.pages_analytics import (
    PagesAnalyticsClient,
    PagesAnalyticsError,
)


@pytest.fixture
def analytics_payload(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "pages_analytics_referrers.json").read_text())


@pytest.mark.asyncio
async def test_referrer_groups_aggregated_and_normalized(httpx_mock, analytics_payload):
    httpx_mock.add_response(
        url="https://api.cloudflare.com/client/v4/graphql",
        json=analytics_payload,
    )

    client = PagesAnalyticsClient(
        api_token="token",
        account_id="acct",
        zone_id="zone",
    )
    referrers = await client.referrer_share(days=30)

    # Aggregated groups: Google/Bing/DDG/Direct/ChatGPT/Claude/Perplexity/Other
    by_source = {r.source: r.share_pct for r in referrers}
    # google.com + www.google.com = 6520 + 4100 = 10620 of total 13321 = 79.72%
    assert by_source["Google"] == pytest.approx(79.72, abs=0.1)
    # empty referer = 2300 → Direct
    assert by_source["Direct"] == pytest.approx(17.26, abs=0.1)
    # sum of all shares ~ 100
    assert sum(by_source.values()) == pytest.approx(100.0, abs=0.5)


@pytest.mark.asyncio
async def test_error_on_graphql_errors(httpx_mock):
    httpx_mock.add_response(
        url="https://api.cloudflare.com/client/v4/graphql",
        json={"errors": [{"message": "not authorized"}]},
    )
    client = PagesAnalyticsClient(api_token="bad", account_id="acct", zone_id="zone")
    with pytest.raises(PagesAnalyticsError) as exc_info:
        await client.referrer_share(days=30)
    assert "not authorized" in str(exc_info.value)
