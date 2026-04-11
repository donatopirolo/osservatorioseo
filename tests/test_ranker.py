from datetime import UTC, datetime, timedelta

from osservatorio_seo.models import Item, Source
from osservatorio_seo.ranker import Ranker


def mk_item(
    item_id: str,
    importance: int,
    authority: int,
    category: str = "google_updates",
    is_doc_change: bool = False,
    hours_ago: float = 1.0,
) -> Item:
    return Item(
        id=item_id,
        title_original=item_id,
        title_it=item_id,
        summary_it="summary",
        url=f"https://example.com/{item_id}",
        source=Source(
            id=f"src-{item_id}",
            name="src",
            authority=authority,
            type="official",
            fetcher="rss",
            feed_url="https://x.com",
        ),
        category=category,  # type: ignore[arg-type]
        tags=[],
        importance=importance,
        published_at=datetime.now(UTC) - timedelta(hours=hours_ago),
        fetched_at=datetime.now(UTC),
        is_doc_change=is_doc_change,
        language_original="en",
        summarizer_model="x",
        raw_hash="x",
    )


def test_higher_importance_ranks_first() -> None:
    items = [
        mk_item("low", importance=1, authority=5),
        mk_item("high", importance=5, authority=5),
    ]
    r = Ranker()
    top10, by_cat = r.rank(items)
    assert top10[0] == "high"


def test_doc_change_bonus() -> None:
    items = [
        mk_item("normal", importance=5, authority=10, category="google_updates"),
        mk_item(
            "doc", importance=5, authority=10, category="google_docs_change", is_doc_change=True
        ),
    ]
    top10, _ = Ranker().rank(items)
    assert top10[0] == "doc"


def test_top10_limits_to_ten() -> None:
    items = [mk_item(f"i{i}", importance=3, authority=5) for i in range(20)]
    top10, _ = Ranker().rank(items)
    assert len(top10) == 10


def test_categories_populated() -> None:
    items = [
        mk_item("a", 3, 5, category="google_updates"),
        mk_item("b", 4, 5, category="ai_models"),
        mk_item("c", 2, 5, category="google_updates"),
    ]
    _, by_cat = Ranker().rank(items)
    assert by_cat["google_updates"] == ["a", "c"]  # order by score desc
    assert by_cat["ai_models"] == ["b"]
