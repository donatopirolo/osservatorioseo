# tests/test_rss_fetcher.py
from pathlib import Path

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
