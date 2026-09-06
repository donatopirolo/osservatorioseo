import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from osservatorio_seo.models import Feed, FeedStats, Item, Source
from osservatorio_seo.publisher import Publisher, _absolute_date, _meta_description, format_date_it


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


def mk_doc_item(item_id: str) -> Item:
    it = mk_item(item_id)
    it.is_doc_change = True
    it.category = "google_docs_change"
    return it


def mk_feed_on(day: datetime, items: list[Item]) -> Feed:
    feed = mk_feed()
    feed.generated_at = day
    feed.generated_at_local = day
    feed.items = items
    feed.categories = {}
    for it in items:
        feed.categories.setdefault(it.category, []).append(it.id)
    feed.top10 = [it.id for it in items]
    return feed


def test_publish_preserves_doc_change_items_on_same_day_rerun(tmp_path: Path) -> None:
    """Un secondo run nello stesso giorno non deve cancellare i doc-change item
    pubblicati dal primo run (regressione: overwrite totale dell'archivio)."""
    archive_dir = tmp_path / "archive"
    pub = Publisher(data_dir=tmp_path, archive_dir=archive_dir)
    day = datetime(2026, 5, 16, 7, 0, tzinfo=UTC)

    # Run 1: rileva la modifica alle linee guida e la pubblica
    pub.publish(mk_feed_on(day, [mk_item("news_a"), mk_doc_item("doc_spam")]))

    # Run 2 (stesso giorno): nessun doc-change rilevato, solo notizie normali
    pub.publish(mk_feed_on(day, [mk_item("news_a"), mk_item("news_b")]))

    archive = json.loads((archive_dir / "2026-05-16.json").read_text())
    ids = {i["id"] for i in archive["items"]}
    # Il doc item del primo run deve sopravvivere
    assert "doc_spam" in ids, "doc-change item cancellato dal secondo run"
    doc = next(i for i in archive["items"] if i["id"] == "doc_spam")
    assert doc["is_doc_change"] is True
    # Ed è referenziato nella categoria così da essere renderizzato
    assert "doc_spam" in archive["categories"].get("google_docs_change", [])
    # Le notizie normali del secondo run ci sono comunque
    assert "news_b" in ids

    feed_json = json.loads((tmp_path / "feed.json").read_text())
    feed_ids = {i["id"] for i in feed_json["items"]}
    assert "doc_spam" in feed_ids, "doc-change item assente da feed.json dopo il secondo run"
    feed_doc = next(i for i in feed_json["items"] if i["id"] == "doc_spam")
    assert feed_doc["is_doc_change"] is True
    assert "doc_spam" in feed_json["categories"].get("google_docs_change", [])
    assert "news_b" in feed_ids


def test_select_google_updates_only_google_sources() -> None:
    """La sezione mostra SOLO item da fonte ufficiale Google o doc-change Google;
    gli articoli di terze parti che parlano di Google sono esclusi."""
    base = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)

    def mk(item_id, source_id, imp, days_ago, *, doc=False):
        it = mk_item(item_id)
        it.source = Source(
            id=source_id,
            name=source_id,
            authority=10,
            type="official",
            fetcher="rss",
            feed_url="https://x.com",
        )
        it.importance = imp
        it.published_at = base - timedelta(days=days_ago)
        it.is_doc_change = doc
        return it

    items = [
        # Terza parte che parla di Google (es. spam update via Roundtable) → escluso
        mk("ser_spam", "search_engine_roundtable", 4, 0),
        # Fonte ufficiale Google → incluso
        mk("g_blog", "google_search_central_blog", 5, 1),
        # Doc-change (fonte = documentazione Google) → incluso
        mk("g_doc", "doc_watcher", 5, 0, doc=True),
        # Fonte Google ma sotto soglia (es. annuncio evento imp2) → escluso
        mk("g_event", "google_search_central_blog", 2, 0),
    ]
    result = Publisher._select_google_updates(items, limit=10, min_importance=3)
    ids = [i.id for i in result]

    assert "ser_spam" not in ids  # terza parte
    assert "g_event" not in ids  # sotto soglia
    assert set(ids) == {"g_doc", "g_blog"}
    assert ids == ["g_doc", "g_blog"]  # importanza pari → recency desc (doc è più recente)

    # Il cap limita il numero di item
    assert len(Publisher._select_google_updates(items, limit=1, min_importance=3)) == 1


