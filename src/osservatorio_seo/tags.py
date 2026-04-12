"""Normalizzazione del vocabolario tag.

I tag arrivano dal modello AI in forma semi-libera (snake_case ma con
inconsistenze: plurali, spazi, apostrofi, sinonimi). Al momento NON c'è
una strategia SEO dedicata sui tag e non vengono generate pagine hub
individuali. Questo modulo serve a:

1. Collassare varianti ovvie (plurali, spazi→underscore, maiuscole)
2. Normalizzare in snake_case ASCII-safe
3. Mantenere un ``ALIAS_MAP`` per sinonimi editoriali noti

L'obiettivo dichiarato dall'utente è: "raccogliere dati con tag più
puliti per poi decidere in futuro la strategia SEO". Questo modulo è
il punto di consolidamento minimo.
"""

from __future__ import annotations

import re
import unicodedata

# Sinonimi editoriali: chiave = form canonica, valore = varianti da
# collassare. Mantenere minimalista, aggiungere pattern solo dopo aver
# osservato duplicati reali negli archive.
ALIAS_MAP: dict[str, set[str]] = {
    "core_update": {
        "core_update",
        "core_updates",
        "coreupdate",
        "google_core_update",
        "google_core_updates",
    },
    "google_search": {
        "google_search",
        "googlesearch",
        "search_google",
    },
    "search_central_live": {
        "search_central_live",
        "searchcentrallive",
        "google_search_central_live",
    },
    "googlebot": {"googlebot", "google_bot"},
    "crawling": {"crawling", "crawl", "crawlers"},
    "ai_overviews": {"ai_overviews", "ai_overview", "aioverviews", "aioverview"},
    "e_e_a_t": {"e_e_a_t", "eeat", "e_eat", "eat"},
    "structured_data": {"structured_data", "structureddata", "schema_markup"},
    "event": {"event", "events", "seo_event", "seo_events"},
    "google_event": {"google_event", "google_events"},
}


def _build_reverse_alias() -> dict[str, str]:
    rev: dict[str, str] = {}
    for canonical, variants in ALIAS_MAP.items():
        for v in variants:
            rev[v] = canonical
    return rev


_REVERSE_ALIAS = _build_reverse_alias()


def _strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize_tag(raw: str) -> str | None:
    """Normalizza un tag in forma snake_case canonica.

    Ritorna ``None`` se il tag è vuoto / invalido dopo la pulizia.
    """
    if not raw:
        return None
    t = _strip_accents(raw).lower().strip()
    # Rimuovi prefissi tipo "#"
    t = t.lstrip("#")
    # Sostituisci separatori non-alfanumerici con underscore
    t = re.sub(r"[^a-z0-9]+", "_", t)
    # Collassa underscore multipli e strip agli estremi
    t = re.sub(r"_+", "_", t).strip("_")
    if not t:
        return None
    # Plurali semplici → singolare (evitare casi noti come "news")
    if (
        t not in {"news", "analytics"}
        and t.endswith("s")
        and len(t) > 3
        and not t.endswith("ss")
        and not t.endswith("us")
    ):
        singular = t[:-1]
        if singular in _REVERSE_ALIAS or len(singular) >= 3:
            t = singular
    # Applica alias map
    return _REVERSE_ALIAS.get(t, t)


def normalize_tags(tags: list[str]) -> list[str]:
    """Normalizza una lista di tag rimuovendo duplicati mantenendo l'ordine."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in tags or []:
        n = normalize_tag(raw)
        if n is None or n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out
