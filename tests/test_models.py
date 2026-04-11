# tests/test_models.py
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from osservatorio_seo.models import (
    Feed,
    FeedStats,
    Item,
    RawItem,
    Source,
)


def test_source_creation() -> None:
    src = Source(
        id="google_search_central",
        name="Google Search Central Blog",
        authority=10,
        type="official",
        fetcher="rss",
        feed_url="https://developers.google.com/search/blog/rss",
    )
    assert src.authority == 10
    assert src.enabled is True


def test_source_authority_out_of_range() -> None:
    with pytest.raises(ValidationError):
        Source(
            id="x",
            name="x",
            authority=11,
            type="official",
            fetcher="rss",
            feed_url="https://x.com",
        )


def test_raw_item_minimal() -> None:
    item = RawItem(
        title="March Core Update done",
        url="https://example.com/a",
        source_id="google_search_central",
        published_at=datetime.now(UTC),
        content="Some content here",
    )
    assert item.language_original == "en"


def test_item_full() -> None:
    item = Item(
        id="item_2026-04-11_001",
        title_original="March Core Update done",
        title_it="Il Core Update di marzo è finito",
        summary_it="Google ha completato il rollout.",
        url="https://example.com/a",
        source=Source(
            id="g",
            name="Google",
            authority=10,
            type="official",
            fetcher="rss",
            feed_url="https://x.com",
        ),
        category="google_updates",
        tags=["core_update"],
        importance=5,
        published_at=datetime.now(UTC),
        fetched_at=datetime.now(UTC),
        is_doc_change=False,
        language_original="en",
        summarizer_model="google/gemini-2.0-flash",
        raw_hash="sha256:abc",
    )
    assert item.importance == 5


def test_item_importance_range() -> None:
    base = {
        "id": "x",
        "title_original": "x",
        "title_it": "x",
        "summary_it": "x",
        "url": "https://x.com",
        "source": Source(
            id="g",
            name="G",
            authority=5,
            type="official",
            fetcher="rss",
            feed_url="https://x.com",
        ),
        "category": "google_updates",
        "tags": [],
        "published_at": datetime.now(UTC),
        "fetched_at": datetime.now(UTC),
        "is_doc_change": False,
        "language_original": "en",
        "summarizer_model": "x",
        "raw_hash": "x",
    }
    with pytest.raises(ValidationError):
        Item(**{**base, "importance": 6})
    with pytest.raises(ValidationError):
        Item(**{**base, "importance": 0})


def test_feed_serialization_round_trip() -> None:
    feed = Feed(
        schema_version="1.0",
        generated_at=datetime.now(UTC),
        generated_at_local=datetime.now(UTC),
        timezone="Europe/Rome",
        run_id="2026-04-11-0700",
        stats=FeedStats(
            sources_checked=10,
            sources_failed=0,
            items_collected=15,
            items_after_dedup=12,
            doc_changes_detected=0,
            ai_cost_eur=0.0,
        ),
        top10=[],
        categories={},
        items=[],
        doc_watcher_status=[],
        failed_sources=[],
    )
    dumped = feed.model_dump(mode="json")
    restored = Feed.model_validate(dumped)
    assert restored.schema_version == "1.0"
