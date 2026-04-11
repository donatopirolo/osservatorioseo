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


# =============================================================================
# SSG tests
# =============================================================================


def test_publish_ssg_writes_homepage(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir / "data",
    )
    feed = mk_feed()
    pub.publish_ssg(feed, [], [], templates_dir=Path("templates"), site_dir=site_dir)
    index_html = site_dir / "index.html"
    assert index_html.exists()
    content = index_html.read_text()
    assert "OSSERVATORIO_SEO" in content
    assert 'id="top10"' in content
    assert "01." in content
    assert mk_feed().items[0].title_it in content


def test_publish_ssg_writes_snapshot_and_day_hub(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir / "data",
    )
    feed = mk_feed()
    pub.publish_ssg(feed, [], [], templates_dir=Path("templates"), site_dir=site_dir)

    day_iso = feed.generated_at_local.strftime("%Y-%m-%d")
    y, m, d = day_iso.split("-")
    snapshot = site_dir / "archivio" / y / m / d / "index.html"
    assert snapshot.exists()
    assert f"TOP 10 DEL GIORNO {d} {m} {y}" in snapshot.read_text()

    day_hub = site_dir / "archivio" / y / m / d / "hub" / "index.html"
    assert day_hub.exists()


def test_publish_ssg_writes_article_for_high_importance(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir / "data",
    )
    feed = mk_feed()
    feed.items[0].importance = 5
    pub.publish_ssg(feed, [], [], templates_dir=Path("templates"), site_dir=site_dir)

    day_iso = feed.generated_at_local.strftime("%Y-%m-%d")
    y, m, d = day_iso.split("-")
    articles = [
        p for p in (site_dir / "archivio" / y / m / d).iterdir() if p.is_dir() and p.name != "hub"
    ]
    assert len(articles) == 1
    article_html = (articles[0] / "index.html").read_text()
    assert '"@type": "NewsArticle"' in article_html
    assert '"@type": "BreadcrumbList"' in article_html


def test_publish_ssg_writes_archive_hubs(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    archive_dir = tmp_path / "data" / "archive"
    archive_dir.mkdir(parents=True)
    (archive_dir / "2026-04-10.json").write_text("{}")
    (archive_dir / "2026-04-11.json").write_text("{}")

    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=archive_dir,
        site_data_dir=site_dir / "data",
    )
    pub.publish_ssg(mk_feed(), [], [], templates_dir=Path("templates"), site_dir=site_dir)

    assert (site_dir / "archivio" / "index.html").exists()
    assert (site_dir / "archivio" / "2026" / "index.html").exists()
    assert (site_dir / "archivio" / "2026" / "04" / "index.html").exists()


def test_publish_ssg_writes_category_hub(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir / "data",
    )
    pub.publish_ssg(mk_feed(), [], [], templates_dir=Path("templates"), site_dir=site_dir)
    cat_html = site_dir / "categoria" / "google-updates" / "index.html"
    assert cat_html.exists()
    assert "Google Updates" in cat_html.read_text()


def test_publish_ssg_writes_docs_about_sitemap_feed_robots(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir / "data",
    )
    pub.publish_ssg(mk_feed(), [], [], templates_dir=Path("templates"), site_dir=site_dir)
    assert (site_dir / "docs" / "index.html").exists()
    assert (site_dir / "about" / "index.html").exists()
    sitemap = site_dir / "sitemap.xml"
    assert sitemap.exists()
    assert "<loc>" in sitemap.read_text()
    feed_xml = site_dir / "feed.xml"
    assert feed_xml.exists()
    assert "<feed xmlns" in feed_xml.read_text()
    robots = site_dir / "robots.txt"
    assert robots.exists()
    assert "Disallow: /" in robots.read_text()
    assert "Sitemap:" in robots.read_text()


def test_publish_ssg_writes_top_week(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    archive_dir = tmp_path / "data" / "archive"
    archive_dir.mkdir(parents=True)
    # Seed 2 giorni di feed nell'archivio
    for d_str in ("2026-04-09", "2026-04-10"):
        feed = mk_feed()
        feed.run_id = f"{d_str}-0700"
        feed.generated_at = datetime(
            int(d_str[:4]), int(d_str[5:7]), int(d_str[8:10]), 5, 0, tzinfo=UTC
        )
        feed.generated_at_local = feed.generated_at
        (archive_dir / f"{d_str}.json").write_text(feed.model_dump_json(indent=2), encoding="utf-8")

    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=archive_dir,
        site_data_dir=site_dir / "data",
    )
    pub.publish_ssg(mk_feed(), [], [], templates_dir=Path("templates"), site_dir=site_dir)

    top_week = site_dir / "top-settimana" / "index.html"
    assert top_week.exists()
    content = top_week.read_text()
    assert "TOP 10 DELLA SETTIMANA" in content


def test_publish_ssg_config_snapshot_for_docs(tmp_path: Path) -> None:
    from osservatorio_seo.config import DocWatcherPage

    site_dir = tmp_path / "site"
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir / "data",
    )
    sources = [
        Source(
            id="s1",
            name="Source One",
            authority=9,
            type="official",
            fetcher="rss",
            feed_url="https://example.com/rss",
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
    pub.publish_ssg(mk_feed(), sources, pages, templates_dir=Path("templates"), site_dir=site_dir)
    docs_html = (site_dir / "docs" / "index.html").read_text()
    assert "Source One" in docs_html
    assert "Page One" in docs_html
