"""Tests for tracker v2 collector."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml

from osservatorio_seo.tracker.collector import TrackerCollector
from osservatorio_seo.tracker.models import TrackerSnapshot


@pytest.fixture
def platforms_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "tracker_platforms.yaml"
    cfg.write_text(
        yaml.dump(
            {
                "platforms": [
                    {"domain": "chatgpt.com", "label": "ChatGPT", "type": "chatbot"},
                    {"domain": "claude.ai", "label": "Claude", "type": "chatbot"},
                ]
            }
        )
    )
    return cfg


@pytest.fixture
def mock_radar() -> AsyncMock:
    radar = AsyncMock()
    radar.ranking_top.return_value = [
        {"rank": 1, "domain": "google.com", "categories": ["Search Engines"]},
        {"rank": 2, "domain": "chatgpt.com", "categories": ["Artificial Intelligence"]},
    ]
    radar.domain_timeseries.return_value = [
        {"date": "2026-04-06T00:00:00Z", "rank": 1},
        {"date": "2026-04-13T00:00:00Z", "rank": 1},
    ]
    radar.domain_detail.return_value = {"rank": 10, "bucket": "200"}
    radar.bot_human_timeseries.return_value = [
        {"date": "2026-04-06T00:00:00Z", "human_pct": 83.0, "bot_pct": 17.0},
    ]
    radar.ai_bots_user_agent.return_value = (
        ["Googlebot", "GPTBot"],
        [{"date": "2026-04-06T00:00:00Z", "values": {"Googlebot": 60.0, "GPTBot": 40.0}}],
    )
    radar.crawl_purpose.return_value = (
        ["Training", "User Action"],
        [{"date": "2026-04-06T00:00:00Z", "values": {"Training": 50.0, "User Action": 50.0}}],
    )
    radar.industry_summary.return_value = [
        {"industry": "Retail", "pct": 28.7},
    ]
    radar.device_type_timeseries.return_value = [
        {"date": "2026-04-06T00:00:00Z", "mobile_pct": 51.0, "desktop_pct": 49.0},
    ]
    radar.os_summary.return_value = [
        {"os": "ANDROID", "pct": 38.5},
        {"os": "WINDOWS", "pct": 31.0},
    ]
    return radar


@pytest.mark.asyncio
async def test_collect_builds_v3_snapshot(mock_radar, platforms_config):
    collector = TrackerCollector(radar=mock_radar, platforms_config=platforms_config)
    snapshot = await collector.collect(year=2026, week=16)

    assert isinstance(snapshot, TrackerSnapshot)
    assert snapshot.schema_version == "3.0"
    # Section 1: top 10 for IT and global
    assert len(snapshot.top10_it) == 2
    assert len(snapshot.top10_global) == 2
    assert snapshot.top10_it[0].domain == "google.com"
    assert len(snapshot.top10_it[0].timeseries) == 2
    # Section 2: AI platforms
    assert len(snapshot.ai_platforms_it) == 2
    assert len(snapshot.ai_platforms_global) == 2
    assert snapshot.ai_platforms_it[0].label == "ChatGPT"
    # Section 3: bot/human
    assert len(snapshot.bot_human_it.points) == 1
    assert len(snapshot.bot_human_global.points) == 1
    # Section 4
    assert len(snapshot.ai_bots_ua_it.agents) == 2
    assert len(snapshot.crawl_purpose_it.purposes) == 2
    # Section 5
    assert len(snapshot.industry_it) == 1
    assert len(snapshot.industry_global) == 1
    # Section 9: device type + OS
    assert len(snapshot.device_type_it.points) == 1
    assert len(snapshot.os_it) == 2


@pytest.mark.asyncio
async def test_collect_handles_partial_failures(mock_radar, platforms_config):
    mock_radar.bot_human_timeseries.side_effect = Exception("API down")
    collector = TrackerCollector(radar=mock_radar, platforms_config=platforms_config)
    snapshot = await collector.collect(year=2026, week=16)

    # Should still have data for other sections
    assert len(snapshot.top10_it) == 2
    # But bot_human should be empty
    assert len(snapshot.bot_human_it.points) == 0
    assert any("API down" in w for w in snapshot.metadata.warnings)


@pytest.mark.asyncio
async def test_persist_writes_json(mock_radar, platforms_config, tmp_path):
    collector = TrackerCollector(radar=mock_radar, platforms_config=platforms_config)
    snapshot = await collector.collect(year=2026, week=16)
    target = TrackerCollector.persist(snapshot, base_dir=tmp_path)
    assert target.exists()
    assert target.name == "2026-W16.json"
    restored = TrackerSnapshot.model_validate_json(target.read_text())
    assert restored.schema_version == "3.0"
    assert len(restored.top10_it) == 2
