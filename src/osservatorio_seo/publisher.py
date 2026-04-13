"""Publisher: scrive feed.json, archivi, e genera HTML SSG verso site/."""

from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from osservatorio_seo.models import Feed, Item, Pillar, Source
from osservatorio_seo.ranker import Ranker
from osservatorio_seo.renderer import HtmlRenderer
from osservatorio_seo.seo import (
    canonical,
)
from osservatorio_seo.seo import (
    category_path as make_category_path,
)
from osservatorio_seo.slug import make_unique_slug

if TYPE_CHECKING:
    from osservatorio_seo.config import DocWatcherPage


# ============================================================================
# Module-level helpers per SSG rendering
# ============================================================================

_CATEGORY_LABELS: dict[str, str] = {
    "google_updates": "Google Updates",
    "google_docs_change": "Google Docs Change ⚠️",
    "ai_models": "AI Models",
    "ai_overviews_llm_seo": "AI Overviews & LLM SEO",
    "technical_seo": "Technical SEO",
    "content_eeat": "Content & E-E-A-T",
    "tools_platforms": "Tools & Platforms",
    "industry_news": "Industry News",
}

_CATEGORY_ICONS: dict[str, str] = {
    "google_updates": "history",
    "google_docs_change": "warning",
    "ai_models": "smart_toy",
    "ai_overviews_llm_seo": "auto_awesome",
    "technical_seo": "build",
    "content_eeat": "article",
    "tools_platforms": "settings",
    "industry_news": "public",
}

_MONTH_LABELS: dict[int, str] = {
    1: "Gennaio",
    2: "Febbraio",
    3: "Marzo",
    4: "Aprile",
    5: "Maggio",
    6: "Giugno",
    7: "Luglio",
    8: "Agosto",
    9: "Settembre",
    10: "Ottobre",
    11: "Novembre",
    12: "Dicembre",
}

_TYPE_LABELS: dict[str, str] = {
    "official": "UFFICIALE",
    "media": "MEDIA",
    "independent": "INDIPENDENTE",
    "tool_vendor": "TOOL VENDOR",
    "social": "SOCIAL",
}


def _stars(importance: int) -> str:
    return "★" * importance + "☆" * (5 - importance)


def _short_id(item: Item) -> str:
    src = item.raw_hash or item.id or ""
    m = re.sub(r"[^a-zA-Z0-9]", "", src)
    return (m[-4:] or "0000").upper()


def _build_search_blob(item: Item) -> str:
    parts = [
        item.title_it or "",
        item.title_original or "",
        item.summary_it or "",
        " ".join(item.tags or []),
        item.source.name if item.source else "",
        item.source.id if item.source else "",
        item.category or "",
        item.url or "",
    ]
    blob = " ".join(parts)
    return re.sub(r"[_\-/]+", " ", blob).lower()


