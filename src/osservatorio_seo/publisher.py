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
from zoneinfo import ZoneInfo

from osservatorio_seo.models import Feed, Item, Pillar, Source
from osservatorio_seo.ranker import Ranker
from osservatorio_seo.renderer import HtmlRenderer
from osservatorio_seo.seo import (
    SITE_URL,
    canonical,
    is_indexable,
)
from osservatorio_seo.seo import (
    category_path as make_category_path,
)
from osservatorio_seo.slug import make_unique_slug
from osservatorio_seo.sources import is_google_source

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

# D7: title dedicati per singole hub di categoria, ottimizzati per query
# specifiche. Le categorie non elencate qui ricadono sul pattern generico
# "<Label> — Osservatorio SEO".
_CATEGORY_PAGE_TITLES: dict[str, str] = {
    "google_updates": "Aggiornamenti Google Search: core update, spam update e novità",
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

_DAY_LABELS: dict[int, str] = {
    0: "Lunedì",
    1: "Martedì",
    2: "Mercoledì",
    3: "Giovedì",
    4: "Venerdì",
    5: "Sabato",
    6: "Domenica",
}

_ROME_TZ = ZoneInfo("Europe/Rome")

_TYPE_LABELS: dict[str, str] = {
    "official": "UFFICIALE",
    "media": "MEDIA",
    "independent": "INDIPENDENTE",
    "tool_vendor": "TOOL VENDOR",
    "social": "SOCIAL",
}


def format_date_it(dt: datetime, fmt: str) -> str:
    """strftime indipendente dalla locale di sistema, per formati in italiano.

    ``%A`` e ``%B`` (nome giorno/mese esteso) dipendono dalla locale del
    processo: sui runner di GitHub Actions non c'e' una locale it_IT
    installata, quindi strftime produce nomi in inglese ("Sunday", "April").
    Qui vengono sostituiti con ``_DAY_LABELS``/``_MONTH_LABELS`` prima di
    delegare il resto del formato (numerico, non locale-dipendente) a
    strftime.
    """
    fmt = fmt.replace("%A", _DAY_LABELS[dt.weekday()]).replace("%B", _MONTH_LABELS[dt.month])
    return dt.strftime(fmt)


def _meta_description(text: str, max_len: int = 155) -> str:
    """Taglia una descrizione a ``max_len`` caratteri sull'ultimo spazio.

    Un taglio secco a lunghezza fissa spezza le parole a meta' circa la
    meta' delle volte sui summary reali dell'archivio; qui si torna indietro
    fino all'ultimo spazio cosi' la descrizione finisce sempre a fine parola.
    """
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated.rstrip(" ,;:.") + "…"


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
    return published.astimezone(_ROME_TZ).strftime("%-d %b %Y")


def _absolute_date(published: datetime) -> str:
    return format_date_it(published.astimezone(_ROME_TZ), "%A %-d %B %Y, %H:%M")


def _resolve_article_link(
    item: Item,
    item_idx: dict[str, dict[str, Any]],
    item_slugs: dict[str, str],
    day_iso: str,
) -> tuple[str, bool]:
    """URL e flag "e' interna" per un item, indipendentemente da quale
    giorno dell'archivio provenga.

    Prima cerca in ``item_idx`` (da ``_build_item_index()``, copre tutto
    l'archivio): senza questo, un item pubblicato in un giorno diverso da
    quello corrente risultava sempre linkato all'URL esterno della fonte
    anche se aveva gia' una pagina propria. Ricade su ``item_slugs`` (solo
    item del giorno corrente) per i casi in cui l'archivio non contiene
    ancora il file di oggi (es. nei test che chiamano publish_ssg senza
    prima scrivere l'archivio).
    """
    meta = item_idx.get(item.id)
    if meta:
        return meta["site_path"], True
    if is_indexable(item) and item.id in item_slugs:
        y, m, d = day_iso.split("-")
        return f"/archivio/{y}/{m}/{d}/{item_slugs[item.id]}/", True
    return item.url, False


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

    def publish(self, feed: Feed) -> Feed:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._archive_dir.mkdir(parents=True, exist_ok=True)

        date_str = feed.generated_at_local.strftime("%Y-%m-%d")
        archive_file = self._archive_dir / f"{date_str}.json"
        merged_feed = self._preserve_doc_changes(feed, archive_file)

        feed_json = merged_feed.model_dump_json(indent=2)
        feed_file = self._data_dir / "feed.json"
        feed_file.write_text(feed_json, encoding="utf-8")

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

        return merged_feed

    def _preserve_doc_changes(self, feed: Feed, archive_file: Path) -> Feed:
        """Conserva i doc-change item gia' pubblicati nello stesso giorno.

        I doc-change item compaiono solo nel run che rileva la modifica. Senza
        questa logica un secondo run nello stesso giorno riscriverebbe l'archivio
        del giorno cancellando la notizia (lo state e' gia' "consumato", quindi
        la modifica non viene piu' rilevata). Qui i doc-change item presenti
        nell'archivio esistente ma assenti dal feed corrente vengono reiniettati.
        """
        if not archive_file.exists():
            return feed
        try:
            existing = Feed.model_validate_json(archive_file.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return feed

        current_ids = {i.id for i in feed.items}
        preserved = [i for i in existing.items if i.is_doc_change and i.id not in current_ids]
        if not preserved:
            return feed

        merged_items = [*feed.items, *preserved]
        merged_categories = {k: list(v) for k, v in feed.categories.items()}
        for item in preserved:
            ids = merged_categories.setdefault(item.category, [])
            if item.id not in ids:
                ids.append(item.id)
        return feed.model_copy(update={"items": merged_items, "categories": merged_categories})

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

        # URL gia' pubblicati (con pagina propria) in un giorno precedente:
        # non generare una seconda pagina per lo stesso URL (es. una fonte
        # ripubblica/aggiorna un articolo vecchio senza cambiarne l'URL).
        urls_published_before_today = {
            meta["url"] for meta in self._build_item_index().values() if meta["date"] < day_iso
        }

        # Slugs univoci per gli item con importance>=4 (quelli che avranno una
        # single-article page).
        existing_slugs: set[str] = set()
        item_slugs: dict[str, str] = {}
        for item in feed.items:
            if not is_indexable(item):
                continue
            if item.url in urls_published_before_today:
                continue
            slug = make_unique_slug(item.title_it, existing_slugs)
            existing_slugs.add(slug)
            item_slugs[item.id] = slug

        self._ssg_homepage(renderer, feed, site_dir, allow_indexing, item_slugs, day_iso)
        self._ssg_snapshot(renderer, feed, site_dir, allow_indexing, item_slugs, day_iso)
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
        if is_indexable(item) and item.id in item_slugs:
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
            f"{format_date_it(feed.generated_at_local, '%A %d %B %Y, %H:%M')} // "
            f"{feed.stats.sources_checked} SOURCES // {feed.stats.items_after_dedup} LOGS // "
            f"{feed.stats.doc_changes_detected} DOC CHANGES // €{feed.stats.ai_cost_eur:.3f} AI COST"
        )

        return {
            "page_title": "Notizie SEO di oggi: novità Google, AI e aggiornamenti",
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
        # Mesi minuscoli: in italiano vanno cosi' nel testo corrente, anche
        # dentro un <title>. _MONTH_LABELS li ha capitalizzati perche' servono
        # anche da soli nei breadcrumb, dove la maiuscola e' corretta.
        day_label_full = format_date_it(datetime(int(y), int(m), int(d)), "%-d %B %Y").lower()
        ctx = {
            **base,
            "page_title": f"Notizie SEO del {day_label_full} — Osservatorio SEO",
            "page_description": (
                f"Le notizie SEO e AI del {day_label_full}: "
                f"{feed.stats.items_after_dedup} "
                f"{'segnalazione' if feed.stats.items_after_dedup == 1 else 'segnalazioni'} "
                "da fonti autorevoli, "
                "riassunte in italiano nell'archivio di Osservatorio SEO."
            ),
            "canonical_url": canonical(f"/archivio/{y}/{m}/{d}/"),
            "active_nav": "archive",
            "meta_line": f"SNAPSHOT {day_iso} // " + base["meta_line"],
            "top10_title": f"> TOP 10 DEL GIORNO {d} {m} {y}",
            "categories_title": f"> TUTTE PER CATEGORIA {d} {m} {y}",
            "breadcrumbs": [
                {"name": "Home", "url": canonical("/")},
                {"name": "Archivio", "url": canonical("/archivio/")},
                {"name": y, "url": canonical(f"/archivio/{y}/")},
                {
                    "name": _MONTH_LABELS[int(m)],
                    "url": canonical(f"/archivio/{y}/{m}/"),
                },
                {"name": day_iso, "url": canonical(f"/archivio/{y}/{m}/{d}/")},
            ],
        }
        html = renderer.render_snapshot(ctx)
        target = site_dir / "archivio" / y / m / d
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

        # Mappa tag -> dossier: un tag cliccabile ha senso solo se porta a un
        # contenuto vero (il dossier che lo tratta), non a un hub generico
        # (i tag hub sono disattivati, vedi nota in _ssg_category_tag_hubs).
        tag_to_dossier = {p.tag: p.slug for p in self._load_pillars()}

        # Pool per la sezione "Correlati": altri item indicizzabili della
        # stessa categoria, in tutto l'archivio, piu' recenti prima.
        item_idx = self._build_item_index()
        related_by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for iid, meta in item_idx.items():
            related_by_category[meta["category"]].append({**meta, "id": iid})
        for cat_items in related_by_category.values():
            cat_items.sort(key=lambda meta: meta["date"], reverse=True)

        for item in feed.items:
            if not is_indexable(item) or item.id not in item_slugs:
                continue
            slug = item_slugs[item.id]
            article_url = canonical(f"/archivio/{y}/{m}/{d}/{slug}/")
            related = [
                {"title": meta["title"], "path": meta["site_path"]}
                for meta in related_by_category.get(item.category, [])
                if meta["id"] != item.id
            ][:5]
            ctx = {
                "page_title": f"{item.title_it} — Osservatorio SEO",
                "page_description": _meta_description(item.summary_it),
                "canonical_url": article_url,
                "active_nav": "archive",
                "tag_to_dossier": tag_to_dossier,
                "related_articles": related,
                "noindex": not allow_indexing or not is_indexable(item),
                "og_type": "article",
                "item": item.model_dump(mode="json"),
                "stars": _stars(item.importance),
                "absolute_date": _absolute_date(item.published_at),
                "day_label": format_date_it(feed.generated_at_local, "%A %d %B %Y"),
                "day_path": f"/archivio/{y}/{m}/{d}/",
                "category_path": make_category_path(item.category),
                "category_label": _CATEGORY_LABELS.get(item.category, item.category),
                # Data di pubblicazione SUL SITO (questo run), non della
                # fonte: e' quella corretta per NewsArticle.datePublished.
                "published_iso": feed.generated_at.isoformat(),
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
                        # Nome del mese, non "09": il breadcrumb e' testo per
                        # utenti e per la SERP, non un percorso di filesystem.
                        "name": _MONTH_LABELS[int(m)],
                        "url": canonical(f"/archivio/{y}/{m}/"),
                        "site_path": f"/archivio/{y}/{m}/",
                    },
                    {
                        "name": f"{int(d)} {_MONTH_LABELS[int(m)].lower()}",
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
        day_item_counts: dict[str, int] = {}
        for p in dated_files:
            try:
                y, m, d = p.stem.split("-")
                by_year[int(y)][int(m)].append(d)
            except ValueError:
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                day_item_counts[p.stem] = len(data.get("items", []))
            except Exception:  # noqa: BLE001
                day_item_counts[p.stem] = 0

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
                            "count": day_item_counts.get(f"{year:04d}-{month:02d}-{day}", 0),
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
        # Ultimi 30 giorni di archivio, non solo il feed di oggi: una hub
        # costruita sul solo giorno corrente sparisce (o resta vuota) per
        # qualunque categoria senza notizie proprio oggi, pur avendo storia
        # nell'archivio. Stesso pattern di dedup-per-URL di _ssg_top_week.
        cutoff = datetime.now(UTC) - timedelta(days=30)
        combined_items: list[Item] = []
        seen_urls: set[str] = set()
        # Giorno d'archivio di ogni item: serve come destinazione di ripiego
        # per le card degli item senza pagina propria (importance < 4). Senza,
        # il template le rende come <span> e restano testo non cliccabile.
        item_day: dict[str, str] = {}
        for item in feed.items:
            if item.url not in seen_urls:
                combined_items.append(item)
                seen_urls.add(item.url)
                item_day[item.id] = day_iso

        archive_files = sorted(
            (
                p
                for p in self._archive_dir.glob("*.json")
                if p.stem != "index" and p.stem != day_iso
            ),
            reverse=True,
        )
        for path in archive_files[:30]:
            try:
                past_feed = Feed.model_validate(json.loads(path.read_text(encoding="utf-8")))
            except Exception:  # noqa: BLE001
                continue
            if past_feed.generated_at < cutoff:
                continue
            for item in past_feed.items:
                if item.url in seen_urls:
                    continue
                combined_items.append(item)
                seen_urls.add(item.url)
                item_day[item.id] = path.stem

        combined_items.sort(key=lambda i: i.published_at, reverse=True)

        # Metadata (slug/site_path) degli item con pagina interna in QUALSIASI
        # giorno dell'archivio, non solo oggi: senza questo le card di un
        # item pubblicato ieri puntavano sempre all'URL esterno della fonte.
        item_idx = self._build_item_index()

        items_by_cat: dict[str, list[Item]] = defaultdict(list)
        items_by_tag: dict[str, list[Item]] = defaultdict(list)
        for item in combined_items:
            items_by_cat[item.category].append(item)
            for tag in item.tags:
                items_by_tag[tag].append(item)

        def build_teaser(item: Item) -> str:
            article_url, is_internal = _resolve_article_link(item, item_idx, item_slugs, day_iso)
            if not is_internal and item.id in item_day:
                # Nessuna pagina propria: si va allo snapshot del giorno in cui
                # la notizia e' comparsa. E' interno, pertinente, e da' un
                # percorso a chi arriva sulla hub di categoria (1.9-fix).
                dy, dm, dd = item_day[item.id].split("-")
                article_url = f"/archivio/{dy}/{dm}/{dd}/"
                is_internal = True
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

        # Tutte le categorie note, non solo quelle con notizie negli ultimi
        # 30 giorni: altrimenti una categoria senza notizie perde la pagina
        # (e sparisce da sitemap/navigazione) invece di mostrarla vuota.
        for cat_id, label in _CATEGORY_LABELS.items():
            items = items_by_cat.get(cat_id, [])
            cards = [build_teaser(i) for i in items]
            ctx = {
                "page_title": _CATEGORY_PAGE_TITLES.get(cat_id, f"{label} — Osservatorio SEO"),
                "page_description": f"Notizie SEO e AI della categoria {label}, ultimi 30 giorni.",
                "canonical_url": canonical(make_category_path(cat_id)),
                "active_nav": "today",
                "noindex": not allow_indexing,
                "category_label": label,
                "meta_line": f"{len(items)} ARTICOLI (ULTIMI 30 GIORNI)",
                "teaser_cards": cards,
                "breadcrumbs": [
                    {"name": "Home", "url": canonical("/")},
                    {"name": label, "url": canonical(make_category_path(cat_id))},
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

        Ritorna mapping ``item.id → {date, title, source, importance, category,
        slug, site_path, url}`` per risolvere i ``Pillar.item_refs`` nel
        template, per il dedup cross-day (D 1.4: non generare una seconda
        pagina per un URL gia' pubblicato in un giorno precedente) e per la
        sezione "Correlati" nella pagina articolo.
        """
        idx: dict[str, dict[str, Any]] = {}
        # Ordine cronologico: serve a "seen_urls" per sapere qual e' il PRIMO
        # giorno in cui un URL ha ricevuto una pagina (stessa regola di
        # publish_ssg: niente seconda pagina per un URL gia' pubblicato).
        archive_files = sorted(
            (p for p in self._archive_dir.glob("*.json") if p.stem != "index"),
            key=lambda p: p.stem,
        )
        seen_urls: set[str] = set()
        for arc in archive_files:
            try:
                feed = Feed.model_validate(json.loads(arc.read_text(encoding="utf-8")))
            except Exception:  # noqa: BLE001
                continue
            day = arc.stem  # YYYY-MM-DD
            y, m, d = day.split("-")
            existing_slugs: set[str] = set()
            for item in feed.items:
                if not is_indexable(item) or item.url in seen_urls:
                    continue
                slug = make_unique_slug(item.title_it, existing_slugs)
                existing_slugs.add(slug)
                site_path = f"/archivio/{y}/{m}/{d}/{slug}/"
                idx[item.id] = {
                    "date": day,
                    "title": item.title_it,
                    "source": item.source.name,
                    "importance": item.importance,
                    "category": item.category,
                    "stars": _stars(item.importance),
                    "site_path": site_path,
                    "url": item.url,
                }
                seen_urls.add(item.url)
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
                    "updated_label": format_date_it(p.generated_at, "%d %B %Y"),
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
            updated_label = format_date_it(pillar.generated_at, "%d %B %Y")
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

        if snapshot.schema_version not in ("2.0", "3.0"):
            return

        updated_label = format_date_it(snapshot.generated_at, "%d %B %Y")
        nxt = snapshot.generated_at + timedelta(days=7)
        next_update = format_date_it(nxt, "%d %B %Y")

        tracker_json = snapshot.model_dump_json()

        ctx = {
            "page_title": "AI Tracker — Adozione e tendenze — Osservatorio SEO",
            "page_description": (
                "Dashboard settimanale: quali AI usano gli italiani (Google Trends), "
                "traffico bot AI, crawler per settore, confronto Italia vs Mondo."
            ),
            "canonical_url": canonical("/tracker/"),
            "active_nav": "tracker",
            "noindex": not allow_indexing,
            "og_type": "website",
            "page_headline": (f"AI Tracker — Settimana {snapshot.week}, {snapshot.year}"),
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
            month_label = format_date_it(datetime(report.year, report.month, 1), "%B %Y")
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

        if snapshot.schema_version not in ("2.0", "3.0"):
            return None

        # AI top 3 from Google Trends averages (IT)
        ai_top3: list[dict[str, Any]] = []
        if snapshot.trends_it.averages:
            ranked = sorted(snapshot.trends_it.averages.items(), key=lambda x: x[1], reverse=True)
            for name, avg in ranked[:3]:
                ai_top3.append({"name": name, "avg": avg})

        # Bot percentage
        bot_pct = None
        if snapshot.bot_human_it.points:
            bot_pct = snapshot.bot_human_it.points[-1].bot_pct

        # Latest trends values
        trends_latest: dict[str, int] = {}
        if snapshot.trends_it.points:
            trends_latest = snapshot.trends_it.points[-1].values

        return {
            "ai_top3": ai_top3,
            "bot_pct_it": bot_pct,
            "trends_latest": trends_latest,
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

        # Snapshot giornalieri: un URL per ogni giorno archiviato (non solo
        # oggi), con lastmod = il giorno stesso: la pagina non cambia piu'
        # dopo la pubblicazione.
        for entry in self._build_archive_index():
            snap_y, snap_m, snap_d = entry["date"].split("-")
            urls.append(
                {
                    "loc": canonical(f"/archivio/{snap_y}/{snap_m}/{snap_d}/"),
                    "lastmod": entry["date"],
                    "priority": "0.8" if entry["date"] == today else "0.5",
                }
            )

        # Articoli: uno per ogni item indicizzabile mai pubblicato (da
        # _build_item_index, che scansiona tutto l'archivio), con lastmod
        # pari al giorno di pubblicazione sul sito — non "oggi" per tutti.
        for meta in self._build_item_index().values():
            urls.append(
                {"loc": canonical(meta["site_path"]), "lastmod": meta["date"], "priority": "0.7"}
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
            if not is_indexable(item) or item.id not in item_slugs:
                continue
            if item.published_at < news_cutoff:
                continue
            slug = item_slugs[item.id]
            news_entries.append(
                {
                    "loc": canonical(f"/archivio/{y}/{m}/{d}/{slug}/"),
                    # Data di pubblicazione SUL SITO (questo run), non quella
                    # della fonte: Google News valuta la freschezza della
                    # pagina indicizzata, non dell'articolo originale.
                    "publication_date": feed.generated_at.isoformat(),
                    "title": item.title_it,
                }
            )
        (site_dir / "sitemap-news.xml").write_text(
            renderer.render_sitemap_news({"entries": news_entries}), encoding="utf-8"
        )

        entries = [
            {
                "title": item.title_it,
                "url": (
                    canonical(f"/archivio/{y}/{m}/{d}/{item_slugs.get(item.id, 'untitled')}/")
                    if is_indexable(item) and item.id in item_slugs
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
                    "site_url": SITE_URL,
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
                    "site_url": SITE_URL,
                }
            ),
            encoding="utf-8",
        )

        # item_index.json: id -> site_path degli item con pagina propria, in
        # tutto l'archivio. Il client (app.js) non puo' ricostruire lo slug
        # di un articolo da solo (dipende da un contatore di disambiguazione
        # calcolato lato Python sull'intero batch del giorno): senza questo
        # indice, la ricerca cross-archivio linkava sempre allo snapshot del
        # giorno invece che alla pagina dell'articolo.
        item_index_json = {iid: meta["site_path"] for iid, meta in self._build_item_index().items()}
        data_dir = site_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "item_index.json").write_text(
            json.dumps(item_index_json, indent=2), encoding="utf-8"
        )

    # --- Top Week (rolling 7-day top 10) ---

    @staticmethod
    def _select_google_updates(
        items: list[Item], limit: int = 10, min_importance: int = 3
    ) -> list[Item]:
        """Seleziona gli aggiornamenti da FONTE Google da mostrare in evidenza su
        /top-settimana/: solo item provenienti da fonti ufficiali Google
        (``is_google_source``) o modifiche alle linee guida rilevate dal doc
        watcher (``is_doc_change``, la cui fonte è la documentazione Google).
        Esclude gli articoli di terze parti che parlano di Google. Filtra sotto
        una soglia di importanza (esclude gli annunci di eventi a bassa
        importanza), ordina per importanza e recency, limita a ``limit``."""
        selected = [
            i
            for i in items
            if (is_google_source(i.source.id) or i.is_doc_change) and i.importance >= min_importance
        ]
        selected.sort(key=lambda i: (i.importance, i.published_at), reverse=True)
        return selected[:limit]

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

        # Metadata (slug/site_path) degli item con pagina interna in
        # QUALSIASI giorno dell'archivio: prima solo gli item del feed di
        # oggi potevano linkare alla propria pagina, quelli degli altri 6
        # giorni finivano sempre linkati all'URL esterno della fonte anche
        # quando avevano gia' una pagina propria.
        item_idx = self._build_item_index()

        top10_cards: list[str] = []
        top10_itemlist: list[dict[str, str]] = []
        for idx, item_id in enumerate(ranked.top10, start=1):
            item = items_by_id.get(item_id)
            if not item:
                continue

            article_url, is_internal = _resolve_article_link(item, item_idx, item_slugs, day_iso)

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

        # Sezione "Aggiornamenti Google della settimana": gli item google_updates
        # e le modifiche alle linee guida degli ultimi 7 giorni, in evidenza a
        # prescindere dal ranking generico della top 10.
        google_cards: list[str] = []
        google_updates = self._select_google_updates(combined_items)
        for idx, item in enumerate(google_updates, start=1):
            article_url, is_internal = _resolve_article_link(item, item_idx, item_slugs, day_iso)
            google_cards.append(
                renderer.render_raw(
                    "partials/_card_top10.html.jinja",
                    {
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
                    },
                )
            )

        meta_line = (
            f"SYSTEM STATUS: OPTIMAL // ROLLING 7D // "
            f"{len(combined_items)} ARTICOLI ANALIZZATI // TOP 10"
        )

        ctx = {
            "page_title": "Novità SEO della settimana: le 10 notizie che contano",
            "page_description": (
                "Le 10 notizie SEO e AI più rilevanti degli ultimi 7 giorni, "
                "aggiornate ogni mattina."
            ),
            "canonical_url": canonical("/top-settimana/"),
            "active_nav": "top-week",
            "noindex": not allow_indexing,
            "meta_line": meta_line,
            "google_cards": google_cards,
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
