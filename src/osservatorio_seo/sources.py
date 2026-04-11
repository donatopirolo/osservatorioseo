"""Policy editoriali sulle fonti.

Definisce regole trasversali che sovrascrivono il giudizio del summarizer AI
quando necessario per motivi di autorevolezza / governance editoriale.
"""

from __future__ import annotations

# Fonti ufficiali Google: qualsiasi contenuto pubblicato da queste fonti è
# considerato critical by design (importance=5), indipendentemente dal
# giudizio del summarizer. Ragione: sono la sorgente canonica per tutto
# ciò che riguarda algoritmo di ricerca, crawling, indicizzazione e
# documentazione ufficiale. Ogni loro post ha implicazioni operative
# per chi fa SEO.
GOOGLE_SOURCE_IDS: frozenset[str] = frozenset(
    {
        "google_search_central_blog",
        "google_search_status_dashboard",
        "google_deepmind_blog",
        "web_dev",
        "chrome_developers_blog",
        "searchliaison_x",
    }
)

# Tag che identificano item di tipo "evento" (conferenze, meetup,
# Search Central Live, ecc.). Gli annunci di eventi NON devono ereditare
# il bump a 5 stelle anche se provengono da fonte Google: sono info di
# networking, non cambi operativi all'algoritmo o alla documentazione.
EVENT_TAGS: frozenset[str] = frozenset(
    {
        "event",
        "events",
        "seo_event",
        "seo_events",
        "google_event",
        "google_events",
        "search_central_live",
        "conference",
        "meetup",
        "seo_community",
    }
)


def is_google_source(source_id: str) -> bool:
    return source_id in GOOGLE_SOURCE_IDS


def is_event_item(tags: list[str] | None) -> bool:
    if not tags:
        return False
    return bool({t.lower() for t in tags} & EVENT_TAGS)


def override_importance(
    source_id: str,
    ai_importance: int,
    tags: list[str] | None = None,
) -> int:
    """Restituisce l'importance finale considerando le policy editoriali.

    Google → sempre 5, TRANNE per annunci di eventi (Search Central Live,
    conferenze, meetup) dove rispettiamo il giudizio AI. Tutte le altre
    fonti → rispetta il giudizio AI.
    """
    if is_google_source(source_id):
        if is_event_item(tags):
            return ai_importance
        return 5
    return ai_importance
