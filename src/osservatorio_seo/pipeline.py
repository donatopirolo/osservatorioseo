"""Orchestratore: chiama fetcher → normalizer → summarizer → ranker → publisher."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from osservatorio_seo.config import (
    DocWatcherPage,
    Settings,
    load_doc_watcher,
    load_sources,
)
from osservatorio_seo.doc_watcher.state import StateStore
from osservatorio_seo.doc_watcher.watcher import DocChangeResult, DocWatcher
from osservatorio_seo.fetchers.base import Fetcher
from osservatorio_seo.fetchers.playwright_fetcher import PlaywrightFetcher
from osservatorio_seo.fetchers.rss import RSSFetcher
from osservatorio_seo.fetchers.scraper import ScraperFetcher
from osservatorio_seo.http_client import HttpClient
from osservatorio_seo.models import (
    DocChange,
    DocWatcherStatus,
    FailedSource,
    Feed,
    FeedStats,
    Item,
    RawItem,
    Source,
)
from osservatorio_seo.normalizer import Normalizer
from osservatorio_seo.publisher import Publisher
from osservatorio_seo.ranker import Ranker
from osservatorio_seo.summarizer import Summarizer

logger = logging.getLogger(__name__)
ROME_TZ = ZoneInfo("Europe/Rome")


class Pipeline:
    def __init__(
        self,
        settings: Settings,
        sources_path: Path,
        doc_watcher_path: Path,
        site_data_dir: Path | None = None,
    ) -> None:
        self._settings = settings
        self._sources_path = sources_path
        self._doc_watcher_path = doc_watcher_path
        self._site_data_dir = site_data_dir

    async def run(self) -> Feed:
        now_utc = datetime.now(UTC)
        now_local = now_utc.astimezone(ROME_TZ)
        run_id = now_local.strftime("%Y-%m-%d-%H%M")

        sources = load_sources(self._sources_path)
        doc_pages = load_doc_watcher(self._doc_watcher_path)

        async with HttpClient(
            max_concurrent_per_host=self._settings.max_concurrent_per_host,
            timeout_s=self._settings.request_timeout_s,
        ) as http:
            fetchers: dict[str, Fetcher] = {
                "rss": RSSFetcher(http),
                "scraper": ScraperFetcher(http),
                "playwright": PlaywrightFetcher(self._settings.playwright_timeout_s),
            }
            raw_items, failed_sources = await self._fetch_all(sources, fetchers)

            state = StateStore(self._settings.state_dir)
            doc_watcher = DocWatcher(http=http, state=state)
            doc_results, doc_statuses = await self._check_doc_pages(doc_pages, doc_watcher)

        normalizer = Normalizer()
        sources_by_id = {s.id: s for s in sources}
        normalized = normalizer.normalize(raw_items, sources_by_id)

        summarizer = Summarizer(
            api_key=self._settings.openrouter_api_key,
            primary_model=self._settings.summarizer_model,
            fallback_models=self._settings.fallback_models,
        )
        items, ai_cost = await self._summarize_all(normalized, sources_by_id, summarizer)

        doc_items, doc_cost = await self._summarize_doc_changes(doc_results, doc_pages, summarizer)
        items.extend(doc_items)
        ai_cost += doc_cost

        ranker = Ranker()
        ranked = ranker.rank(items)

        stats = FeedStats(
            sources_checked=len(sources),
            sources_failed=len(failed_sources),
            items_collected=len(raw_items),
            items_after_dedup=len(normalized),
            doc_changes_detected=sum(1 for r in doc_results if r.changed),
            ai_cost_eur=round(ai_cost, 4),
        )
        feed = Feed(
            generated_at=now_utc,
            generated_at_local=now_local,
            timezone="Europe/Rome",
            run_id=run_id,
            stats=stats,
            top10=ranked.top10,
            categories=ranked.categories,
            items=items,
            doc_watcher_status=doc_statuses,
            failed_sources=failed_sources,
        )

        publisher = Publisher(
            data_dir=self._settings.data_dir,
            archive_dir=self._settings.archive_dir,
            site_data_dir=self._site_data_dir,
        )
        publisher.publish(feed)
        # Snapshot di sources + doc_watcher pages per /docs/ SSG
        publisher.publish_config_snapshot(sources, doc_pages)
        # SSG: genera tutti gli HTML statici (homepage, archivio, articoli,
        # hub, docs, about, sitemap, feed.xml, robots.txt, top-settimana)
        site_dir = self._site_data_dir.parent if self._site_data_dir else Path("site")
        publisher.publish_ssg(
            feed,
            sources,
            doc_pages,
            templates_dir=Path("templates"),
            site_dir=site_dir,
            allow_indexing=False,
        )
        return feed

    async def _fetch_all(
        self, sources: list[Source], fetchers: dict[str, Fetcher]
    ) -> tuple[list[RawItem], list[FailedSource]]:
        raw_items: list[RawItem] = []
        failed: list[FailedSource] = []

        async def fetch_one(src: Source) -> None:
            fetcher = fetchers.get(src.fetcher)
            if fetcher is None:
                failed.append(FailedSource(id=src.id, error=f"no fetcher for {src.fetcher}"))
                return
            try:
                items = await asyncio.wait_for(
                    fetcher.fetch(src),
                    timeout=self._settings.fetcher_timeout_s,
                )
                raw_items.extend(items)
            except Exception as e:  # noqa: BLE001
                logger.warning("source %s failed: %s", src.id, e)
                failed.append(FailedSource(id=src.id, error=type(e).__name__ + ": " + str(e)[:200]))

        await asyncio.gather(*(fetch_one(s) for s in sources))
        return raw_items, failed

    async def _check_doc_pages(
        self, pages: list[DocWatcherPage], watcher: DocWatcher
    ) -> tuple[list[DocChangeResult], list[DocWatcherStatus]]:
        results: list[DocChangeResult] = []
        statuses: list[DocWatcherStatus] = []
        for page in pages:
            try:
                r = await watcher.check(page)
                results.append(r)
                statuses.append(
                    DocWatcherStatus(page_id=page.id, last_checked=r.checked_at, changed=r.changed)
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("doc page %s failed: %s", page.id, e)
        return results, statuses

    async def _summarize_all(
        self,
        normalized: list[RawItem],
        sources_by_id: dict[str, Source],
        summarizer: Summarizer,
    ) -> tuple[list[Item], float]:
        items: list[Item] = []
        total_cost = 0.0

        for idx, raw in enumerate(sorted(normalized, key=lambda r: r.published_at), start=1):
            source = sources_by_id[raw.source_id]
            try:
                summary = await summarizer.summarize_item(raw, source)
            except Exception as e:  # noqa: BLE001
                logger.warning("summarize failed for %s: %s", raw.url, e)
                continue
            date_str = datetime.now(ROME_TZ).strftime("%Y-%m-%d")
            items.append(
                Item(
                    id=f"item_{date_str}_{idx:03d}",
                    title_original=raw.title,
                    title_it=summary.title_it,
                    summary_it=summary.summary_it,
                    url=raw.url,
                    source=source,
                    category=summary.category,
                    tags=summary.tags,
                    importance=summary.importance,
                    published_at=raw.published_at,
                    fetched_at=datetime.now(UTC),
                    is_doc_change=False,
                    language_original=raw.language_original,
                    summarizer_model=summary.model_used,
                    raw_hash="sha256:" + hashlib.sha256(raw.content.encode()).hexdigest()[:16],
                )
            )
            total_cost += summary.cost_eur
        return items, total_cost

    async def _summarize_doc_changes(
        self,
        results: list[DocChangeResult],
        pages: list[DocWatcherPage],
        summarizer: Summarizer,
    ) -> tuple[list[Item], float]:
        items: list[Item] = []
        total_cost = 0.0
        pages_by_id = {p.id: p for p in pages}

        for idx, r in enumerate(results, start=1):
            if not r.changed:
                continue
            page = pages_by_id[r.page_id]
            try:
                summary = await summarizer.summarize_doc_change(
                    page_name=page.name, page_url=page.url, diff=r.diff
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("doc change summary failed for %s: %s", page.id, e)
                continue
            date_str = datetime.now(ROME_TZ).strftime("%Y-%m-%d")
            items.append(
                Item(
                    id=f"doc_{date_str}_{idx:03d}",
                    title_original=page.name,
                    title_it=summary.title_it,
                    summary_it=summary.summary_it,
                    url=page.url,
                    source=Source(
                        id="doc_watcher",
                        name="OsservatorioSEO Doc Watcher",
                        authority=10,
                        type="doc_change",
                        fetcher="rss",
                    ),
                    category=page.category,
                    tags=summary.tags,
                    importance=summary.importance,
                    published_at=r.checked_at,
                    fetched_at=r.checked_at,
                    is_doc_change=True,
                    doc_change=DocChange(
                        page_id=page.id,
                        previous_hash=r.previous_hash or "",
                        current_hash=r.current_hash,
                        lines_added=r.lines_added,
                        lines_removed=r.lines_removed,
                    ),
                    summarizer_model=summary.model_used,
                    raw_hash=r.current_hash,
                )
            )
            total_cost += summary.cost_eur
        return items, total_cost
