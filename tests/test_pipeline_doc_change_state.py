"""Test che il pipeline aggiorni lo state del doc_watcher solo dopo
un summarize riuscito.

Senza questa garanzia un fail del summarizer (es. 401 OpenRouter)
"consumerebbe" il diff silenziosamente: lo state verrebbe aggiornato
sulla nuova versione e la run successiva non rivedrebbe piu' la modifica.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

from osservatorio_seo.config import DocWatcherPage, Settings
from osservatorio_seo.doc_watcher.state import StateStore
from osservatorio_seo.doc_watcher.watcher import DocChangeResult
from osservatorio_seo.pipeline import Pipeline
from osservatorio_seo.summarizer import AISummary, Summarizer


def _make_pipeline(tmp_path: Path) -> Pipeline:
    settings = Settings(
        openrouter_api_key="sk-test",
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        state_dir=tmp_path / "state",
    )
    return Pipeline(
        settings=settings,
        sources_path=tmp_path / "unused-sources.yml",
        doc_watcher_path=tmp_path / "unused-doc.yml",
    )


def _make_page() -> DocWatcherPage:
    return DocWatcherPage(
        id="google_spam_policies",
        name="Google Spam Policies",
        url="https://developers.google.com/spam",
        selector="main article",
        type="html",
        category="google_docs_change",
        importance=5,
    )


def _make_change_result() -> DocChangeResult:
    return DocChangeResult(
        page_id="google_spam_policies",
        changed=True,
        previous_hash="sha256:OLD_HASH",
        current_hash="sha256:NEW_HASH",
        diff="--- prev\n+++ curr\n+new spam policy line",
        lines_added=1,
        lines_removed=0,
        checked_at=datetime.now(UTC),
        new_text="new normalized text content",
    )


async def test_summarize_failure_preserves_doc_state(tmp_path: Path) -> None:
    state = StateStore(tmp_path / "state")
    state.save("google_spam_policies", "sha256:OLD_HASH", "old text")

    summarizer = AsyncMock(spec=Summarizer)
    summarizer.summarize_doc_change.side_effect = Exception("401 Unauthorized")

    pipeline = _make_pipeline(tmp_path)
    items, _cost, attempted, failed = await pipeline._summarize_doc_changes(
        results=[_make_change_result()],
        pages=[_make_page()],
        summarizer=summarizer,
        state=state,
    )

    assert items == []
    assert attempted == 1
    assert failed == 1
    # Lo state deve essere ancora quello vecchio: niente "consumo silenzioso" del diff
    assert state.load_hash("google_spam_policies") == "sha256:OLD_HASH"
    assert state.load_text("google_spam_policies") == "old text"


async def test_summarize_success_commits_doc_state(tmp_path: Path) -> None:
    state = StateStore(tmp_path / "state")
    state.save("google_spam_policies", "sha256:OLD_HASH", "old text")

    summarizer = AsyncMock(spec=Summarizer)
    summarizer.summarize_doc_change.return_value = AISummary(
        title_it="Aggiornamento policy spam",
        summary_it="Google ha aggiunto una riga sulle policy anti-spam.",
        category="google_docs_change",
        tags=["spam"],
        importance=5,
        model_used="google/gemini-2.0-flash",
        cost_eur=0.001,
    )

    pipeline = _make_pipeline(tmp_path)
    items, _cost, attempted, failed = await pipeline._summarize_doc_changes(
        results=[_make_change_result()],
        pages=[_make_page()],
        summarizer=summarizer,
        state=state,
    )

    assert len(items) == 1
    assert attempted == 1
    assert failed == 0
    # State aggiornato sul nuovo hash/text
    assert state.load_hash("google_spam_policies") == "sha256:NEW_HASH"
    assert state.load_text("google_spam_policies") == "new normalized text content"
