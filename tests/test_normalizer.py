from datetime import UTC, datetime, timedelta

from osservatorio_seo.models import RawItem, Source
from osservatorio_seo.normalizer import Normalizer


def mk_source(authority: int = 5) -> Source:
    return Source(
        id=f"src{authority}", name=f"src{authority}",
        authority=authority, type="media", fetcher="rss",
        feed_url="https://example.com/feed",
    )


def mk_raw(url: str, title: str, source_id: str, content: str = "enough content here for normalization") -> RawItem:
    return RawItem(
        title=title, url=url, source_id=source_id,
        published_at=datetime.now(UTC), content=content,
    )


def test_url_tracking_params_removed() -> None:
    norm = Normalizer()
    items = [mk_raw("https://example.com/a?utm_source=x&id=5", "Hello", "s1")]
    out = norm.normalize(items, {"s1": mk_source()})
    assert out[0].url == "https://example.com/a?id=5"


def test_url_trailing_slash_normalized() -> None:
    norm = Normalizer()
    items = [mk_raw("https://example.com/a/", "Hello", "s1")]
    out = norm.normalize(items, {"s1": mk_source()})
    assert out[0].url == "https://example.com/a"


def test_dedup_by_url() -> None:
    norm = Normalizer()
    items = [
        mk_raw("https://example.com/a", "Hello", "s1"),
        mk_raw("https://example.com/a", "Hello again", "s2"),
    ]
    out = norm.normalize(items, {"s1": mk_source(5), "s2": mk_source(9)})
    assert len(out) == 1
    # il duplicato con authority più alta vince
    assert out[0].source_id == "s2"


def test_dedup_by_fuzzy_title() -> None:
    norm = Normalizer()
    items = [
        mk_raw("https://a.com/x", "Google Releases New Core Update for Search", "s1"),
        mk_raw("https://b.com/y", "Google releases new core update for search!", "s2"),
    ]
    out = norm.normalize(items, {"s1": mk_source(5), "s2": mk_source(10)})
    assert len(out) == 1
    assert out[0].source_id == "s2"


def test_filter_too_old() -> None:
    norm = Normalizer(max_age_hours=48)
    old_item = RawItem(
        title="Old", url="https://a.com/old", source_id="s1",
        published_at=datetime.now(UTC) - timedelta(hours=72),
        content="some content",
    )
    out = norm.normalize([old_item], {"s1": mk_source()})
    assert out == []


def test_filter_too_short() -> None:
    norm = Normalizer()
    short = mk_raw("https://a.com/short", "Hi", "s1", content="tiny")
    out = norm.normalize([short], {"s1": mk_source()})
    assert out == []
