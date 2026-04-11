import json
from datetime import UTC, datetime
from pathlib import Path

from osservatorio_seo.models import Feed, FeedStats, Item, Source
from osservatorio_seo.publisher import Publisher


def mk_item(item_id: str) -> Item:
    return Item(
        id=item_id,
        title_original=item_id,
        title_it=item_id,
        summary_it="s",
        url=f"https://example.com/{item_id}",
        source=Source(
            id="s", name="S", authority=5, type="official",
            fetcher="rss", feed_url="https://x.com",
        ),
        category="google_updates",
        tags=[],
        importance=3,
        published_at=datetime.now(UTC),
        fetched_at=datetime.now(UTC),
        is_doc_change=False,
        language_original="en",
        summarizer_model="x",
        raw_hash="x",
    )


def mk_feed() -> Feed:
    return Feed(
        generated_at=datetime.now(UTC),
        generated_at_local=datetime.now(UTC),
        timezone="Europe/Rome",
        run_id="2026-04-11-0700",
        stats=FeedStats(
            sources_checked=1, sources_failed=0, items_collected=1,
            items_after_dedup=1, doc_changes_detected=0, ai_cost_eur=0.01,
        ),
        top10=["a"],
        categories={"google_updates": ["a"]},
        items=[mk_item("a")],
        doc_watcher_status=[],
        failed_sources=[],
    )


def test_publish_writes_feed_and_archive(tmp_path: Path) -> None:
    pub = Publisher(data_dir=tmp_path, archive_dir=tmp_path / "archive")
    feed = mk_feed()
    pub.publish(feed)
    feed_file = tmp_path / "feed.json"
    assert feed_file.exists()
    data = json.loads(feed_file.read_text())
    assert data["run_id"] == "2026-04-11-0700"
    archive_files = list((tmp_path / "archive").glob("*.json"))
    assert len(archive_files) == 1


def test_publish_copies_to_site_data(tmp_path: Path) -> None:
    site_dir = tmp_path / "site" / "data"
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir,
    )
    pub.publish(mk_feed())
    assert (site_dir / "feed.json").exists()
