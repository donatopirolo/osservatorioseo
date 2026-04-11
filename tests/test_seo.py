from datetime import UTC, datetime

from osservatorio_seo.models import Item, Source
from osservatorio_seo.seo import (
    article_path,
    category_path,
    day_path,
    month_path,
    tag_path,
    year_path,
)


def mk_item(
    item_id: str = "item_2026-04-11_001",
    title_it: str = "Google rilascia il Core Update",
) -> Item:
    return Item(
        id=item_id,
        title_original="Google releases the Core Update",
        title_it=title_it,
        summary_it="s",
        url="https://example.com/a",
        source=Source(
            id="src",
            name="Src",
            authority=9,
            type="official",
            fetcher="rss",
            feed_url="https://x.com",
        ),
        category="google_updates",
        tags=["core_update"],
        importance=5,
        published_at=datetime(2026, 4, 11, 7, 0, tzinfo=UTC),
        fetched_at=datetime(2026, 4, 11, 7, 0, tzinfo=UTC),
        is_doc_change=False,
        language_original="en",
        summarizer_model="x",
        raw_hash="x",
    )


def test_year_path() -> None:
    assert year_path(2026) == "/archivio/2026/"


def test_month_path() -> None:
    assert month_path(2026, 4) == "/archivio/2026/04/"


def test_day_path() -> None:
    assert day_path(2026, 4, 11) == "/archivio/2026/04/11/"


def test_article_path() -> None:
    item = mk_item()
    path = article_path(item, date_str="2026-04-11", slug="google-rilascia-core-update")
    assert path == "/archivio/2026/04/11/google-rilascia-core-update/"


def test_category_path() -> None:
    assert category_path("google_updates") == "/categoria/google-updates/"


def test_tag_path() -> None:
    assert tag_path("core_update") == "/tag/core-update/"
    assert tag_path("ai_overviews") == "/tag/ai-overviews/"
