# tests/test_rss_fetcher.py
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from pytest_httpx import HTTPXMock

from osservatorio_seo.fetchers.rss import RSSFetcher
from osservatorio_seo.http_client import HttpClient
from osservatorio_seo.models import Source


async def test_rss_fetch(fixtures_dir: Path, httpx_mock: HTTPXMock) -> None:
    xml = (fixtures_dir / "sample_feed.xml").read_text()
    httpx_mock.add_response(url="https://example.com/feed.xml", text=xml)

    source = Source(
        id="example",
        name="Example",
        authority=7,
        type="media",
        fetcher="rss",
        feed_url="https://example.com/feed.xml",
    )
    async with HttpClient() as client:
        fetcher = RSSFetcher(client)
        items = await fetcher.fetch(source)

    assert len(items) == 2
    assert items[0].title == "March Core Update Finished"
    assert items[0].url == "https://example.com/march-core-update"
    assert items[0].source_id == "example"
    assert items[0].content  # non vuoto


async def test_rss_empty_feed(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://example.com/feed.xml",
        text="<?xml version='1.0'?><rss><channel></channel></rss>",
    )
    source = Source(
        id="x",
        name="x",
        authority=5,
        type="media",
        fetcher="rss",
        feed_url="https://example.com/feed.xml",
    )
    async with HttpClient() as client:
        fetcher = RSSFetcher(client)
        items = await fetcher.fetch(source)
    assert items == []


async def test_rss_403_is_failure_not_empty_feed(httpx_mock: HTTPXMock) -> None:
    """Un feed che risponde 403 e' una fonte morta: deve sollevare, non
    ritornare [] come se il feed fosse semplicemente senza voci."""
    httpx_mock.add_response(url="https://example.com/feed.xml", status_code=403, text="Forbidden")
    source = Source(
        id="x",
        name="x",
        authority=5,
        type="media",
        fetcher="rss",
        feed_url="https://example.com/feed.xml",
    )
    async with HttpClient() as client:
        fetcher = RSSFetcher(client)
        with pytest.raises(httpx.HTTPStatusError, match="403"):
            await fetcher.fetch(source)


async def test_rss_dates_are_utc_regardless_of_process_tz(
    fixtures_dir: Path, httpx_mock: HTTPXMock, monkeypatch
) -> None:
    """Regressione: time.mktime() interpreta lo struct_time UTC di feedparser
    come ora locale del processo. Il workflow di produzione imposta
    TZ=Europe/Rome, quindi le date pubblicate finivano decalate di 1-2 ore.
    calendar.timegm() tratta lo struct_time come UTC indipendentemente da TZ."""
    with monkeypatch.context() as m:
        m.setenv("TZ", "Europe/Rome")
        time.tzset()

        xml = (fixtures_dir / "sample_feed.xml").read_text()
        httpx_mock.add_response(url="https://example.com/feed.xml", text=xml)
        source = Source(
            id="example",
            name="Example",
            authority=7,
            type="media",
            fetcher="rss",
            feed_url="https://example.com/feed.xml",
        )
        async with HttpClient() as client:
            fetcher = RSSFetcher(client)
            items = await fetcher.fetch(source)

        # sample_feed.xml: pubDate "Fri, 11 Apr 2026 03:42:00 GMT" e
        # "Fri, 11 Apr 2026 05:12:00 GMT" — devono restare quegli orari UTC
        # esatti, non scalati dell'offset di Europe/Rome (CEST = UTC+2).
        assert items[0].published_at == datetime(2026, 4, 11, 3, 42, tzinfo=UTC)
        assert items[1].published_at == datetime(2026, 4, 11, 5, 12, tzinfo=UTC)
    time.tzset()
