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
