"""Valutazione di salute del run del pipeline.

Usato dal CLI per decidere l'exit code: se troppi summary falliscono
(es. chiave OpenRouter scaduta) il run produce 0 item ma il workflow
GitHub Actions resta verde. Ritornando un exit code != 0 facciamo
scattare lo step "Open issue on failure" già configurato.
"""

from __future__ import annotations

from osservatorio_seo.models import Feed

DEFAULT_SUMMARIZE_FAILURE_THRESHOLD = 0.5


def feed_health(
    feed: Feed,
    summarize_failure_threshold: float = DEFAULT_SUMMARIZE_FAILURE_THRESHOLD,
) -> tuple[bool, str]:
    """Decide se un run è "healthy" o richiede alert.

    Ritorna (is_healthy, reason). Reason è human-readable per il log/CLI.
    """
    attempted = feed.stats.summarize_attempted
    failed = feed.stats.summarize_failed
    if attempted == 0:
        return True, "no summarize attempts"
    failure_rate = failed / attempted
    if failure_rate >= summarize_failure_threshold:
        return False, (
            f"summarizer failure rate {failure_rate:.0%} "
            f"({failed}/{attempted}) >= {summarize_failure_threshold:.0%} threshold"
        )
    succeeded = attempted - failed
    return True, f"summarizer ok ({succeeded}/{attempted} succeeded)"