def test_absolute_date_converts_utc_to_rome_local(monkeypatch) -> None:
    """Regressione: _absolute_date formattava published_at (sempre UTC) senza
    convertirlo in ora locale Europe/Rome. Un item pubblicato la sera tardi in
    UTC puo' cadere nel giorno dopo a Roma (CEST = UTC+2): qui verifichiamo
    che la data mostrata avanzi di giorno, indipendentemente dal TZ del
    processo (la conversione usa ZoneInfo('Europe/Rome') fisso, non il TZ
    di sistema)."""
    with monkeypatch.context() as m:
        m.setenv("TZ", "UTC")
        time.tzset()
        published = datetime(2026, 4, 11, 22, 30, tzinfo=UTC)
        result = _absolute_date(published)
    time.tzset()

    # 22:30 UTC + 2h (CEST) = 00:30 del giorno dopo a Roma
    parts = result.split()
    assert parts[1] == "12", f"giorno non convertito a Roma: {result!r}"
    assert result.endswith("00:30"), f"ora non convertita a Roma: {result!r}"


def test_format_date_it_uses_italian_day_and_month_names() -> None:
    """Regressione 1.7: strftime('%A ... %B ...') dipende dalla locale di
    sistema, assente sui runner (produce 'Sunday'/'April' in inglese).
    format_date_it deve restare in italiano indipendentemente dalla locale."""
    dt = datetime(2026, 4, 12, 0, 30)  # domenica
    result = format_date_it(dt, "%A %-d %B %Y, %H:%M")
    assert result == "Domenica 12 Aprile 2026, 00:30"


def test_format_date_it_leaves_numeric_directives_untouched() -> None:
    dt = datetime(2026, 9, 3)
    assert format_date_it(dt, "%d %B %Y") == "03 Settembre 2026"
    assert format_date_it(dt, "%Y-%m-%d") == "2026-09-03"


def test_meta_description_cuts_on_word_boundary() -> None:
    """Regressione 1.7: un taglio secco a lunghezza fissa spezza le parole a
    meta' su circa la meta' dei summary reali dell'archivio (es. 'sn' invece
    di 'snippet'). Il taglio deve tornare indietro fino all'ultimo spazio."""
    words = ["Questa", "frase", "contiene", "diverse", "parole", "distinte", "per", "il", "test"]
    text = " ".join(words)
    # max_len scelto apposta a meta' di una parola ("distinte" -> "disti|nte")
    result = _meta_description(text, max_len=text.index("distinte") + 5)
    assert result.endswith("…")
    kept_words = result[:-1].split()
    assert kept_words == words[: len(kept_words)]  # solo parole intere, niente troncate


def test_meta_description_leaves_short_text_untouched() -> None:
    assert _meta_description("Testo breve.", max_len=155) == "Testo breve."


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


def test_publish_ssg_writes_snapshot(tmp_path: Path) -> None:
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

    # La hub /hub/ del giorno e' stata rimossa (1.3): 155 pagine thin-content
    # duplicate dello snapshot, non linkate da nessun template.
    day_hub = site_dir / "archivio" / y / m / d / "hub" / "index.html"
    assert not day_hub.exists()


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


