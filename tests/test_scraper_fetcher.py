# tests/test_scraper_fetcher.py
from pathlib import Path

from pytest_httpx import HTTPXMock

from osservatorio_seo.fetchers.scraper import ScraperFetcher
from osservatorio_seo.http_client import HttpClient
from osservatorio_seo.models import Source


async def test_scraper_fetch(fixtures_dir: Path, httpx_mock: HTTPXMock) -> None:
    html = (fixtures_dir / "sample_scraper_page.html").read_text()
    httpx_mock.add_response(url="https://example.com/news", text=html)

    source = Source(
        id="example_scraper",
        name="Example Scraper",
        authority=7,
        type="media",
        fetcher="scraper",
        target_url="https://example.com/news",
        selectors={
            "article": "article.post",
            "title": "h2 a",
            "link": "h2 a",
            "content": "div.excerpt",
            "date": "time",
        },
    )
    async with HttpClient() as client:
        fetcher = ScraperFetcher(client)
        items = await fetcher.fetch(source)

    assert len(items) == 2
    assert items[0].title == "First News"
    assert items[0].url == "https://example.com/news/1"  # relative resolved
    assert items[1].url == "https://example.com/news/2"  # absolute preserved
    assert "first" in items[0].content.lower()


async def test_scraper_no_selectors() -> None:
    source = Source(
        id="x",
        name="x",
        authority=5,
        type="media",
        fetcher="scraper",
        target_url="https://x.com",
    )
    async with HttpClient() as client:
        fetcher = ScraperFetcher(client)
        items = await fetcher.fetch(source)
    assert items == []


async def test_scraper_empty_link_selector_uses_article_node(
    httpx_mock: HTTPXMock,
) -> None:
    """When link='' the article node itself is treated as the anchor."""
    html = """
    <html><body>
      <a class="card" href="/news/alpha"><h3>Alpha news</h3></a>
      <a class="card" href="/news/beta"><h3>Beta news</h3></a>
    </body></html>
    """
    httpx_mock.add_response(url="https://example.com/news", text=html)

    source = Source(
        id="self_link_site",
        name="Self link site",
        authority=8,
        type="media",
        fetcher="scraper",
        target_url="https://example.com/news",
        selectors={
            "article": "a.card",
            "title": "h3",
            "link": "",
        },
    )
    async with HttpClient() as client:
        fetcher = ScraperFetcher(client)
        items = await fetcher.fetch(source)

    assert len(items) == 2
    assert items[0].title == "Alpha news"
    assert items[0].url == "https://example.com/news/alpha"
    assert items[1].url == "https://example.com/news/beta"
