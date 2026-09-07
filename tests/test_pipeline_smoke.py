# tests/test_pipeline_smoke.py
import json
from datetime import UTC, datetime
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pytest_httpx import HTTPXMock

from osservatorio_seo.config import Settings
from osservatorio_seo.models import RawItem, Source
from osservatorio_seo.pipeline import Pipeline
from osservatorio_seo.summarizer import AISummary, SummarizerBudgetExceededError


@pytest.fixture
def smoke_settings(tmp_path: Path) -> Settings:
    return Settings(
        openrouter_api_key="sk-test",
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        state_dir=tmp_path / "data" / "state" / "doc_watcher",
        seen_urls_path=tmp_path / "data" / "state" / "seen_urls.json",
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


def build_rss_with_two_items() -> str:
    now_rfc = format_datetime(datetime.now(UTC))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Smoke</title>
  <link>https://example.com</link>
  <description>Smoke</description>
  <item>
    <title>Core update rollout finished</title>
    <link>https://example.com/core-update</link>
    <description>Detailed content about the March 2026 core update rollout finishing today.</description>
    <pubDate>{now_rfc}</pubDate>
  </item>
  <item>
    <title>Second story of the day</title>
    <link>https://example.com/second-story</link>
    <description>Another detailed piece of content published on the same day, for the budget test.</description>
    <pubDate>{now_rfc}</pubDate>
  </item>
</channel></rss>"""


async def test_pipeline_stops_summarizing_once_budget_exceeded(
    smoke_settings: Settings,
    fixtures_dir: Path,
    tmp_path: Path,
    httpx_mock: HTTPXMock,
) -> None:
    """Regressione 2.3: quando il summarizer segnala il tetto di spesa
    raggiunto, la pipeline deve interrompere la summarization (non contarlo
    come tentativo fallito) e comunque produrre un feed valido con gli item
    gia' riassunti prima del tetto."""
    httpx_mock.add_response(
        url="https://developers.google.com/search/blog/rss",
        text=build_rss_with_two_items(),
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
    summarize_mock = AsyncMock(
        side_effect=[fake_summary, SummarizerBudgetExceededError("tetto raggiunto")]
    )

    pipeline = Pipeline(
        settings=smoke_settings,
        sources_path=fixtures_dir / "sources.smoke.yml",
        doc_watcher_path=fixtures_dir / "doc_watcher.test.yml",
        site_data_dir=tmp_path / "site" / "data",
    )

    with (
        patch("osservatorio_seo.summarizer.Summarizer.summarize_item", new=summarize_mock),
        patch(
            "osservatorio_seo.premium_writer.PremiumWriter.analyze",
            new=AsyncMock(side_effect=Exception("skip in smoke test")),
        ),
    ):
        feed = await pipeline.run()

    assert len(feed.items) == 1
    assert feed.stats.summarize_attempted == 1
    assert feed.stats.summarize_failed == 0


async def test_pipeline_completes_when_jina_reader_fails(
    smoke_settings: Settings,
    fixtures_dir: Path,
    tmp_path: Path,
    httpx_mock: HTTPXMock,
) -> None:
    """Regressione 2.2: lo stadio Jina Reader e' best-effort. Un fallimento
    (qui: 500 da r.jina.ai) non deve mai impedire alla pipeline di produrre
    un feed — l'item prosegue con il content originale del fetcher."""
    jina_settings = smoke_settings.model_copy(update={"jina_api_key": "test-jina-key"})

    httpx_mock.add_response(
        url="https://developers.google.com/search/blog/rss",
        text=build_rss_with_current_dates(),
    )
    httpx_mock.add_response(
        url="https://developers.google.com/search/docs/essentials/spam-policies",
        text="<html><body><main><article>Stable content for doc watcher first run.</article></main></body></html>",
    )
    for _ in range(3):  # esaurisce i retry su 5xx di HttpClient
        httpx_mock.add_response(
            url="https://r.jina.ai/https://example.com/core-update", status_code=500
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
        settings=jina_settings,
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

    assert len(feed.items) == 1
    assert (smoke_settings.data_dir / "feed.json").exists()


async def test_pipeline_skips_previously_seen_url_on_second_run(
    smoke_settings: Settings,
    fixtures_dir: Path,
    tmp_path: Path,
    httpx_mock: HTTPXMock,
) -> None:
    """Regressione 2.1: con la finestra di freschezza a 72h lo stesso item
    ricompare in `normalized` per piu' run consecutivi. Senza seen_urls.json
    verrebbe rimandato al summarizer AI (pagato) e ripubblicato ogni giorno
    come se fosse nuovo."""
    rss = build_rss_with_current_dates()
    for _ in range(2):
        httpx_mock.add_response(url="https://developers.google.com/search/blog/rss", text=rss)
        httpx_mock.add_response(
            url="https://developers.google.com/search/docs/essentials/spam-policies",
            text="<html><body><main><article>Stable content for doc watcher.</article></main></body></html>",
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
    summarize_mock = AsyncMock(return_value=fake_summary)

    def mk_pipeline() -> Pipeline:
        return Pipeline(
            settings=smoke_settings,
            sources_path=fixtures_dir / "sources.smoke.yml",
            doc_watcher_path=fixtures_dir / "doc_watcher.test.yml",
            site_data_dir=tmp_path / "site" / "data",
        )

    with (
        patch("osservatorio_seo.summarizer.Summarizer.summarize_item", new=summarize_mock),
        patch(
            "osservatorio_seo.premium_writer.PremiumWriter.analyze",
            new=AsyncMock(side_effect=Exception("skip in smoke test")),
        ),
    ):
        feed1 = await mk_pipeline().run()
        feed2 = await mk_pipeline().run()

    assert feed1.stats.summarize_attempted == 1
    assert len(feed1.items) == 1

    # Stesso URL, secondo run: gia' visto, non deve tornare al summarizer ne'
    # ricomparire nel feed come se fosse una notizia nuova.
    assert summarize_mock.await_count == 1
    assert feed2.stats.summarize_attempted == 0
    assert len(feed2.items) == 0


async def test_run_a_vuoto_non_cancella_l_edizione_precedente(
    smoke_settings: Settings,
    fixtures_dir: Path,
    tmp_path: Path,
    httpx_mock: HTTPXMock,
) -> None:
    """La homepage e' renderizzata dal feed corrente: un feed vuoto la svuota.

    Successo davvero il 2026-09-07: un secondo run lanciato 25 minuti dopo il
    primo non aveva niente di nuovo (seen_urls aveva gia' visto tutti e 17 gli
    item in finestra), ha scritto un feed con `items: []` e la home e' rimasta
    senza articoli. Un giorno senza notizie nuove deve lasciare in piedi
    l'edizione precedente, non cancellarla.
    """
    rss = build_rss_with_current_dates()
    for _ in range(2):
        httpx_mock.add_response(url="https://developers.google.com/search/blog/rss", text=rss)
        httpx_mock.add_response(
            url="https://developers.google.com/search/docs/essentials/spam-policies",
            text="<html><body><main><article>Stable content for doc watcher.</article></main></body></html>",
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

    def mk_pipeline() -> Pipeline:
        return Pipeline(
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
        feed1 = await mk_pipeline().run()
        feed2 = await mk_pipeline().run()

    assert len(feed2.items) == 0, "il secondo run non ha nulla di nuovo"

    # Il feed su disco e' ancora quello del primo run, non quello vuoto.
    on_disk = json.loads((smoke_settings.data_dir / "feed.json").read_text(encoding="utf-8"))
    assert on_disk["run_id"] == feed1.run_id
    assert len(on_disk["items"]) == 1
    assert len(on_disk["top10"]) == 1

    published = json.loads((tmp_path / "site" / "data" / "feed.json").read_text(encoding="utf-8"))
    assert len(published["items"]) == 1


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
