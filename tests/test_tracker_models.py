"""Tests for tracker v2 pydantic models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from osservatorio_seo.tracker.models import (
    AIBotPoint,
    AIBotsTimeseries,
    AIPlatformEntry,
    BotHumanPoint,
    BotHumanTimeseries,
    CrawlPurposePoint,
    CrawlPurposeTimeseries,
    ReportTakeaway,
    SnapshotMetadata,
    TimeseriesPoint,
    TopDomainEntry,
    TrackerMonthlyReport,
    TrackerSnapshot,
)

NOW = datetime(2026, 4, 13, 12, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# TopDomainEntry
# ---------------------------------------------------------------------------


def test_top_domain_entry_roundtrip():
    entry = TopDomainEntry(
        rank=1,
        domain="google.com",
        categories=["search"],
        timeseries=[TimeseriesPoint(date=NOW, value=99.5)],
    )
    dumped = entry.model_dump_json()
    restored = TopDomainEntry.model_validate_json(dumped)
    assert restored.rank == 1
    assert restored.domain == "google.com"
    assert restored.categories == ["search"]
    assert len(restored.timeseries) == 1
    assert restored.timeseries[0].value == 99.5


def test_top_domain_entry_rank_ge1():
    with pytest.raises(ValidationError):
        TopDomainEntry(rank=0, domain="bad.com")


def test_top_domain_entry_defaults():
    entry = TopDomainEntry(rank=5, domain="example.com")
    assert entry.categories == []
    assert entry.timeseries == []


# ---------------------------------------------------------------------------
# AIPlatformEntry
# ---------------------------------------------------------------------------


def test_ai_platform_entry_with_rank():
    entry = AIPlatformEntry(
        domain="claude.ai",
        label="Claude",
        type="llm",
        rank=2,
        bucket="top10",
    )
    assert entry.rank == 2


def test_ai_platform_entry_without_rank():
    entry = AIPlatformEntry(
        domain="perplexity.ai",
        label="Perplexity",
        type="search",
        bucket="top50",
    )
    assert entry.rank is None


def test_ai_platform_entry_extra_field_rejected():
    with pytest.raises(ValidationError):
        AIPlatformEntry(
            domain="x.ai",
            label="Grok",
            type="llm",
            bucket="top10",
            unknown_field="oops",
        )


# ---------------------------------------------------------------------------
# BotHumanTimeseries
# ---------------------------------------------------------------------------


def test_bot_human_timeseries_creation():
    ts = BotHumanTimeseries(
        points=[
            BotHumanPoint(date=NOW, human_pct=60.0, bot_pct=40.0),
            BotHumanPoint(date=datetime(2026, 3, 13, tzinfo=UTC), human_pct=58.0, bot_pct=42.0),
        ]
    )
    assert len(ts.points) == 2
    assert ts.points[0].human_pct == 60.0
    assert ts.points[0].bot_pct == 40.0


def test_bot_human_timeseries_default_empty():
    ts = BotHumanTimeseries()
    assert ts.points == []


# ---------------------------------------------------------------------------
# AIBotsTimeseries
# ---------------------------------------------------------------------------


def test_ai_bots_timeseries_with_points():
    ts = AIBotsTimeseries(
        agents=["GPTBot", "ClaudeBot"],
        points=[
            AIBotPoint(date=NOW, values={"GPTBot": 55.0, "ClaudeBot": 30.0}),
        ],
    )
    assert ts.agents == ["GPTBot", "ClaudeBot"]
    assert ts.points[0].values["ClaudeBot"] == 30.0


def test_ai_bots_timeseries_defaults():
    ts = AIBotsTimeseries()
    assert ts.agents == []
    assert ts.points == []


# ---------------------------------------------------------------------------
# CrawlPurposeTimeseries
# ---------------------------------------------------------------------------


def test_crawl_purpose_timeseries_with_points():
    ts = CrawlPurposeTimeseries(
        purposes=["indexing", "ai_training"],
        points=[
            CrawlPurposePoint(date=NOW, values={"indexing": 70.0, "ai_training": 30.0}),
        ],
    )
    assert ts.purposes == ["indexing", "ai_training"]
    assert ts.points[0].values["ai_training"] == 30.0


def test_crawl_purpose_timeseries_defaults():
    ts = CrawlPurposeTimeseries()
    assert ts.purposes == []
    assert ts.points == []


# ---------------------------------------------------------------------------
# TrackerSnapshot v2
# ---------------------------------------------------------------------------


def test_tracker_snapshot_minimal_creation():
    snap = TrackerSnapshot(
        year=2026,
        week=15,
        generated_at=NOW,
        metadata=SnapshotMetadata(),
    )
    assert snap.schema_version == "2.0"
    assert snap.year == 2026
    assert snap.week == 15
    assert snap.top10_it == []
    assert snap.top10_global == []
    assert snap.ai_platforms_it == []
    assert snap.ai_platforms_global == []
    assert snap.industry_it == []
    assert snap.industry_global == []


def test_tracker_snapshot_json_roundtrip():
    snap = TrackerSnapshot(
        year=2026,
        week=15,
        generated_at=NOW,
        top10_it=[
            TopDomainEntry(rank=1, domain="google.com", categories=["search"]),
        ],
        ai_platforms_it=[
            AIPlatformEntry(domain="claude.ai", label="Claude", type="llm", rank=1, bucket="top10"),
        ],
        bot_human_it=BotHumanTimeseries(
            points=[BotHumanPoint(date=NOW, human_pct=65.0, bot_pct=35.0)]
        ),
        ai_bots_ua_it=AIBotsTimeseries(
            agents=["GPTBot"],
            points=[AIBotPoint(date=NOW, values={"GPTBot": 100.0})],
        ),
        crawl_purpose_it=CrawlPurposeTimeseries(
            purposes=["indexing"],
            points=[CrawlPurposePoint(date=NOW, values={"indexing": 100.0})],
        ),
        metadata=SnapshotMetadata(radar_calls=5, warnings=["low data"]),
    )
    dumped = snap.model_dump_json()
    restored = TrackerSnapshot.model_validate_json(dumped)
    assert restored.schema_version == "2.0"
    assert restored.year == 2026
    assert restored.week == 15
    assert restored.top10_it[0].domain == "google.com"
    assert restored.ai_platforms_it[0].label == "Claude"
    assert restored.bot_human_it.points[0].human_pct == 65.0
    assert restored.ai_bots_ua_it.agents == ["GPTBot"]
    assert restored.crawl_purpose_it.purposes == ["indexing"]
    assert restored.metadata.radar_calls == 5
    assert restored.metadata.warnings == ["low data"]


def test_tracker_snapshot_week_bounds():
    with pytest.raises(ValidationError):
        TrackerSnapshot(year=2026, week=0, generated_at=NOW, metadata=SnapshotMetadata())
    with pytest.raises(ValidationError):
        TrackerSnapshot(year=2026, week=54, generated_at=NOW, metadata=SnapshotMetadata())


def test_tracker_snapshot_extra_field_rejected():
    with pytest.raises(ValidationError):
        TrackerSnapshot(
            year=2026,
            week=15,
            generated_at=NOW,
            metadata=SnapshotMetadata(),
            unknown_field="oops",
        )


# ---------------------------------------------------------------------------
# TrackerMonthlyReport
# ---------------------------------------------------------------------------


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
        generated_at=NOW,
        model_used="anthropic/claude-sonnet-4-5",
        cost_eur=0.07,
    )
    assert report.schema_version == "2.0"
    assert len(report.takeaways) == 5
    assert report.hero_mover == "claude.ai"
