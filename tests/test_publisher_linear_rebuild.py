"""Tests for publish_day / publish_global (task 4.2, rebuild lineare).

scripts/rebuild_seo_html.py used to call publish_ssg() once per archived
day, which redoes ALL the global work (homepage, hubs, sitemap, tracker,
dossier) on every single call even though only the last one's output
survives on disk. publish_day() writes only the day-specific permanent
pages (snapshot + articles); publish_global() does the rest, and only
needs to run once with the most recent feed.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from osservatorio_seo.publisher import Publisher
from tests.test_publisher import mk_feed_on, mk_item


def _pub(tmp_path: Path) -> tuple[Publisher, Path]:
    site_dir = tmp_path / "site"
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir / "data",
    )
    return pub, site_dir


def test_publish_day_writes_only_snapshot_and_articles(tmp_path: Path) -> None:
    pub, site_dir = _pub(tmp_path)
    item = mk_item("a")
    item.importance = 5
    feed = mk_feed_on(datetime.now(UTC), [item])

    pub.publish_day(feed, templates_dir=Path("templates"), site_dir=site_dir)

    day_iso = feed.generated_at_local.strftime("%Y-%m-%d")
    y, m, d = day_iso.split("-")
    assert (site_dir / "archivio" / y / m / d / "index.html").exists()
    articles = [
        p for p in (site_dir / "archivio" / y / m / d).iterdir() if p.is_dir() and p.name != "hub"
    ]
    assert len(articles) == 1

    # Niente stato globale: publish_day non lo tocca.
    assert not (site_dir / "index.html").exists()
    assert not (site_dir / "sitemap.xml").exists()
    assert not (site_dir / "categoria").exists()


def test_publish_global_writes_homepage_hub_sitemap_but_not_that_days_snapshot(
    tmp_path: Path,
) -> None:
    pub, site_dir = _pub(tmp_path)
    item = mk_item("b")
    feed = mk_feed_on(datetime.now(UTC), [item])
    pub.publish(feed)  # serve un archivio su disco per hub/sitemap/item-index

    pub.publish_global(feed, [], [], templates_dir=Path("templates"), site_dir=site_dir)

    assert (site_dir / "index.html").exists()
    assert (site_dir / "sitemap.xml").exists()
    assert (site_dir / "categoria" / "google-updates" / "index.html").exists()

    day_iso = feed.generated_at_local.strftime("%Y-%m-%d")
    y, m, d = day_iso.split("-")
    # publish_global non genera la pagina snapshot del giorno: quella e' di
    # publish_day.
    assert not (site_dir / "archivio" / y / m / d / "index.html").exists()


def test_publish_day_then_publish_global_once_matches_full_rebuild(tmp_path: Path) -> None:
    """Il rebuild lineare (publish_day per ogni giorno + publish_global una
    sola volta sull'ultimo) deve coprire nell'output globale finale tutti i
    giorni pubblicati, esattamente come prima quando publish_ssg girava per
    intero su ogni giorno."""
    pub, site_dir = _pub(tmp_path)

    old_day = datetime.now(UTC) - timedelta(days=3)
    latest_day = datetime.now(UTC)

    old_item = mk_item("old_google")
    old_item.importance = 5
    latest_item = mk_item("latest_google")
    latest_item.importance = 5

    feed_old = mk_feed_on(old_day, [old_item])
    feed_latest = mk_feed_on(latest_day, [latest_item])

    # Seed dell'archivio su disco (come farebbe la pipeline quotidiana).
    pub.publish(feed_old)
    pub.publish(feed_latest)

    # Rebuild lineare: un publish_day per giorno, un solo publish_global.
    pub.publish_day(feed_old, templates_dir=Path("templates"), site_dir=site_dir)
    pub.publish_day(feed_latest, templates_dir=Path("templates"), site_dir=site_dir)
    pub.publish_global(feed_latest, [], [], templates_dir=Path("templates"), site_dir=site_dir)

    # Entrambi i giorni hanno la propria pagina permanente.
    for day in (old_day, latest_day):
        y, m, d = day.strftime("%Y-%m-%d").split("-")
        assert (site_dir / "archivio" / y / m / d / "index.html").exists()

    # L'hub di categoria (stato globale, calcolato una sola volta) copre
    # entrambi i giorni, non solo l'ultimo passato a publish_global.
    cat_html = (site_dir / "categoria" / "google-updates" / "index.html").read_text()
    assert "old_google" in cat_html
    assert "latest_google" in cat_html

    # L'homepage riflette il feed piu' recente (quello passato a publish_global).
    home_html = (site_dir / "index.html").read_text()
    assert "latest_google" in home_html

    # Il sitemap copre entrambe le pagine snapshot.
    sitemap = (site_dir / "sitemap.xml").read_text()
    for day in (old_day, latest_day):
        y, m, d = day.strftime("%Y-%m-%d").split("-")
        assert f"/archivio/{y}/{m}/{d}/" in sitemap


def test_publish_ssg_unchanged_still_does_day_and_global_in_one_call(tmp_path: Path) -> None:
    """publish_ssg resta invariato per la pipeline quotidiana: un solo feed,
    scrive sia le pagine del giorno sia lo stato globale in una chiamata."""
    pub, site_dir = _pub(tmp_path)
    item = mk_item("c")
    item.importance = 5
    feed = mk_feed_on(datetime.now(UTC), [item])

    pub.publish_ssg(feed, [], [], templates_dir=Path("templates"), site_dir=site_dir)

    day_iso = feed.generated_at_local.strftime("%Y-%m-%d")
    y, m, d = day_iso.split("-")
    assert (site_dir / "archivio" / y / m / d / "index.html").exists()
    assert (site_dir / "index.html").exists()
    assert (site_dir / "sitemap.xml").exists()


def test_articolo_mostra_le_fonti_secondarie(tmp_path: Path) -> None:
    """Le fonti accorpate finiscono in pagina, non nel nulla.

    Il dedup per titolo attribuisce la notizia alla fonte con autorita' piu'
    alta; le altre restano in `also_in` e devono comparire come "Anche su".
    """
    from osservatorio_seo.models import AlsoIn

    pub, site_dir = _pub(tmp_path)
    item = mk_item("a")
    item.importance = 5
    item.also_in = [
        AlsoIn(
            source_id="sej",
            source_name="Search Engine Journal",
            url="https://www.searchenginejournal.com/x",
        )
    ]
    feed = mk_feed_on(datetime.now(UTC), [item])
    pub.publish_day(feed, templates_dir=Path("templates"), site_dir=site_dir)

    y, m, d = feed.generated_at_local.strftime("%Y-%m-%d").split("-")
    day_dir = site_dir / "archivio" / y / m / d
    article = next(p / "index.html" for p in day_dir.iterdir() if p.is_dir() and p.name != "hub")
    html = article.read_text(encoding="utf-8")

    assert "Anche su" in html
    assert "Search Engine Journal" in html
    assert 'href="https://www.searchenginejournal.com/x"' in html


def test_articolo_senza_fonti_secondarie_non_mostra_nulla(tmp_path: Path) -> None:
    pub, site_dir = _pub(tmp_path)
    item = mk_item("a")
    item.importance = 5
    feed = mk_feed_on(datetime.now(UTC), [item])
    pub.publish_day(feed, templates_dir=Path("templates"), site_dir=site_dir)

    y, m, d = feed.generated_at_local.strftime("%Y-%m-%d").split("-")
    day_dir = site_dir / "archivio" / y / m / d
    article = next(p / "index.html" for p in day_dir.iterdir() if p.is_dir() and p.name != "hub")
    assert "Anche su" not in article.read_text(encoding="utf-8")
