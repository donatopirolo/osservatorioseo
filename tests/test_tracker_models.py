"""Tests for tracker pydantic models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from osservatorio_seo.tracker.models import (
    BumpChartData,
    BumpChartWeek,
    DomainMovement,
    DomainRank,
    IndexTimeseries,
    ReportTakeaway,
    SnapshotMetadata,
    TimeseriesPoint,
    TopMovers,
    TrackerMonthlyReport,
    TrackerSnapshot,
)


def test_domain_rank_computes_delta_rank():
    r = DomainRank(
        domain="chat.openai.com",
        rank=1,
        previous_rank=3,
        traffic_change_pct=12.5,
    )
    assert r.delta_rank == 2  # moved up 2 positions (3 -> 1)


def test_domain_rank_handles_missing_previous_rank():
    r = DomainRank(domain="new.ai", rank=10)
    assert r.previous_rank is None
    assert r.delta_rank is None


def test_timeseries_point_requires_date_and_value():
    p = TimeseriesPoint(date=datetime(2026, 4, 12, tzinfo=UTC), value=42.5)
    assert p.value == 42.5


def test_index_timeseries_is_iterable():
    ts = IndexTimeseries(
        label="AI category Italy",
        points=[
            TimeseriesPoint(date=datetime(2024, 1, 1, tzinfo=UTC), value=100.0),
            TimeseriesPoint(date=datetime(2024, 2, 1, tzinfo=UTC), value=105.2),
        ],
    )
    assert len(ts.points) == 2


def test_bump_chart_data_enforces_domain_consistency():
    data = BumpChartData(
        domains=["a.com", "b.com"],
        weeks=[
            BumpChartWeek(
                week_end=datetime(2026, 3, 1, tzinfo=UTC),
                ranks={"a.com": 1, "b.com": 2},
            ),
        ],
    )
    assert data.weeks[0].ranks["a.com"] == 1


def test_top_movers_respects_max_5_each_side():
    movers = TopMovers(
        up=[DomainMovement(domain=f"d{i}.ai", delta_pct=10.0 + i) for i in range(5)],
        down=[DomainMovement(domain=f"x{i}.ai", delta_pct=-10.0 - i) for i in range(5)],
    )
    assert len(movers.up) == 5
    assert len(movers.down) == 5


def test_top_movers_rejects_more_than_5():
    with pytest.raises(ValidationError):
        TopMovers(
            up=[DomainMovement(domain=f"d{i}.ai", delta_pct=1.0) for i in range(6)],
            down=[],
        )


def test_tracker_snapshot_roundtrip():
    snap = TrackerSnapshot(
        year=2026,
        week=15,
        generated_at=datetime(2026, 4, 14, 8, 0, tzinfo=UTC),
        ai_top10_current=[DomainRank(domain="chat.openai.com", rank=1, previous_rank=1)],
        search_top5_current=[DomainRank(domain="google.com", rank=1, previous_rank=1)],
        ai_index_24mo=IndexTimeseries(label="AI IT", points=[]),
        internet_index_24mo=IndexTimeseries(label="Internet IT", points=[]),
        market_composition_12mo=[],
        bump_chart_6mo=BumpChartData(domains=[], weeks=[]),
        category_heatmap_6mo=[],
        top_movers_30d=TopMovers(up=[], down=[]),
        big4_6mo=[],
        own_referrers_30d=[],
        metadata=SnapshotMetadata(
            radar_calls=0,
            pages_analytics_calls=0,
            categories_with_it_data=[],
            warnings=[],
        ),
    )
    dumped = snap.model_dump_json()
    reloaded = TrackerSnapshot.model_validate_json(dumped)
    assert reloaded.year == 2026
    assert reloaded.week == 15


def test_tracker_monthly_report_structure():
    report = TrackerMonthlyReport(
        year=2026,
        month=3,
        title_it="Claude +42% a marzo 2026: il mover del mese in Italia",
        subtitle_it="Snapshot del mercato AI & Search italiano",
        hero_mover="claude.ai",
        executive_summary=["Punto 1", "Punto 2", "Punto 3"],
        narrative="Paragrafo 1.\n\nParagrafo 2.",
        takeaways=[ReportTakeaway(title=f"Takeaway {i}", body="Corpo") for i in range(5)],
        outlook="Cosa aspettarsi.",
        snapshot_week_refs=["2026-W10", "2026-W11", "2026-W12", "2026-W13"],
        generated_at=datetime(2026, 4, 1, tzinfo=UTC),
        model_used="anthropic/claude-sonnet-4-5",
        cost_eur=0.07,
    )
    assert len(report.takeaways) == 5
    assert report.hero_mover == "claude.ai"
