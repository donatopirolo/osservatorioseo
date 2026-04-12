"""Test that PremiumWriter.write_tracker_report produces valid output.

The LLM call is mocked — we test the prompt construction and response
parsing, not the actual model behavior.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from osservatorio_seo.premium_writer import PremiumWriter, _RawResult
from osservatorio_seo.tracker.models import (
    BumpChartData,
    DomainMovement,
    DomainRank,
    IndexTimeseries,
    SnapshotMetadata,
    TopMovers,
    TrackerMonthlyReport,
    TrackerSnapshot,
)


def _stub_snapshot(week: int) -> TrackerSnapshot:
    return TrackerSnapshot(
        year=2026,
        week=week,
        generated_at=datetime(2026, 4, 1 + week, tzinfo=UTC),
        ai_index_24mo=IndexTimeseries(label="ai"),
        internet_index_24mo=IndexTimeseries(label="internet"),
        bump_chart_6mo=BumpChartData(),
        top_movers_30d=TopMovers(
            up=[DomainMovement(domain="claude.ai", delta_pct=42.5)],
            down=[DomainMovement(domain="perplexity.ai", delta_pct=-8.1)],
        ),
        ai_top10_current=[DomainRank(domain="chat.openai.com", rank=1)],
        search_top5_current=[DomainRank(domain="google.com", rank=1)],
        metadata=SnapshotMetadata(radar_calls=5, pages_analytics_calls=1),
    )


@pytest.mark.asyncio
async def test_write_tracker_report_returns_parsed_model():
    snapshots = [_stub_snapshot(w) for w in (10, 11, 12, 13)]
    writer = PremiumWriter(api_key="test")

    fake_response = {
        "title_it": "Claude +42% a marzo 2026",
        "subtitle_it": "Il mover del mese",
        "executive_summary": ["Punto 1", "Punto 2", "Punto 3"],
        "narrative": "Paragrafo 1.\n\nParagrafo 2.",
        "takeaways": [{"title": f"T{i}", "body": "body"} for i in range(5)],
        "outlook": "Prospettive.",
    }
    writer._call_with_fallback = AsyncMock(
        return_value=_RawResult(parsed=fake_response, model="test-model", cost_eur=0.05)
    )

    report = await writer.write_tracker_report(year=2026, month=3, snapshots=snapshots)

    assert isinstance(report, TrackerMonthlyReport)
    assert report.year == 2026
    assert report.month == 3
    assert len(report.takeaways) == 5
    assert report.hero_mover == "claude.ai"
    assert report.cost_eur == 0.05
    assert len(report.snapshot_week_refs) == 4
