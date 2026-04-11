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


def is_google_source(source_id: str) -> bool:
    return source_id in GOOGLE_SOURCE_IDS


def override_importance(source_id: str, ai_importance: int) -> int:
    """Restituisce l'importance finale considerando le policy editoriali.

    Google → sempre 5. Tutte le altre fonti → rispetta il giudizio AI.
    """
    if is_google_source(source_id):
        return 5
    return ai_importance
