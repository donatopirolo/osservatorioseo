# tests/test_pipeline_smoke.py
from datetime import UTC, datetime
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pytest_httpx import HTTPXMock

from osservatorio_seo.config import Settings
from osservatorio_seo.pipeline import Pipeline
from osservatorio_seo.summarizer import AISummary


@pytest.fixture
def smoke_settings(tmp_path: Path) -> Settings:
    return Settings(
        openrouter_api_key="sk-test",
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        state_dir=tmp_path / "data" / "state" / "doc_watcher",
    )


def build_rss_with_current_dates() -> str:
    now_rfc = format_datetime(datetime.now(UTC))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Smoke</title>
  <link>https://example.com</link>
  <description>Smoke</description>
  <item>
    <title>Core update rollout finished</title>
    <link>https://example.com/core-update</link>
    <description>Detailed content about the March 2026 core update rollout finishing today with notable impact.</description>
    <pubDate>{now_rfc}</pubDate>
  </item>
</channel></rss>"""


async def test_pipeline_end_to_end(
    smoke_settings: Settings,
    fixtures_dir: Path,
    tmp_path: Path,
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        url="https://developers.google.com/search/blog/rss",
        text=build_rss_with_current_dates(),
    )
    httpx_mock.add_response(
        url="https://developers.google.com/search/docs/essentials/spam-policies",
        text="<html><body><main><article>Stable content for doc watcher first run.</article></main></body></html>",
    )

    fake_summary = AISummary(
        title_it="Titolo IT di prova",
        summary_it="Riassunto in italiano di almeno venti caratteri.",
        category="google_updates",
        tags=["core_update"],
        importance=5,
        model_used="google/gemini-2.0-flash",
        cost_eur=0.001,
    )

    pipeline = Pipeline(
        settings=smoke_settings,
        sources_path=fixtures_dir / "sources.smoke.yml",
        doc_watcher_path=fixtures_dir / "doc_watcher.test.yml",
        site_data_dir=tmp_path / "site" / "data",
    )

    with (
        patch(
            "osservatorio_seo.summarizer.Summarizer.summarize_item",
            new=AsyncMock(return_value=fake_summary),
        ),
        patch(
            "osservatorio_seo.premium_writer.PremiumWriter.analyze",
            new=AsyncMock(side_effect=Exception("skip in smoke test")),
        ),
    ):
        feed = await pipeline.run()

    assert feed.stats.sources_checked == 1
    assert feed.stats.items_collected >= 1
    assert (smoke_settings.data_dir / "feed.json").exists()
    assert (tmp_path / "site" / "data" / "feed.json").exists()
