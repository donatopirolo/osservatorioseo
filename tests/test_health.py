"""Test per la valutazione di salute del run del pipeline."""

from __future__ import annotations

from datetime import UTC, datetime

from osservatorio_seo.health import feed_health
from osservatorio_seo.models import Feed, FeedStats


def _make_feed(
    *, attempted: int, failed: int, sources_checked: int = 1, sources_failed: int = 0
) -> Feed:
    return Feed(
        generated_at=datetime.now(UTC),
        generated_at_local=datetime.now(UTC),
        timezone="Europe/Rome",
        run_id="test-run",
        stats=FeedStats(
            sources_checked=sources_checked,
            sources_failed=sources_failed,
            items_collected=attempted,
            items_after_dedup=attempted,
            doc_changes_detected=0,
            ai_cost_eur=0.0,
            summarize_attempted=attempted,
            summarize_failed=failed,
        ),
        top10=[],
        categories={},
        items=[],
        doc_watcher_status=[],
        failed_sources=[],
    )


def test_no_summarize_attempts_is_healthy() -> None:
    """Senza tentativi di summarize non possiamo concludere nulla → healthy."""
    healthy, _ = feed_health(_make_feed(attempted=0, failed=0))
    assert healthy is True


def test_all_summaries_failed_is_unhealthy() -> None:
    """Caso reale del 401 OpenRouter: tutti i summary falliscono."""
    healthy, reason = feed_health(_make_feed(attempted=10, failed=10))
    assert healthy is False
    assert "10/10" in reason


def test_majority_succeeded_is_healthy() -> None:
    healthy, _ = feed_health(_make_feed(attempted=10, failed=2))
    assert healthy is True


def test_at_threshold_is_unhealthy() -> None:
    """Failure rate esattamente al threshold (default 0.5) → unhealthy."""
    healthy, _ = feed_health(_make_feed(attempted=10, failed=5))
    assert healthy is False


def test_just_below_threshold_is_healthy() -> None:
    healthy, _ = feed_health(_make_feed(attempted=10, failed=4))
    assert healthy is True


def test_custom_threshold_respected() -> None:
    """Soglia configurabile per test/uso futuro."""
    feed = _make_feed(attempted=10, failed=3)
    assert feed_health(feed, summarize_failure_threshold=0.2)[0] is False
    assert feed_health(feed, summarize_failure_threshold=0.5)[0] is True


def test_no_sources_checked_is_healthy() -> None:
    """Senza fonti da controllare non possiamo concludere nulla → healthy."""
    healthy, _ = feed_health(_make_feed(attempted=0, failed=0, sources_checked=0))
    assert healthy is True


def test_half_sources_failed_is_unhealthy() -> None:
    """Regressione: 7 fonti morte su 21 restavano invisibili. Qui la metà
    esatta delle fonti fallisce → deve scattare unhealthy."""
    healthy, reason = feed_health(
        _make_feed(attempted=0, failed=0, sources_checked=10, sources_failed=5)
    )
    assert healthy is False
    assert "5/10" in reason


def test_minority_sources_failed_is_healthy() -> None:
    """Caso produzione attuale: 7/21 fonti morte, sotto la soglia del 50%."""
    healthy, _ = feed_health(
        _make_feed(attempted=0, failed=0, sources_checked=21, sources_failed=7)
    )
    assert healthy is True


def test_source_failure_checked_before_summarizer() -> None:
    """Le fonti guasto sono controllate per prime: un guasto a monte e' piu'
    informativo di un summarizer che non ha ricevuto nulla da riassumere."""
    healthy, reason = feed_health(
        _make_feed(attempted=10, failed=0, sources_checked=10, sources_failed=6)
    )
    assert healthy is False
    assert "source failure" in reason


def test_custom_source_threshold_respected() -> None:
    feed = _make_feed(attempted=0, failed=0, sources_checked=10, sources_failed=3)
    assert feed_health(feed, source_failure_threshold=0.2)[0] is False
    assert feed_health(feed, source_failure_threshold=0.5)[0] is True
