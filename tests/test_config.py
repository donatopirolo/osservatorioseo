# tests/test_config.py
from pathlib import Path

import pytest

from osservatorio_seo.config import (
    load_doc_watcher,
    load_settings,
    load_sources,
)


def test_load_sources(fixtures_dir: Path) -> None:
    sources = load_sources(fixtures_dir / "sources.test.yml")
    enabled_ids = [s.id for s in sources]
    assert "google_search_central" in enabled_ids
    assert "some_scraper_site" in enabled_ids
    assert "disabled_source" not in enabled_ids


def test_load_doc_watcher(fixtures_dir: Path) -> None:
    pages = load_doc_watcher(fixtures_dir / "doc_watcher.test.yml")
    assert len(pages) == 1
    assert pages[0].id == "google_spam_policies"
    assert pages[0].importance == 5


def test_load_settings_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        load_settings()


def test_load_settings_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    s = load_settings()
    assert s.openrouter_api_key == "sk-test"
    assert s.summarizer_model == "google/gemini-2.0-flash"
