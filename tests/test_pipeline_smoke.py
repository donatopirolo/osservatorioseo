# tests/test_pipeline_smoke.py
from datetime import UTC, datetime
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pytest_httpx import HTTPXMock

from osservatorio_seo.config import Settings
from osservatorio_seo.models import RawItem, Source
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
    assert feed.stats.sources_failed == 0
    assert feed.stats.sources_empty == 0
    assert (smoke_settings.data_dir / "feed.json").exists()
    assert (tmp_path / "site" / "data" / "feed.json").exists()


async def test_fetch_all_counts_failed_and_empty_sources(
    smoke_settings: Settings, fixtures_dir: Path
) -> None:
    """Regressione: failed_sources era vuoto da 155 giorni perche' le fonti
    che ritornano [] (senza sollevare) non venivano contate come guasto ne'
    come vuote da nessuna parte."""

    def mk_source(source_id: str, fetcher: str) -> Source:
        return Source(
            id=source_id,
            name=source_id,
            authority=5,
            type="media",
            fetcher=fetcher,
            feed_url="https://example.com" if fetcher != "scraper" else None,
            target_url="https://example.com" if fetcher == "scraper" else None,
        )

    async def ok_fetch(source: Source) -> list[RawItem]:
        return [
            RawItem(
                title="t",
                url="https://example.com/1",
                source_id=source.id,
                published_at=datetime.now(UTC),
                content="c",
            ),
            RawItem(
                title="t2",
                url="https://example.com/2",
                source_id=source.id,
                published_at=datetime.now(UTC),
                content="c",
            ),
        ]

    async def empty_fetch(source: Source) -> list[RawItem]:
        return []

    async def failing_fetch(source: Source) -> list[RawItem]:
        raise RuntimeError("boom")

    class StubFetcher:
        def __init__(self, fn):
            self._fn = fn

        async def fetch(self, source: Source) -> list[RawItem]:
            return await self._fn(source)

    pipeline = Pipeline(
        settings=smoke_settings,
        sources_path=fixtures_dir / "sources.smoke.yml",
        doc_watcher_path=fixtures_dir / "doc_watcher.test.yml",
    )
    sources = [
        mk_source("source_ok", "rss"),
        mk_source("source_empty", "scraper"),
        mk_source("source_failing", "playwright"),
    ]
    fetchers = {
        "rss": StubFetcher(ok_fetch),
        "scraper": StubFetcher(empty_fetch),
        "playwright": StubFetcher(failing_fetch),
    }

    raw_items, failed, empty = await pipeline._fetch_all(sources, fetchers)

    assert len(raw_items) == 2
    assert [f.id for f in failed] == ["source_failing"]
    assert empty == ["source_empty"]
