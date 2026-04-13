"""Test that PremiumWriter.write_tracker_report produces valid output.

The LLM call is mocked — we test the prompt construction and response
parsing, not the actual model behavior.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from osservatorio_seo.premium_writer import PremiumWriter, _RawResult
from osservatorio_seo.tracker.models import (
    AIPlatformEntry,
    SnapshotMetadata,
    TopDomainEntry,
    TrackerMonthlyReport,
    TrackerSnapshot,
)


def _stub_snapshot(week: int) -> TrackerSnapshot:
    return TrackerSnapshot(
        year=2026,
        week=week,
        generated_at=datetime(2026, 4, 1 + week, tzinfo=UTC),
        top10_it=[
            TopDomainEntry(rank=1, domain="google.com"),
            TopDomainEntry(rank=2, domain="youtube.com"),
        ],
        top10_global=[
            TopDomainEntry(rank=1, domain="google.com"),
        ],
        ai_platforms_it=[
            AIPlatformEntry(
                domain="claude.ai",
                label="Claude",
                type="chatbot",
                rank=1,
                bucket="top",
            ),
            AIPlatformEntry(
                domain="chat.openai.com",
                label="ChatGPT",
                type="chatbot",
                rank=2,
                bucket="top",
            ),
        ],
        metadata=SnapshotMetadata(radar_calls=5),
    )


@pytest.mark.asyncio
async def test_write_tracker_report_returns_parsed_model():
    snapshots = [_stub_snapshot(w) for w in (10, 11, 12, 13)]
    writer = PremiumWriter(api_key="test")

    fake_response = {
        "title_it": "Claude al vertice a marzo 2026",
        "subtitle_it": "Piattaforma AI più rilevante in Italia",
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