def test_publish_ssg_article_date_published_is_site_date_not_source(tmp_path: Path) -> None:
    """NewsArticle.datePublished deve essere la data di pubblicazione SUL
    SITO (feed.generated_at), non quella della fonte (item.published_at):
    volutamente diverse in questo test (1.5/D5)."""
    site_dir = tmp_path / "site"
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir / "data",
    )
    item = mk_item("a")
    item.importance = 5
    item.published_at = datetime(2026, 4, 9, 12, 0, tzinfo=UTC)
    feed = mk_feed_on(datetime(2026, 4, 11, 7, 0, tzinfo=UTC), [item])
    pub.publish_ssg(feed, [], [], templates_dir=Path("templates"), site_dir=site_dir)

    day_dir = site_dir / "archivio" / "2026" / "04" / "11"
    article_dir = next(p for p in day_dir.iterdir() if p.is_dir())
    article_html = (article_dir / "index.html").read_text()
    assert '"datePublished": "2026-04-11T07:00:00+00:00"' in article_html
    assert '"dateModified": "2026-04-11T07:00:00+00:00"' in article_html


def test_publish_ssg_skips_article_page_for_url_published_earlier(tmp_path: Path) -> None:
    """Se lo stesso URL ha gia' una pagina in un giorno precedente (es. una
    fonte ripubblica un articolo vecchio senza cambiare URL), non va
    generata una seconda pagina articolo per il giorno corrente (1.4)."""
    site_dir = tmp_path / "site"
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir / "data",
    )

    old_item = mk_item("old")
    old_item.importance = 5
    old_item.url = "https://example.com/shared-article"
    old_feed = mk_feed_on(datetime(2026, 4, 10, 7, 0, tzinfo=UTC), [old_item])
    pub.publish(old_feed)
    pub.publish_ssg(
        old_feed, [], [], templates_dir=Path("templates"), site_dir=site_dir, allow_indexing=True
    )

    new_item = mk_item("new")
    new_item.importance = 5
    new_item.url = "https://example.com/shared-article"  # stesso URL del giorno prima
    new_feed = mk_feed_on(datetime(2026, 4, 11, 7, 0, tzinfo=UTC), [new_item])
    pub.publish(new_feed)

    pub.publish_ssg(
        new_feed, [], [], templates_dir=Path("templates"), site_dir=site_dir, allow_indexing=True
    )

    # Il giorno vecchio ha la sua pagina...
    assert (site_dir / "archivio" / "2026" / "04" / "10" / "old" / "index.html").exists()
    # ...ma il giorno nuovo NON genera una seconda pagina per lo stesso URL.
    new_day_dir = site_dir / "archivio" / "2026" / "04" / "11"
    article_dirs = [p for p in new_day_dir.iterdir() if p.is_dir() and p.name != "hub"]
    assert article_dirs == []


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


def test_publish_ssg_snapshot_breadcrumb_uses_month_name(tmp_path: Path) -> None:
    """Regressione 1.7: il breadcrumb dello snapshot mostrava '05' invece di
    'Maggio' (la etichetta era il numero del mese, non _MONTH_LABELS)."""
    site_dir = tmp_path / "site"
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir / "data",
    )
    feed = mk_feed_on(datetime(2026, 5, 16, 7, 0, tzinfo=UTC), [mk_item("a")])
    pub.publish_ssg(feed, [], [], templates_dir=Path("templates"), site_dir=site_dir)

    snapshot_html = (site_dir / "archivio" / "2026" / "05" / "16" / "index.html").read_text()
    assert '"name": "Maggio"' in snapshot_html
    assert '"name": "05"' not in snapshot_html


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
    feed_xml_text = feed_xml.read_text()
    assert "<feed xmlns" in feed_xml_text
    # item "a" ha importance 3 (mk_item), quindi non e' indicizzabile e non ha
    # una pagina interna: il link nel feed deve restare l'URL esterno della
    # fonte cosi' com'e', non "osservatorioseo.com/https://..." (bug 1.6).
    assert '<link href="https://example.com/a" />' in feed_xml_text
    assert "osservatorioseo.com/https://" not in feed_xml_text
    robots = site_dir / "robots.txt"
    assert robots.exists()
    assert "Disallow: /" in robots.read_text()
    assert "Sitemap:" in robots.read_text()


