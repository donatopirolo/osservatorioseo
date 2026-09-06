"""Valutazione di salute del run del pipeline.

Usato dal CLI per decidere l'exit code: se troppi summary falliscono
(es. chiave OpenRouter scaduta) o troppe fonti falliscono (es. bloccate
con 403/404) il run puo' produrre poco o nulla ma il workflow GitHub
Actions resterebbe verde. Ritornando un exit code != 0 facciamo
scattare lo step "Open issue on failure" già configurato.
"""

from __future__ import annotations

from osservatorio_seo.models import Feed

DEFAULT_SUMMARIZE_FAILURE_THRESHOLD = 0.5
DEFAULT_SOURCE_FAILURE_THRESHOLD = 0.5


def feed_health(
    feed: Feed,
    summarize_failure_threshold: float = DEFAULT_SUMMARIZE_FAILURE_THRESHOLD,
    source_failure_threshold: float = DEFAULT_SOURCE_FAILURE_THRESHOLD,
) -> tuple[bool, str]:
    """Decide se un run è "healthy" o richiede alert.

    Ritorna (is_healthy, reason). Reason è human-readable per il log/CLI.
    """
    checked = feed.stats.sources_checked
    source_failed = feed.stats.sources_failed
    if checked > 0:
        source_failure_rate = source_failed / checked
        if source_failure_rate >= source_failure_threshold:
            return False, (
                f"source failure rate {source_failure_rate:.0%} "
                f"({source_failed}/{checked}) >= {source_failure_threshold:.0%} threshold"
            )

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
