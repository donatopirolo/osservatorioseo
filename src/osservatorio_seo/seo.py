"""SEO URL / path helpers."""

from __future__ import annotations

from osservatorio_seo.models import Item

SITE_URL = "https://www.osservatorioseo.com"


def year_path(year: int) -> str:
    return f"/archivio/{year:04d}/"


def month_path(year: int, month: int) -> str:
    return f"/archivio/{year:04d}/{month:02d}/"


def day_path(year: int, month: int, day: int) -> str:
    return f"/archivio/{year:04d}/{month:02d}/{day:02d}/"


def article_path(item: Item, date_str: str, slug: str) -> str:
    """``date_str`` is ``YYYY-MM-DD`` (the publish day of the feed, not the item)."""
    y, m, d = date_str.split("-")
    return f"/archivio/{y}/{m}/{d}/{slug}/"


def category_path(category: str) -> str:
    return f"/categoria/{category.replace('_', '-')}/"


def tag_path(tag: str) -> str:
    return f"/tag/{tag.replace('_', '-')}/"


def canonical(path: str) -> str:
    """Build full canonical URL from a site-relative path."""
    if path.startswith("/"):
        return SITE_URL + path
    return SITE_URL + "/" + path


def is_indexable(item: Item) -> bool:
    """True se l'item ha (o avra') una pagina articolo dedicata e indicizzabile.

    Unico criterio oggi: ``importance >= 4`` (D1 — tutti gli importance 4 e 5
    restano indicizzabili, nessuna soglia aggiuntiva). Centralizzato qui
    perche' prima era ripetuto identico in una decina di punti di
    publisher.py (sitemap, news sitemap, hub, feed.xml, top-settimana).
    """
    return item.importance >= 4
