from datetime import UTC, datetime, timedelta

from osservatorio_seo.models import RawItem, Source
from osservatorio_seo.normalizer import Normalizer


def mk_source(authority: int = 5) -> Source:
    return Source(
        id=f"src{authority}",
        name=f"src{authority}",
        authority=authority,
        type="media",
        fetcher="rss",
        feed_url="https://example.com/feed",
    )


def mk_raw(
    url: str, title: str, source_id: str, content: str = "enough content here for normalization"
) -> RawItem:
    return RawItem(
        title=title,
        url=url,
        source_id=source_id,
        published_at=datetime.now(UTC),
        content=content,
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


def test_no_dedup_for_distinct_stories_same_topic() -> None:
    """Titoli reali dall'archivio del 2026-06-03 (stessa fonte, stesso
    argomento — il Google May 2026 Core Update — ma DUE notizie diverse:
    la volatilita' che riprende il 2 giugno, e il rollout completato).
    token_set_ratio tra i due e' 69: sotto la soglia 80, non deve collassare.
    """
    norm = Normalizer()
    items = [
        mk_raw(
            "https://a.com/x",
            "Google May 2026 Core Update Volatility Hits Hard Again June 2nd",
            "s1",
        ),
        mk_raw(
            "https://b.com/y",
            "Google May 2026 Core Update Has Completed Rolling Out",
            "s1",
        ),
    ]
    out = norm.normalize(items, {"s1": mk_source(5)})
    assert len(out) == 2


def test_filter_too_old() -> None:
    norm = Normalizer(max_age_hours=48)
    old_item = RawItem(
        title="Old",
        url="https://a.com/old",
        source_id="s1",
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


def test_no_dedup_on_subset_titles_regression() -> None:
    """Regressione: titoli reali dell'archivio che NON devono collassare.

    Un tentativo di aggiungere ``fuzz.token_set_ratio >= 80`` al dedup
    (2026-09-06) produceva 3 falsi positivi su 5 collassi sui dati veri:
    token_set_ratio vale 100 quando un titolo e' sottoinsieme dell'altro.
    Queste coppie sono notizie distinte e devono restare due.
    """
    coppie = [
        (
            "The 50 Most-Cited Websites in Google AI Overviews (June 2026)",
            "The 50 Most-Cited Websites in Grok (June 2026)",
        ),
        (
            "Google Answers Why Search Updates Aren't Announced Right Away",
            "Google Answers Why Spam Updates Need To Happen",
        ),
        (
            "Search News Buzz Video Recap: Google Search Breaks Usage Records",
            "Google Search Console adds social and video reports",
        ),
    ]
    norm = Normalizer()
    for i, (t1, t2) in enumerate(coppie):
        items = [
            mk_raw(f"https://a.example/{i}", t1, "s1"),
            mk_raw(f"https://b.example/{i}", t2, "s2"),
        ]
        out = norm.normalize(items, {"s1": mk_source(5), "s2": mk_source(10)})
        assert len(out) == 2, f"collassate erroneamente: {t1!r} / {t2!r}"
