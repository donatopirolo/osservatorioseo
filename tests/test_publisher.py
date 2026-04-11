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
            id="s",
            name="S",
            authority=5,
            type="official",
            fetcher="rss",
            feed_url="https://x.com",
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
            sources_checked=1,
            sources_failed=0,
            items_collected=1,
            items_after_dedup=1,
            doc_changes_detected=0,
            ai_cost_eur=0.01,
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
    # Il dated file archive è scritto
    archive_dated = list((tmp_path / "archive").glob("20*.json"))
    assert len(archive_dated) == 1
    # L'index.json dell'archivio è scritto
    assert (tmp_path / "archive" / "index.json").exists()


def test_publish_creates_archive_index(tmp_path: Path) -> None:
    pub = Publisher(data_dir=tmp_path, archive_dir=tmp_path / "archive")
    # Simula 2 run precedenti creando direttamente i file
    (tmp_path / "archive").mkdir(parents=True, exist_ok=True)
    (tmp_path / "archive" / "2026-04-09.json").write_text("{}", encoding="utf-8")
    (tmp_path / "archive" / "2026-04-10.json").write_text("{}", encoding="utf-8")
    pub.publish(mk_feed())  # genera il 3° file dated per oggi
    index_path = tmp_path / "archive" / "index.json"
    index = json.loads(index_path.read_text())
    assert isinstance(index, list)
    dates = [e["date"] for e in index]
    assert "2026-04-09" in dates
    assert "2026-04-10" in dates
    # Ordine discendente: la più recente per prima
    assert dates == sorted(dates, reverse=True)
    # L'index non include sé stesso
    assert "index" not in dates


def test_publish_copies_to_site_data(tmp_path: Path) -> None:
    site_dir = tmp_path / "site" / "data"
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir,
    )
    pub.publish(mk_feed())
    assert (site_dir / "feed.json").exists()


def test_publish_config_snapshot(tmp_path: Path) -> None:
    from osservatorio_seo.config import DocWatcherPage

    site_dir = tmp_path / "site" / "data"
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir,
    )
    sources = [
        Source(
            id="s1",
            name="Source One",
            authority=9,
            type="official",
            fetcher="rss",
            feed_url="https://example.com/rss",
            category_hint="google_updates",
        ),
        Source(
            id="s2",
            name="Source Two",
            authority=7,
            type="media",
            fetcher="scraper",
            target_url="https://example2.com/news",
        ),
    ]
    pages = [
        DocWatcherPage(
            id="p1",
            name="Page One",
            url="https://docs.example.com/p1",
            type="html",
            importance=5,
            category="google_docs_change",
        ),
    ]
    pub.publish_config_snapshot(sources, pages)

    target = tmp_path / "data" / "config_snapshot.json"
    assert target.exists()
    data = json.loads(target.read_text())
    ids = [s["id"] for s in data["sources"]]
    assert ids == ["s1", "s2"]
    assert data["sources"][0]["name"] == "Source One"
    assert data["sources"][0]["url"] == "https://example.com/rss"
    assert data["sources"][1]["url"] == "https://example2.com/news"
    assert len(data["doc_watcher_pages"]) == 1
    assert data["doc_watcher_pages"][0]["id"] == "p1"
    assert data["doc_watcher_pages"][0]["importance"] == 5
    # Site copy
    site_copy = site_dir / "config_snapshot.json"
    assert site_copy.exists()
    assert site_copy.read_text() == target.read_text()


def test_publish_copies_archive_directory_to_site(tmp_path: Path) -> None:
    site_dir = tmp_path / "site" / "data"
    archive_dir = tmp_path / "data" / "archive"
    # Pre-popolo archivio con 2 file da un "ieri"
    archive_dir.mkdir(parents=True, exist_ok=True)
    (archive_dir / "2026-04-09.json").write_text('{"old": 1}', encoding="utf-8")
    (archive_dir / "2026-04-10.json").write_text('{"old": 2}', encoding="utf-8")

    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=archive_dir,
        site_data_dir=site_dir,
    )
    pub.publish(mk_feed())

    # L'archivio viene copiato sotto site/data/archive/
    site_archive = site_dir / "archive"
    assert site_archive.exists()
    copied_dated = sorted(f.name for f in site_archive.glob("20*.json"))
    # 2 file pre-esistenti + 1 di oggi dal feed
    assert len(copied_dated) == 3
    assert "2026-04-09.json" in copied_dated
    assert "2026-04-10.json" in copied_dated
    # L'index è copiato anche lui
    assert (site_archive / "index.json").exists()