def test_publish_ssg_sitemap_includes_past_days_with_real_lastmod(tmp_path: Path) -> None:
    """La sitemap deve includere snapshot e articoli di TUTTI i giorni
    archiviati (non solo il run corrente), ciascuno col proprio lastmod
    (regressione: prima 'lastmod' era 'oggi' su ogni URL e gli articoli dei
    giorni precedenti sparivano dalla sitemap a ogni run)."""
    site_dir = tmp_path / "site"
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir / "data",
    )

    old_item = mk_item("old")
    old_item.importance = 5
    old_feed = mk_feed_on(datetime(2026, 4, 10, 7, 0, tzinfo=UTC), [old_item])
    pub.publish(old_feed)

    new_item = mk_item("new")
    new_item.importance = 5
    new_feed = mk_feed_on(datetime(2026, 4, 11, 7, 0, tzinfo=UTC), [new_item])
    pub.publish(new_feed)

    pub.publish_ssg(
        new_feed, [], [], templates_dir=Path("templates"), site_dir=site_dir, allow_indexing=True
    )

    sitemap = (site_dir / "sitemap.xml").read_text()
    assert "/archivio/2026/04/10/" in sitemap
    assert "<lastmod>2026-04-10</lastmod>" in sitemap
    assert "/archivio/2026/04/11/" in sitemap
    assert "<lastmod>2026-04-11</lastmod>" in sitemap
    # Lo slug e' derivato dal titolo (== item_id nei fixture di test)
    assert "/archivio/2026/04/10/old/" in sitemap
    assert "/archivio/2026/04/11/new/" in sitemap


def test_publish_ssg_sitemap_excludes_cross_day_republished_url(tmp_path: Path) -> None:
    """La sitemap non deve elencare la pagina del secondo giorno per un URL
    gia' pubblicato in un giorno precedente (1.4): quella pagina non viene
    piu' generata (in 301 verso la prima), quindi non va nemmeno in sitemap
    (regressione: _build_item_index applicava is_indexable ma non il
    dedup cross-day di publish_ssg, elencando URL redirect-301 in sitemap)."""
    site_dir = tmp_path / "site"
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir / "data",
    )

    old_item = mk_item("old")
    old_item.importance = 5
    old_item.url = "https://example.com/shared-article"
    old_feed = mk_feed_on(datetime(2026, 4, 10, 7, 0, tzinfo=UTC), [old_item])
    pub.publish(old_feed)

    new_item = mk_item("new")
    new_item.importance = 5
    new_item.url = "https://example.com/shared-article"
    new_feed = mk_feed_on(datetime(2026, 4, 11, 7, 0, tzinfo=UTC), [new_item])
    pub.publish(new_feed)

    pub.publish_ssg(
        new_feed, [], [], templates_dir=Path("templates"), site_dir=site_dir, allow_indexing=True
    )

    sitemap = (site_dir / "sitemap.xml").read_text()
    assert "/archivio/2026/04/10/old/" in sitemap
    assert "/archivio/2026/04/11/new/" not in sitemap


def test_publish_ssg_news_sitemap_uses_site_publication_date(tmp_path: Path) -> None:
    """news:publication_date deve essere la data di pubblicazione SUL SITO
    (feed.generated_at), non quella della fonte (item.published_at): sono
    volutamente diverse in questo test per non poter passare per caso."""
    site_dir = tmp_path / "site"
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir / "data",
    )
    item = mk_item("fresh")
    item.importance = 5
    item.published_at = datetime.now(UTC) - timedelta(hours=2)
    generated_at = datetime.now(UTC) - timedelta(hours=1)
    feed = mk_feed_on(generated_at, [item])
    pub.publish(feed)
    pub.publish_ssg(
        feed, [], [], templates_dir=Path("templates"), site_dir=site_dir, allow_indexing=True
    )

    news_sitemap = (site_dir / "sitemap-news.xml").read_text()
    assert feed.generated_at.isoformat() in news_sitemap
    assert item.published_at.isoformat() not in news_sitemap


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