def _relative_date(published: datetime) -> str:
    now = datetime.now(UTC)
    diff = now - published
    secs = diff.total_seconds()
    if secs < 60:
        return "adesso"
    if secs < 3600:
        return f"{int(secs // 60)} min fa"
    if secs < 86400:
        return f"{int(secs // 3600)} h fa"
    days = int(secs // 86400)
    if days < 2:
        return "ieri"
    if days < 7:
        return f"{days} giorni fa"
    return published.strftime("%-d %b %Y")


def _absolute_date(published: datetime) -> str:
    return published.strftime("%A %-d %B %Y, %H:%M")


def _safe_hostname(url: str) -> str:
    try:
        return urlparse(url).hostname or url
    except Exception:
        return url


# ============================================================================
# Publisher
# ============================================================================


class Publisher:
    def __init__(
        self,
        data_dir: Path,
        archive_dir: Path,
        site_data_dir: Path | None = None,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._archive_dir = Path(archive_dir)
        self._site_data_dir = Path(site_data_dir) if site_data_dir else None

    def publish(self, feed: Feed) -> Path:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._archive_dir.mkdir(parents=True, exist_ok=True)

        feed_json = feed.model_dump_json(indent=2)
        feed_file = self._data_dir / "feed.json"
        feed_file.write_text(feed_json, encoding="utf-8")

        date_str = feed.generated_at_local.strftime("%Y-%m-%d")
        archive_file = self._archive_dir / f"{date_str}.json"
        archive_file.write_text(feed_json, encoding="utf-8")

        # Indice archivio: elenco ordinato di tutte le date disponibili
        archive_index = self._build_archive_index()
        archive_index_file = self._archive_dir / "index.json"
        archive_index_file.write_text(json.dumps(archive_index, indent=2), encoding="utf-8")

        if self._site_data_dir:
            self._site_data_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(feed_file, self._site_data_dir / "feed.json")

            # Copia l'intera dir archive nel site/ per servirla da Cloudflare Pages
            site_archive_dir = self._site_data_dir / "archive"
            site_archive_dir.mkdir(parents=True, exist_ok=True)
            for src in self._archive_dir.glob("*.json"):
                shutil.copy2(src, site_archive_dir / src.name)

        return feed_file

    def _build_archive_index(self) -> list[dict[str, str]]:
        """Ritorna la lista di tutte le date archivio disponibili, ordine desc."""
        entries: list[dict[str, str]] = []
        for path in self._archive_dir.glob("*.json"):
            if path.stem == "index":
                continue
            entries.append({"date": path.stem, "file": path.name})
        entries.sort(key=lambda e: e["date"], reverse=True)
        return entries

    def publish_config_snapshot(
        self,
        sources: list[Source],
        doc_pages: list[DocWatcherPage],
    ) -> Path:
        """Scrive uno snapshot leggibile del config (fonti + doc watcher pages)."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        snapshot = {
            "sources": [
                {
                    "id": s.id,
                    "name": s.name,
                    "type": s.type,
                    "authority": s.authority,
                    "fetcher": s.fetcher,
                    "url": s.feed_url or s.target_url or "",
                    "category_hint": s.category_hint,
                    "enabled": s.enabled,
                }
                for s in sources
            ],
            "doc_watcher_pages": [
                {
                    "id": p.id,
                    "name": p.name,
                    "url": p.url,
                    "type": p.type,
                    "importance": p.importance,
                    "category": p.category,
                }
                for p in doc_pages
            ],
        }
        target = self._data_dir / "config_snapshot.json"
        target.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        if self._site_data_dir:
            self._site_data_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, self._site_data_dir / "config_snapshot.json")
        return target

    # ========================================================================
    # SSG entrypoint + helpers
    # ========================================================================

    def publish_ssg(
        self,
        feed: Feed,
        sources: list[Source],
        doc_pages: list[DocWatcherPage],
        templates_dir: Path,
        site_dir: Path,
        *,
        allow_indexing: bool = False,
    ) -> None:
        """Genera tutti gli HTML SSG (homepage, snapshot, articoli, hub, docs,
        sitemap, feed.xml, robots.txt, top-settimana) dentro ``site_dir``.

        Articoli singoli vengono generati solo per ``item.importance >= 4``
        per mantenere il numero di file sotto i limiti free di Cloudflare.
        """
        renderer = HtmlRenderer(templates_dir)
        site_dir.mkdir(parents=True, exist_ok=True)

        day_iso = feed.generated_at_local.strftime("%Y-%m-%d")

        # Slugs univoci per gli item con importance>=4 (quelli che avranno una
        # single-article page).
        existing_slugs: set[str] = set()
        item_slugs: dict[str, str] = {}
        for item in feed.items:
            if item.importance < 4:
                continue
            slug = make_unique_slug(item.title_it, existing_slugs)
            existing_slugs.add(slug)
            item_slugs[item.id] = slug

        self._ssg_homepage(renderer, feed, site_dir, allow_indexing, item_slugs, day_iso)
        self._ssg_snapshot(renderer, feed, site_dir, allow_indexing, item_slugs, day_iso)
        self._ssg_day_hub(renderer, feed, site_dir, allow_indexing, item_slugs, day_iso)
        self._ssg_articles(renderer, feed, site_dir, allow_indexing, item_slugs, day_iso)
        self._ssg_archive_hubs(renderer, site_dir, allow_indexing)
        self._ssg_category_tag_hubs(renderer, feed, site_dir, allow_indexing, item_slugs, day_iso)
        self._ssg_docs_and_about(renderer, sources, doc_pages, site_dir, allow_indexing)
        self._ssg_dossiers(renderer, site_dir, allow_indexing)
        self._ssg_tracker(renderer, site_dir, allow_indexing)
        self._ssg_tracker_reports(renderer, site_dir, allow_indexing)
        self._ssg_seo_assets(renderer, feed, site_dir, allow_indexing, item_slugs, day_iso)
        self._ssg_top_week(renderer, feed, site_dir, allow_indexing, item_slugs, day_iso)

    # --- Homepage / snapshot ---

    def _build_card_ctx(
        self, item: Item, day_iso: str, item_slugs: dict[str, str]
    ) -> dict[str, Any]:
        y, m, d = day_iso.split("-")
        if item.importance >= 4 and item.id in item_slugs:
            article_url = f"/archivio/{y}/{m}/{d}/{item_slugs[item.id]}/"
            is_internal = True
        else:
            article_url = item.url
            is_internal = False
        return {
            "item": item.model_dump(mode="json"),
            "search_blob": _build_search_blob(item),
            "short_id": _short_id(item),
            "relative_date": _relative_date(item.published_at),
            "absolute_date": _absolute_date(item.published_at),
            "stars": _stars(item.importance),
            "tags": item.tags,
            "article_url": article_url,
            "is_internal_link": is_internal,
        }

    def _build_homepage_context(
        self,
        feed: Feed,
        allow_indexing: bool,
        item_slugs: dict[str, str],
        renderer: HtmlRenderer,
        day_iso: str,
    ) -> dict[str, Any]:
        items_by_id = {i.id: i for i in feed.items}
        y, m, d = day_iso.split("-")

        top10_cards: list[str] = []
        top10_itemlist: list[dict[str, str]] = []
        for idx, item_id in enumerate(feed.top10, start=1):
            item = items_by_id.get(item_id)
            if not item:
                continue
            card_ctx = self._build_card_ctx(item, day_iso, item_slugs)
            ctx = {**card_ctx, "order": idx}
            top10_cards.append(renderer.render_raw("partials/_card_top10.html.jinja", ctx))
            # ItemList schema: URL assoluta se articolo interno, altrimenti
            # puntiamo al snapshot del giorno (no URL esterne per non
            # inquinare il segnale di Google sui nostri URL)
            if card_ctx.get("is_internal_link"):
                item_url = canonical(card_ctx["article_url"])
            else:
                item_url = canonical(f"/archivio/{y}/{m}/{d}/")
            top10_itemlist.append({"url": item_url, "name": item.title_it})

        categories = []
        for cat_id, ids in feed.categories.items():
            cards = []
            for item_id in ids:
                item = items_by_id.get(item_id)
                if not item:
                    continue
                cards.append(
                    renderer.render_raw(
                        "partials/_card_category.html.jinja",
                        self._build_card_ctx(item, day_iso, item_slugs),
                    )
                )
            if cards:
                categories.append(
                    {
                        "label": _CATEGORY_LABELS.get(cat_id, cat_id),
                        "icon": _CATEGORY_ICONS.get(cat_id, "folder"),
                        "path": make_category_path(cat_id),
                        "cards": cards,
                    }
                )

        meta_line = (
            f"SYSTEM STATUS: OPTIMAL // LAST REFRESH "
            f"{feed.generated_at_local.strftime('%A %d %B %Y, %H:%M')} // "
            f"{feed.stats.sources_checked} SOURCES // {feed.stats.items_after_dedup} LOGS // "
            f"{feed.stats.doc_changes_detected} DOC CHANGES // €{feed.stats.ai_cost_eur:.3f} AI COST"
        )

        return {
            "page_title": "Osservatorio SEO — News giornaliere SEO e AI",
            "page_description": (
                "Hub giornaliero di notizie SEO e AI aggiornato alle 07:00. "
                "Fonti autorevoli, riassunti in italiano, rilevamento modifiche policy Google."
            ),
            "canonical_url": canonical("/"),
            "active_nav": "today",
            "noindex": not allow_indexing,
            "meta_line": meta_line,
            "top10_cards": top10_cards,
            "top10_itemlist": top10_itemlist,
            "top10_itemlist_name": "Top 10 del giorno — Osservatorio SEO",
            "categories": categories,
            "failed_sources": [fs.model_dump() for fs in feed.failed_sources],
            "tracker_teaser": self._build_tracker_teaser(),
            "breadcrumbs": [{"name": "Home", "url": canonical("/")}],
        }

    def _ssg_homepage(
        self,
        renderer: HtmlRenderer,
        feed: Feed,
        site_dir: Path,
        allow_indexing: bool,
        item_slugs: dict[str, str],
        day_iso: str,
    ) -> None:
        context = self._build_homepage_context(feed, allow_indexing, item_slugs, renderer, day_iso)
        html = renderer.render_homepage(context)
        (site_dir / "index.html").write_text(html, encoding="utf-8")

    def _ssg_snapshot(
        self,
        renderer: HtmlRenderer,
        feed: Feed,
        site_dir: Path,
        allow_indexing: bool,
        item_slugs: dict[str, str],
        day_iso: str,
    ) -> None:
        base = self._build_homepage_context(feed, allow_indexing, item_slugs, renderer, day_iso)
        y, m, d = day_iso.split("-")
        ctx = {
            **base,
            "page_title": f"Snapshot {day_iso} — Osservatorio SEO",
            "canonical_url": canonical(f"/archivio/{y}/{m}/{d}/"),
            "active_nav": "archive",
            "meta_line": f"SNAPSHOT {day_iso} // " + base["meta_line"],
            "top10_title": f"> TOP 10 DEL GIORNO {d} {m} {y}",
            "categories_title": f"> TUTTE PER CATEGORIA {d} {m} {y}",
            "breadcrumbs": [
                {"name": "Home", "url": canonical("/")},
                {"name": "Archivio", "url": canonical("/archivio/")},
                {"name": y, "url": canonical(f"/archivio/{y}/")},
                {"name": m, "url": canonical(f"/archivio/{y}/{m}/")},
                {"name": day_iso, "url": canonical(f"/archivio/{y}/{m}/{d}/")},
            ],
        }
        html = renderer.render_snapshot(ctx)
        target = site_dir / "archivio" / y / m / d
        target.mkdir(parents=True, exist_ok=True)
        (target / "index.html").write_text(html, encoding="utf-8")

    def _ssg_day_hub(
        self,
        renderer: HtmlRenderer,
        feed: Feed,
        site_dir: Path,
        allow_indexing: bool,
        item_slugs: dict[str, str],
        day_iso: str,
    ) -> None:
        y, m, d = day_iso.split("-")
        teaser_cards: list[str] = []
        for item in feed.items:
            if item.importance >= 4 and item.id in item_slugs:
                article_url = f"/archivio/{y}/{m}/{d}/{item_slugs[item.id]}/"
                is_internal = True
            else:
                article_url = item.url
                is_internal = False
            teaser_cards.append(
                renderer.render_raw(
                    "partials/_card_article_teaser.html.jinja",
                    {
                        "item": item.model_dump(mode="json"),
                        "short_id": _short_id(item),
                        "relative_date": _relative_date(item.published_at),
                        "stars": _stars(item.importance),
                        "article_url": article_url,
                        "is_internal_link": is_internal,
                    },
                )
            )

        day_label = feed.generated_at_local.strftime("%A %d %B %Y")
        ctx = {
            "page_title": f"Archivio {day_iso} — Osservatorio SEO",
            "page_description": f"Tutte le notizie SEO e AI del {day_label}",
            "canonical_url": canonical(f"/archivio/{y}/{m}/{d}/hub/"),
            "active_nav": "archive",
            "noindex": not allow_indexing,
            "meta_line": f"{len(feed.items)} ARTICOLI",
            "year": int(y),
            "year_path": f"/archivio/{y}/",
            "month_label": _MONTH_LABELS.get(int(m), m),
            "month_path": f"/archivio/{y}/{m}/",
            "day": int(d),
            "day_label": day_label,
            "teaser_cards": teaser_cards,
            "snapshot_path": f"/archivio/{y}/{m}/{d}/",
            "breadcrumbs": [
                {"name": "Home", "url": canonical("/")},
                {"name": "Archivio", "url": canonical("/archivio/")},
                {"name": y, "url": canonical(f"/archivio/{y}/")},
                {"name": _MONTH_LABELS.get(int(m), m), "url": canonical(f"/archivio/{y}/{m}/")},
                {"name": d, "url": canonical(f"/archivio/{y}/{m}/{d}/hub/")},
            ],
        }
        html = renderer.render_day_hub(ctx)
        target = site_dir / "archivio" / y / m / d / "hub"
        target.mkdir(parents=True, exist_ok=True)
        (target / "index.html").write_text(html, encoding="utf-8")

    def _ssg_articles(
        self,
        renderer: HtmlRenderer,
        feed: Feed,
        site_dir: Path,
        allow_indexing: bool,
        item_slugs: dict[str, str],
        day_iso: str,
    ) -> None:
        y, m, d = day_iso.split("-")
        for item in feed.items:
            if item.importance < 4 or item.id not in item_slugs:
                continue
            slug = item_slugs[item.id]
            article_url = canonical(f"/archivio/{y}/{m}/{d}/{slug}/")
            ctx = {
                "page_title": f"{item.title_it} — Osservatorio SEO",
                "page_description": item.summary_it[:155],
                "canonical_url": article_url,
                "active_nav": "archive",
                "noindex": not allow_indexing,
                "og_type": "article",
                "item": item.model_dump(mode="json"),
                "stars": _stars(item.importance),
                "absolute_date": _absolute_date(item.published_at),
                "day_label": feed.generated_at_local.strftime("%A %d %B %Y"),
                "day_path": f"/archivio/{y}/{m}/{d}/",
                "category_path": make_category_path(item.category),
                "category_label": _CATEGORY_LABELS.get(item.category, item.category),
                "published_iso": item.published_at.isoformat(),
                "article_url": article_url,
                "word_count": len((item.summary_it or "").split()),
                "breadcrumbs": [
                    {"name": "Home", "url": canonical("/"), "site_path": "/"},
                    {"name": "Archivio", "url": canonical("/archivio/"), "site_path": "/archivio/"},
                    {
                        "name": y,
                        "url": canonical(f"/archivio/{y}/"),
                        "site_path": f"/archivio/{y}/",
                    },
                    {
                        "name": m,
                        "url": canonical(f"/archivio/{y}/{m}/"),
                        "site_path": f"/archivio/{y}/{m}/",
                    },
                    {
                        "name": d,
                        "url": canonical(f"/archivio/{y}/{m}/{d}/"),
                        "site_path": f"/archivio/{y}/{m}/{d}/",
                    },
                    {"name": item.title_it, "url": article_url, "site_path": ""},
                ],
            }
            html = renderer.render_article(ctx)
            target = site_dir / "archivio" / y / m / d / slug
            target.mkdir(parents=True, exist_ok=True)
            (target / "index.html").write_text(html, encoding="utf-8")

    # --- Archive hubs + category/tag ---

    def _ssg_archive_hubs(
        self,
        renderer: HtmlRenderer,
        site_dir: Path,
        allow_indexing: bool,
    ) -> None:
        dated_files = sorted(
            (
                p
                for p in self._archive_dir.glob("*.json")
                if p.stem != "index" and re.match(r"^\d{4}-\d{2}-\d{2}$", p.stem)
            ),
            key=lambda p: p.stem,
            reverse=True,
        )
        if not dated_files:
            return

        by_year: dict[int, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
        for p in dated_files:
            try:
                y, m, d = p.stem.split("-")
                by_year[int(y)][int(m)].append(d)
            except ValueError:
                continue

        # Archive index
        years_ctx = [
            {
                "year": y,
                "path": f"/archivio/{y:04d}/",
                "count": sum(len(v) for v in months.values()),
            }
            for y, months in sorted(by_year.items(), reverse=True)
        ]
        idx_ctx = {
            "page_title": "Archivio — Osservatorio SEO",
            "page_description": "Tutte le giornate archiviate di Osservatorio SEO",
            "canonical_url": canonical("/archivio/"),
            "active_nav": "archive",
            "noindex": not allow_indexing,
            "meta_line": f"{len(dated_files)} LOG FILES",
            "years": years_ctx,
            "breadcrumbs": [
                {"name": "Home", "url": canonical("/")},
                {"name": "Archivio", "url": canonical("/archivio/")},
            ],
        }
        (site_dir / "archivio").mkdir(parents=True, exist_ok=True)
        (site_dir / "archivio" / "index.html").write_text(
            renderer.render_archive_index(idx_ctx), encoding="utf-8"
        )

        # Year hubs
        for year, months in by_year.items():
            y_ctx = {
                "page_title": f"Archivio {year} — Osservatorio SEO",
                "page_description": f"Archivio di tutte le notizie del {year}",
                "canonical_url": canonical(f"/archivio/{year:04d}/"),
                "active_nav": "archive",
                "noindex": not allow_indexing,
                "year": year,
                "months": [
                    {
                        "label": _MONTH_LABELS[month],
                        "path": f"/archivio/{year:04d}/{month:02d}/",
                        "count": len(days),
                    }
                    for month, days in sorted(months.items(), reverse=True)
                ],
                "breadcrumbs": [
                    {"name": "Home", "url": canonical("/")},
                    {"name": "Archivio", "url": canonical("/archivio/")},
                    {"name": str(year), "url": canonical(f"/archivio/{year:04d}/")},
                ],
            }
            y_dir = site_dir / "archivio" / f"{year:04d}"
            y_dir.mkdir(parents=True, exist_ok=True)
            (y_dir / "index.html").write_text(renderer.render_year_hub(y_ctx), encoding="utf-8")

            # Month hubs
            for month, days in months.items():
                m_ctx = {
                    "page_title": f"Archivio {_MONTH_LABELS[month]} {year} — Osservatorio SEO",
                    "page_description": f"Notizie SEO e AI di {_MONTH_LABELS[month]} {year}",
                    "canonical_url": canonical(f"/archivio/{year:04d}/{month:02d}/"),
                    "active_nav": "archive",
                    "noindex": not allow_indexing,
                    "year": year,
                    "year_path": f"/archivio/{year:04d}/",
                    "month_label": _MONTH_LABELS[month],
                    "days": [
                        {
                            "date": f"{year:04d}-{month:02d}-{day}",
                            "path": f"/archivio/{year:04d}/{month:02d}/{day}/",
                            "label": f"{int(day)} {_MONTH_LABELS[month]}",
                            "count": "?",
                        }
                        for day in sorted(days, reverse=True)
                    ],
                    "breadcrumbs": [
                        {"name": "Home", "url": canonical("/")},
                        {"name": "Archivio", "url": canonical("/archivio/")},
                        {"name": str(year), "url": canonical(f"/archivio/{year:04d}/")},
                        {
                            "name": _MONTH_LABELS[month],
                            "url": canonical(f"/archivio/{year:04d}/{month:02d}/"),
                        },
                    ],
                }
                m_dir = y_dir / f"{month:02d}"
                m_dir.mkdir(parents=True, exist_ok=True)
                (m_dir / "index.html").write_text(
                    renderer.render_month_hub(m_ctx), encoding="utf-8"
                )

    def _ssg_category_tag_hubs(
        self,
        renderer: HtmlRenderer,
        feed: Feed,
        site_dir: Path,
        allow_indexing: bool,
        item_slugs: dict[str, str],
        day_iso: str,
    ) -> None:
        y, m, d = day_iso.split("-")
        items_by_cat: dict[str, list[Item]] = defaultdict(list)
        items_by_tag: dict[str, list[Item]] = defaultdict(list)
        for item in feed.items:
            items_by_cat[item.category].append(item)
            for tag in item.tags:
                items_by_tag[tag].append(item)

        def build_teaser(item: Item) -> str:
            if item.importance >= 4 and item.id in item_slugs:
                article_url = f"/archivio/{y}/{m}/{d}/{item_slugs[item.id]}/"
                is_internal = True
            else:
                article_url = item.url
                is_internal = False
            return renderer.render_raw(
                "partials/_card_article_teaser.html.jinja",
                {
                    "item": item.model_dump(mode="json"),
                    "short_id": _short_id(item),
                    "relative_date": _relative_date(item.published_at),
                    "stars": _stars(item.importance),
                    "article_url": article_url,
                    "is_internal_link": is_internal,
                },
            )

        for cat_id, items in items_by_cat.items():
            cards = [build_teaser(i) for i in items]
            ctx = {
                "page_title": f"{_CATEGORY_LABELS.get(cat_id, cat_id)} — Osservatorio SEO",
                "page_description": f"Notizie SEO e AI della categoria {cat_id}",
                "canonical_url": canonical(make_category_path(cat_id)),
                "active_nav": "today",
                "noindex": not allow_indexing,
                "category_label": _CATEGORY_LABELS.get(cat_id, cat_id),
                "meta_line": f"{len(items)} ARTICOLI IN CATEGORIA",
                "teaser_cards": cards,
                "breadcrumbs": [
                    {"name": "Home", "url": canonical("/")},
                    {
                        "name": _CATEGORY_LABELS.get(cat_id, cat_id),
                        "url": canonical(make_category_path(cat_id)),
                    },
                ],
            }
            target = site_dir / "categoria" / cat_id.replace("_", "-")
            target.mkdir(parents=True, exist_ok=True)
            (target / "index.html").write_text(renderer.render_category_hub(ctx), encoding="utf-8")

        # NOTE: le pagine /tag/<slug>/ sono intenzionalmente disabilitate.
        # I tag al momento non hanno una strategia SEO dedicata: la
        # generazione automatica produceva pagine thin-content duplicate
        # dei category hub e inquinava la sitemap. I tag restano come
        # metadata sugli item (card + article header) per raccogliere dati,
        # e nei template sono rese come <span> non cliccabili. Quando
        # avremo un vocabolario controllato (vedi tags.py) e abbastanza
        # data per costruire hub significativi, la generazione tag può
        # essere riattivata qui. `items_by_tag` resta calcolato sopra
        # per eventuale debug / stat, ma non è più usato per rendering.
        _ = items_by_tag  # silenzia linter, conservato per raccolta dati futura

    # --- Docs / About / SEO assets ---

    def _ssg_docs_and_about(
        self,
        renderer: HtmlRenderer,
        sources: list[Source],
        doc_pages: list[DocWatcherPage],
        site_dir: Path,
        allow_indexing: bool,
    ) -> None:
        enriched = []
        for s in sources:
            url = s.feed_url or s.target_url or ""
            enriched.append(
                {
                    "id": s.id,
                    "name": s.name,
                    "type": s.type,
                    "authority": s.authority,
                    "fetcher": s.fetcher,
                    "url": url,
                    "hostname": _safe_hostname(url),
                }
            )
        by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for s in sorted(enriched, key=lambda x: -x["authority"]):
            by_type[_TYPE_LABELS.get(s["type"], s["type"].upper())].append(s)

        docs_ctx = {
            "page_title": "Docs — Osservatorio SEO",
            "page_description": "Come funziona Osservatorio SEO: fonti, pipeline, stack.",
            "canonical_url": canonical("/docs/"),
            "active_nav": "docs",
            "noindex": not allow_indexing,
            "sources": enriched,
            "sources_by_type": dict(by_type),
            "doc_watcher_pages": [
                {
                    "id": p.id,
                    "name": p.name,
                    "url": p.url,
                    "type": p.type,
                    "importance": p.importance,
                    "hostname": _safe_hostname(p.url),
                }
                for p in sorted(doc_pages, key=lambda p: -p.importance)
            ],
            "breadcrumbs": [
                {"name": "Home", "url": canonical("/")},
                {"name": "Docs", "url": canonical("/docs/")},
            ],
        }
        (site_dir / "docs").mkdir(parents=True, exist_ok=True)
        (site_dir / "docs" / "index.html").write_text(
            renderer.render_docs(docs_ctx), encoding="utf-8"
        )

        about_ctx = {
            "page_title": "Chi siamo — Osservatorio SEO",
            "page_description": "Chi c'è dietro Osservatorio SEO",
            "canonical_url": canonical("/about/"),
            "active_nav": "",
            "noindex": not allow_indexing,
            "source_count": len(sources),
            "breadcrumbs": [
                {"name": "Home", "url": canonical("/")},
                {"name": "Chi siamo", "url": canonical("/about/")},
            ],
        }
        (site_dir / "about").mkdir(parents=True, exist_ok=True)
        (site_dir / "about" / "index.html").write_text(
            renderer.render_about(about_ctx), encoding="utf-8"
        )

    # --- Dossier pillar pages ---

    def _load_pillars(self) -> list[Pillar]:
        """Carica tutti i Pillar da ``data/pillars/*.json``."""
        pillars_dir = self._data_dir / "pillars"
        if not pillars_dir.exists():
            return []
        pillars: list[Pillar] = []
        for path in sorted(pillars_dir.glob("*.json")):
            try:
                pillar = Pillar.model_validate(json.loads(path.read_text(encoding="utf-8")))
                pillars.append(pillar)
            except Exception:  # noqa: BLE001
                continue
        return pillars

    def _build_item_index(self) -> dict[str, dict[str, Any]]:
        """Scansione una tantum di tutti gli archive per id → metadata dell'item.

        Ritorna mapping ``item.id → {date, title, source, importance, slug,
        site_path}`` per risolvere i ``Pillar.item_refs`` nel template.
        """
        idx: dict[str, dict[str, Any]] = {}
        for arc in self._archive_dir.glob("*.json"):
            if arc.stem == "index":
                continue
            try:
                feed = Feed.model_validate(json.loads(arc.read_text(encoding="utf-8")))
            except Exception:  # noqa: BLE001
                continue
            day = arc.stem  # YYYY-MM-DD
            y, m, d = day.split("-")
            existing_slugs: set[str] = set()
            for item in feed.items:
                if item.importance < 4:
                    continue
                slug = make_unique_slug(item.title_it, existing_slugs)
                existing_slugs.add(slug)
                site_path = f"/archivio/{y}/{m}/{d}/{slug}/"
                idx[item.id] = {
                    "date": day,
                    "title": item.title_it,
                    "source": item.source.name,
                    "importance": item.importance,
                    "stars": _stars(item.importance),
                    "site_path": site_path,
                }
        return idx

    def _ssg_dossiers(
        self,
        renderer: HtmlRenderer,
        site_dir: Path,
        allow_indexing: bool,
    ) -> None:
        pillars = self._load_pillars()
        if not pillars:
            return
        item_idx = self._build_item_index()

        # Index page /dossier/
        index_entries = []
        for p in pillars:
            word_count = len(
                (p.intro_long + " " + p.context_section + " " + p.timeline_narrative).split()
            )
            index_entries.append(
                {
                    "tag": p.tag,
                    "slug": p.slug,
                    "title_it": p.title_it,
                    "subtitle_it": p.subtitle_it,
                    "refs_count": len(p.item_refs),
                    "updated_label": p.generated_at.strftime("%d %B %Y"),
                    "word_count": word_count,
                }
            )
        index_target = site_dir / "dossier"
        index_target.mkdir(parents=True, exist_ok=True)
        index_ctx = {
            "page_title": "Dossier SEO — Osservatorio SEO",
            "page_description": (
                "Approfondimenti editoriali su core update, E-E-A-T, Googlebot e "
                "altri temi SEO critici. Sintesi analitiche con articoli di riferimento, "
                "takeaways operativi e prospettive future."
            ),
            "canonical_url": canonical("/dossier/"),
            "active_nav": "dossier",
            "noindex": not allow_indexing,
            "pillars": index_entries,
            "breadcrumbs": [
                {"name": "Home", "url": canonical("/")},
                {"name": "Dossier", "url": canonical("/dossier/")},
            ],
        }
        (index_target / "index.html").write_text(
            renderer.render_dossier_index(index_ctx), encoding="utf-8"
        )

        for pillar in pillars:
            slug_dir = pillar.slug
            target = site_dir / "dossier" / slug_dir
            target.mkdir(parents=True, exist_ok=True)

            related: list[dict[str, Any]] = []
            for iid in pillar.item_refs:
                meta = item_idx.get(iid)
                if meta is None:
                    continue
                related.append(meta)
            # Ordine cronologico discendente (più recenti prima) per UX
            related.sort(key=lambda r: r["date"], reverse=True)

            updated_iso = pillar.generated_at.isoformat()
            updated_label = pillar.generated_at.strftime("%d %B %Y")
            article_url = canonical(f"/dossier/{slug_dir}/")

            ctx = {
                "page_title": f"{pillar.title_it} — Dossier Osservatorio SEO",
                "page_description": pillar.subtitle_it,
                "canonical_url": article_url,
                "active_nav": "dossier",
                "noindex": not allow_indexing,
                "og_type": "article",
                "pillar": pillar.model_dump(mode="json"),
                "related_articles": related,
                "updated_iso": updated_iso,
                "updated_label": updated_label,
                "article_url": article_url,
                "breadcrumbs": [
                    {"name": "Home", "url": canonical("/"), "site_path": "/"},
                    {
                        "name": "Dossier",
                        "url": canonical("/dossier/"),
                        "site_path": "/dossier/",
                    },
                    {
                        "name": pillar.title_it,
                        "url": article_url,
                        "site_path": "",
                    },
                ],
            }
            html = renderer.render_dossier(ctx)
            (target / "index.html").write_text(html, encoding="utf-8")

    # --- Tracker dashboard ---

    def _ssg_tracker(
        self,
        renderer: HtmlRenderer,
        site_dir: Path,
        allow_indexing: bool,
    ) -> None:
        """Render the /tracker/ dashboard using the latest v2 snapshot."""
        from osservatorio_seo.tracker.models import TrackerSnapshot

        snapshots_dir = self._data_dir / "tracker" / "snapshots"
        if not snapshots_dir.exists():
            return

        latest = self._find_latest_snapshot(snapshots_dir)
        if latest is None:
            return

        snapshot = TrackerSnapshot.model_validate_json(latest.read_text(encoding="utf-8"))

        if snapshot.schema_version != "2.0":
            return

        updated_label = snapshot.generated_at.strftime("%d %B %Y")
        nxt = snapshot.generated_at + timedelta(days=7)
        next_update = nxt.strftime("%d %B %Y")

        tracker_json = snapshot.model_dump_json()

        ctx = {
            "page_title": "Tracker — Stato della ricerca — Osservatorio SEO",
            "page_description": (
                "Dashboard settimanale: ranking dei top 10 siti in Italia e nel mondo, "
                "piattaforme AI, bot vs umani, crawling AI per settore. Dati Cloudflare Radar."
            ),
            "canonical_url": canonical("/tracker/"),
            "active_nav": "tracker",
            "noindex": not allow_indexing,
            "og_type": "website",
            "page_headline": (f"Stato della ricerca — Settimana {snapshot.week}, {snapshot.year}"),
            "updated_label": updated_label,
            "updated_iso": snapshot.generated_at.isoformat(),
            "next_update_label": next_update,
            "tracker_json": tracker_json,
            "breadcrumbs": [
                {"name": "Home", "url": canonical("/")},
                {"name": "Tracker", "url": canonical("/tracker/")},
            ],
        }

        target_dir = site_dir / "tracker"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "index.html").write_text(renderer.render_tracker(ctx), encoding="utf-8")

    def _ssg_tracker_reports(
        self,
        renderer: HtmlRenderer,
        site_dir: Path,
        allow_indexing: bool,
    ) -> None:
        """Render monthly tracker reports from data/tracker/reports/*.json."""
        reports_dir = self._data_dir / "tracker" / "reports"
        if not reports_dir.exists():
            return

        from osservatorio_seo.tracker.models import TrackerMonthlyReport

        for report_path in sorted(reports_dir.glob("????-??.json")):
            report = TrackerMonthlyReport.model_validate_json(
                report_path.read_text(encoding="utf-8")
            )
            year_str, month_str = report_path.stem.split("-")
            month_label = datetime(report.year, report.month, 1).strftime("%B %Y")
            canonical_url = canonical(f"/tracker/report/{year_str}-{month_str}/")

            ctx = {
                "page_title": f"{report.title_it} — Tracker — Osservatorio SEO",
                "page_description": report.subtitle_it,
                "canonical_url": canonical_url,
                "active_nav": "tracker",
                "noindex": not allow_indexing,
                "og_type": "article",
                "report": report.model_dump(mode="json"),
                "article_url": canonical_url,
                "updated_iso": report.generated_at.isoformat(),
                "month_label": month_label,
                "breadcrumbs": [
                    {"name": "Home", "url": canonical("/"), "site_path": "/"},
                    {"name": "Tracker", "url": canonical("/tracker/"), "site_path": "/tracker/"},
                    {"name": month_label, "url": canonical_url, "site_path": ""},
                ],
            }

            target_dir = site_dir / "tracker" / "report" / f"{year_str}-{month_str}"
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / "index.html").write_text(
                renderer.render_tracker_report(ctx), encoding="utf-8"
            )

    @staticmethod
    def _find_latest_snapshot(snapshots_dir: Path) -> Path | None:
        candidates = sorted(snapshots_dir.glob("*-W*.json"))
        return candidates[-1] if candidates else None

    def _build_tracker_teaser(self) -> dict[str, Any] | None:
        """Produce a small dict for homepage tracker teaser, or None."""
        from osservatorio_seo.tracker.models import TrackerSnapshot

        snapshots_dir = self._data_dir / "tracker" / "snapshots"
        if not snapshots_dir.exists():
            return None
        latest = self._find_latest_snapshot(snapshots_dir)
        if latest is None:
            return None
        try:
            snapshot = TrackerSnapshot.model_validate_json(latest.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None

        if snapshot.schema_version != "2.0":
            return None

        chatgpt_rank = None
        for entry in snapshot.top10_it:
            if entry.domain == "chatgpt.com":
                chatgpt_rank = entry.rank
                break

        bot_pct = None
        if snapshot.bot_human_it.points:
            bot_pct = snapshot.bot_human_it.points[-1].bot_pct

        return {
            "chatgpt_rank_it": chatgpt_rank,
            "bot_pct_it": bot_pct,
            "week": snapshot.week,
            "year": snapshot.year,
        }

    def _ssg_seo_assets(
        self,
        renderer: HtmlRenderer,
        feed: Feed,
        site_dir: Path,
        allow_indexing: bool,
        item_slugs: dict[str, str],
        day_iso: str,
    ) -> None:
        y, m, d = day_iso.split("-")
        today = day_iso

        urls: list[dict[str, Any]] = [
            {"loc": canonical("/"), "lastmod": today, "priority": "1.0", "changefreq": "daily"},
            {
                "loc": canonical("/top-settimana/"),
                "lastmod": today,
                "priority": "0.9",
                "changefreq": "daily",
            },
            {
                "loc": canonical("/archivio/"),
                "lastmod": today,
                "priority": "0.7",
                "changefreq": "daily",
            },
            {
                "loc": canonical("/docs/"),
                "lastmod": today,
                "priority": "0.3",
                "changefreq": "monthly",
            },
            {
                "loc": canonical("/about/"),
                "lastmod": today,
                "priority": "0.3",
                "changefreq": "monthly",
            },
        ]

        # Tracker: add if snapshots exist
        tracker_snapshots = self._data_dir / "tracker" / "snapshots"
        if tracker_snapshots.exists() and self._find_latest_snapshot(tracker_snapshots):
            urls.append(
                {
                    "loc": canonical("/tracker/"),
                    "lastmod": today,
                    "priority": "0.9",
                    "changefreq": "weekly",
                }
            )

        categories_seen = {i.category for i in feed.items}
        for cat in categories_seen:
            urls.append(
                {"loc": canonical(make_category_path(cat)), "lastmod": today, "priority": "0.6"}
            )
        # Tag pages intentionally NOT in sitemap — no SEO strategy on tags yet.

        urls.append(
            {"loc": canonical(f"/archivio/{y}/{m}/{d}/"), "lastmod": today, "priority": "0.8"}
        )
        for item in feed.items:
            if item.importance < 4 or item.id not in item_slugs:
                continue
            slug = item_slugs[item.id]
            urls.append(
                {
                    "loc": canonical(f"/archivio/{y}/{m}/{d}/{slug}/"),
                    "lastmod": today,
                    "priority": "0.7",
                }
            )

        # Dossier pillar pages: priorità alta perché sono contenuto evergreen
        for pillar in self._load_pillars():
            urls.append(
                {
                    "loc": canonical(f"/dossier/{pillar.slug}/"),
                    "lastmod": pillar.generated_at.strftime("%Y-%m-%d"),
                    "priority": "0.9",
                    "changefreq": "weekly",
                }
            )

        (site_dir / "sitemap.xml").write_text(
            renderer.render_sitemap({"urls": urls}), encoding="utf-8"
        )

        # sitemap-news.xml: solo articoli con pagina SSG dedicata E pubblicati
        # nelle ultime 48h (requisito Google News)
        now = datetime.now(UTC)
        news_cutoff = now - timedelta(hours=48)
        news_entries: list[dict[str, str]] = []
        for item in feed.items:
            if item.importance < 4 or item.id not in item_slugs:
                continue
            if item.published_at < news_cutoff:
                continue
            slug = item_slugs[item.id]
            news_entries.append(
                {
                    "loc": canonical(f"/archivio/{y}/{m}/{d}/{slug}/"),
                    "publication_date": item.published_at.isoformat(),
                    "title": item.title_it,
                }
            )
        (site_dir / "sitemap-news.xml").write_text(
            renderer.render_sitemap_news({"entries": news_entries}), encoding="utf-8"
        )

        entries = [
            {
                "title": item.title_it,
                "url": canonical(
                    f"/archivio/{y}/{m}/{d}/{item_slugs.get(item.id, 'untitled')}/"
                    if item.importance >= 4 and item.id in item_slugs
                    else item.url
                ),
                "updated": item.fetched_at.isoformat(),
                "published": item.published_at.isoformat(),
                "summary": item.summary_it,
                "tags": list(item.tags or []),
            }
            for item in feed.items[:50]
        ]
        (site_dir / "feed.xml").write_text(
            renderer.render_feed_xml(
                {
                    "site_url": "https://osservatorioseo.pages.dev",
                    "updated": feed.generated_at.isoformat(),
                    "entries": entries,
                }
            ),
            encoding="utf-8",
        )

        (site_dir / "robots.txt").write_text(
            renderer.render_robots_txt(
                {
                    "allow_indexing": allow_indexing,
                    "site_url": "https://osservatorioseo.pages.dev",
                }
            ),
            encoding="utf-8",
        )

    # --- Top Week (rolling 7-day top 10) ---

    def _ssg_top_week(
        self,
        renderer: HtmlRenderer,
        current_feed: Feed,
        site_dir: Path,
        allow_indexing: bool,
        item_slugs: dict[str, str],
        day_iso: str,
    ) -> None:
        seven_days_ago = datetime.now(UTC) - timedelta(days=7)
        combined_items: list[Item] = []
        seen_urls: set[str] = set()

        # Items del feed corrente prima (priorità su dedup)
        for item in current_feed.items:
            if item.url not in seen_urls:
                combined_items.append(item)
                seen_urls.add(item.url)

        # Items da archivio (esclude il giorno corrente)
        archive_files = sorted(
            (
                p
                for p in self._archive_dir.glob("*.json")
                if p.stem != "index" and p.stem != day_iso
            ),
            reverse=True,
        )
        for path in archive_files[:7]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                feed = Feed.model_validate(data)
            except Exception:
                continue
            if feed.generated_at < seven_days_ago:
                continue
            for item in feed.items:
                if item.url in seen_urls:
                    continue
                combined_items.append(item)
                seen_urls.add(item.url)

        if not combined_items:
            return

        ranker = Ranker()
        ranked = ranker.rank(combined_items)
        items_by_id = {i.id: i for i in combined_items}

        top10_cards: list[str] = []
        top10_itemlist: list[dict[str, str]] = []
        for idx, item_id in enumerate(ranked.top10, start=1):
            item = items_by_id.get(item_id)
            if not item:
                continue

            # Link articolo: se importance>=4 AND è nel feed corrente, punta alla
            # pagina SSG di oggi; altrimenti URL originale
            is_today = any(i.id == item.id for i in current_feed.items)
            if is_today and item.importance >= 4 and item.id in item_slugs:
                y, m, d = day_iso.split("-")
                article_url = f"/archivio/{y}/{m}/{d}/{item_slugs[item.id]}/"
                is_internal = True
            else:
                article_url = item.url
                is_internal = False

            ctx = {
                "item": item.model_dump(mode="json"),
                "search_blob": _build_search_blob(item),
                "short_id": _short_id(item),
                "relative_date": _relative_date(item.published_at),
                "absolute_date": _absolute_date(item.published_at),
                "stars": _stars(item.importance),
                "tags": item.tags,
                "article_url": article_url,
                "is_internal_link": is_internal,
                "order": idx,
            }
            top10_cards.append(renderer.render_raw("partials/_card_top10.html.jinja", ctx))

            # ItemList schema: solo URL interne (evita di "annunciare" URL
            # esterne come se fossero nostre)
            if is_internal:
                top10_itemlist.append({"url": canonical(article_url), "name": item.title_it})
            else:
                top10_itemlist.append({"url": canonical("/top-settimana/"), "name": item.title_it})

        meta_line = (
            f"SYSTEM STATUS: OPTIMAL // ROLLING 7D // "
            f"{len(combined_items)} ARTICOLI ANALIZZATI // TOP 10"
        )

        ctx = {
            "page_title": "Top della Settimana — Osservatorio SEO",
            "page_description": (
                "Le 10 notizie SEO e AI più rilevanti degli ultimi 7 giorni, "
                "aggiornate ogni mattina."
            ),
            "canonical_url": canonical("/top-settimana/"),
            "active_nav": "top-week",
            "noindex": not allow_indexing,
            "meta_line": meta_line,
            "top10_cards": top10_cards,
            "top10_itemlist": top10_itemlist,
            "top10_itemlist_name": "Top 10 della settimana — Osservatorio SEO",
            "breadcrumbs": [
                {"name": "Home", "url": canonical("/")},
                {"name": "Top Settimana", "url": canonical("/top-settimana/")},
            ],
        }
        html = renderer.render_top_week(ctx)
        target = site_dir / "top-settimana"
        target.mkdir(parents=True, exist_ok=True)
        (target / "index.html").write_text(html, encoding="utf-8")
