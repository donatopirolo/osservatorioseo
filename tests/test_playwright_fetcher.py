from datetime import UTC, datetime

import pytest

from osservatorio_seo.fetchers.playwright_fetcher import PlaywrightFetcher
from osservatorio_seo.models import Source


@pytest.fixture
def social_source() -> Source:
    return Source(
        id="test_social",
        name="Test Social",
        authority=8,
        type="social",
        fetcher="playwright",
        target_url="https://x.com/someuser",
        selectors={
            "post": "article[data-testid='tweet']",
            "text": "div[data-testid='tweetText']",
            "link": "a[href*='/status/']",
        },
    )


async def test_playwright_no_target_url() -> None:
    source = Source(
        id="x",
        name="x",
        authority=5,
        type="social",
        fetcher="playwright",
    )
    fetcher = PlaywrightFetcher()
    items = await fetcher.fetch(source)
    assert items == []


async def test_playwright_parses_post_nodes(social_source: Source) -> None:
    fetcher = PlaywrightFetcher()
    fake_html = """
    <html><body>
      <article data-testid="tweet">
        <div data-testid="tweetText">First post text</div>
        <a href="/someuser/status/12345">link</a>
      </article>
      <article data-testid="tweet">
        <div data-testid="tweetText">Second post</div>
        <a href="/someuser/status/67890">link</a>
      </article>
    </body></html>
    """
    items = fetcher._parse_html(fake_html, social_source)
    assert len(items) == 2
    assert items[0].title.startswith("First post")
    assert "status/12345" in items[0].url


async def test_playwright_uses_time_element_for_published_at(
    social_source: Source,
) -> None:
    """Se c'è <time datetime="ISO"> dentro l'articolo, usiamo quello."""
    fetcher = PlaywrightFetcher()
    fake_html = """
    <html><body>
      <article data-testid="tweet">
        <div data-testid="tweetText">Recent post</div>
        <a href="/someuser/status/1897332925382975619">link</a>
        <time datetime="2026-04-10T15:30:00.000Z">10 apr</time>
      </article>
    </body></html>
    """
    items = fetcher._parse_html(fake_html, social_source)
    assert len(items) == 1
    assert items[0].published_at == datetime(2026, 4, 10, 15, 30, 0, tzinfo=UTC)


async def test_playwright_decodes_twitter_snowflake_when_no_time_element(
    social_source: Source,
) -> None:
    """Senza <time>, decodifica l'ID tweet dallo snowflake Twitter."""
    fetcher = PlaywrightFetcher()
    # ID 1897332925382975619 → 2025-03-05 17:06:34 UTC
    # (dalla segnalazione reale dell'utente: https://x.com/Google/status/1897332925382975619)
    fake_html = """
    <html><body>
      <article data-testid="tweet">
        <div data-testid="tweetText">Old google post</div>
        <a href="/Google/status/1897332925382975619">link</a>
      </article>
    </body></html>
    """
    items = fetcher._parse_html(fake_html, social_source)
    assert len(items) == 1
    assert items[0].published_at == datetime(2025, 3, 5, 17, 6, 34, 809000, tzinfo=UTC)


async def test_playwright_skips_item_without_any_date(social_source: Source) -> None:
    """Nessun <time> e nessun /status/N → item skippato (no data fittizia now())."""
    fetcher = PlaywrightFetcher()
    fake_html = """
    <html><body>
      <article data-testid="tweet">
        <div data-testid="tweetText">No date info</div>
        <a href="/random/path">link</a>
      </article>
    </body></html>
    """
    items = fetcher._parse_html(fake_html, social_source)
    assert items == []
