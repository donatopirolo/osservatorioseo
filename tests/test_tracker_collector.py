"""Tests for tracker collector orchestration.

Uses AsyncMock to stub RadarClient and PagesAnalyticsClient so we don't
need real HTTP.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from osservatorio_seo.tracker.collector import TrackerCollector
from osservatorio_seo.tracker.models import (
    AnalyticsReferrer,
    DomainRank,
    IndexTimeseries,
    TimeseriesPoint,
    TrackerSnapshot,
)


@pytest.fixture
def fake_radar():
    client = AsyncMock()

    client.top_domains.side_effect = lambda category, location, limit=10, **kw: {
        ("ai", "IT"): [
            DomainRank(domain="chat.openai.com", rank=1),
            DomainRank(domain="gemini.google.com", rank=2),
            DomainRank(domain="claude.ai", rank=3),
            DomainRank(domain="perplexity.ai", rank=4),
            DomainRank(domain="character.ai", rank=5),
        ],
        ("search_engines", "IT"): [
            DomainRank(domain="google.com", rank=1),
            DomainRank(domain="bing.com", rank=2),
            DomainRank(domain="duckduckgo.com", rank=3),
        ],
    }[(category, location)]

    # Simple timeseries stubs
    base_points = [
        TimeseriesPoint(
            date=datetime(2024 + i // 12, (i % 12) + 1, 1, tzinfo=UTC), value=100 + i * 2
        )
        for i in range(24)
    ]
    client.category_timeseries.return_value = IndexTimeseries(label="ai", points=base_points)
    client.domain_timeseries.return_value = IndexTimeseries(
        label="domain", points=base_points[-24:]
    )

    return client


@pytest.fixture
def fake_pages_analytics():
    client = AsyncMock()
    client.referrer_share.return_value = [
        AnalyticsReferrer(source="Google", share_pct=79.7),
        AnalyticsReferrer(source="Direct", share_pct=17.3),
        AnalyticsReferrer(source="ChatGPT", share_pct=0.6),
        AnalyticsReferrer(source="Claude", share_pct=0.2),
    ]
    return client


@pytest.mark.asyncio
async def test_collect_builds_complete_snapshot(fake_radar, fake_pages_analytics):
    collector = TrackerCollector(
        radar=fake_radar,
        pages_analytics=fake_pages_analytics,
        location="IT",
    )
    snapshot = await collector.collect(year=2026, week=15)

    assert isinstance(snapshot, TrackerSnapshot)
    assert snapshot.year == 2026
    assert snapshot.week == 15
    assert len(snapshot.ai_top10_current) == 5
    assert snapshot.ai_top10_current[0].domain == "chat.openai.com"
    assert len(snapshot.search_top5_current) == 3
    assert snapshot.own_referrers_30d[0].source == "Google"
    # Metadata tracks calls
    assert snapshot.metadata.radar_calls > 0
    assert snapshot.metadata.pages_analytics_calls == 1


@pytest.mark.asyncio
async def test_collect_is_robust_to_partial_failures(fake_radar, fake_pages_analytics):
    """If pages analytics fails, snapshot is still built with a warning."""
    fake_pages_analytics.referrer_share.side_effect = Exception("boom")

    collector = TrackerCollector(
        radar=fake_radar,
        pages_analytics=fake_pages_analytics,
        location="IT",
    )
    snapshot = await collector.collect(year=2026, week=15)
    assert snapshot.own_referrers_30d == []
    assert any("pages_analytics" in w.lower() for w in snapshot.metadata.warnings)


def test_persist_writes_json_to_snapshots_dir(tmp_path):
    """persist() writes snapshot to data/tracker/snapshots/<YYYY-WNN>.json."""
    snapshot = TrackerSnapshot(
        year=2026,
        week=15,
        generated_at=datetime(2026, 4, 14, 8, 0, tzinfo=UTC),
        ai_index_24mo=IndexTimeseries(label="ai"),
        internet_index_24mo=IndexTimeseries(label="internet"),
        bump_chart_6mo={"domains": [], "weeks": []},
        top_movers_30d={"up": [], "down": []},
        metadata={"radar_calls": 5, "pages_analytics_calls": 1},
    )
    TrackerCollector.persist(snapshot, base_dir=tmp_path)

    target = tmp_path / "snapshots" / "2026-W15.json"
    assert target.exists()
    content = target.read_text()
    assert '"week": 15' in content
