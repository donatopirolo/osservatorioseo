"""Allarme sulle pagine sorvegliate che non si leggono, e baseline implausibili."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pytest_httpx import HTTPXMock

from osservatorio_seo.config import DocWatcherPage, Settings
from osservatorio_seo.doc_watcher.health import ALERT_AFTER_DAYS, HEALTH_FILE, WatchHealth
from osservatorio_seo.doc_watcher.state import StateStore
from osservatorio_seo.doc_watcher.watcher import DocExtractError, DocWatcher
from osservatorio_seo.http_client import HttpClient
from osservatorio_seo.pipeline import Pipeline

URL = "https://example.com/policy"


def mk_page(page_id: str = "p1", alert: bool = True) -> DocWatcherPage:
    return DocWatcherPage(id=page_id, name="P", url=URL, selector="main", importance=3, alert=alert)


# --- WatchHealth -------------------------------------------------------------


def test_failures_count_days_not_runs(tmp_path: Path) -> None:
    h = WatchHealth(tmp_path / HEALTH_FILE)
    h.record_failure("p1", "403", "2026-11-17", alert_enabled=True)
    h.record_failure("p1", "403", "2026-11-17", alert_enabled=True)  # rilancio stesso giorno
    assert h.pages["p1"].failing_days == 1
    h.record_failure("p1", "403", "2026-11-18", alert_enabled=True)
    assert h.alerts() == {}
    h.record_failure("p1", "403", "2026-11-19", alert_enabled=True)
    assert h.pages["p1"].failing_days == ALERT_AFTER_DAYS
    assert set(h.alerts()) == {"p1"}
    assert h.pages["p1"].failing_since == "2026-11-17"


def test_success_clears_and_alert_false_never_alerts(tmp_path: Path) -> None:
    h = WatchHealth(tmp_path / HEALTH_FILE)
    for day in ("2026-11-17", "2026-11-18", "2026-11-19"):
        h.record_failure("p1", "x", day, alert_enabled=True)
        h.record_failure("quiet", "x", day, alert_enabled=False)
    assert set(h.alerts()) == {"p1"}
    h.record_success("p1")
    assert h.alerts() == {}
    assert "quiet" in h.pages


def test_save_load_roundtrip_and_prune(tmp_path: Path) -> None:
    path = tmp_path / HEALTH_FILE
    h = WatchHealth(path)
    h.record_failure("p1", "e", "2026-11-19", alert_enabled=True)
    h.record_failure("gone", "e", "2026-11-19", alert_enabled=True)
    h.prune({"p1"})
    h.save()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert list(data["pages"]) == ["p1"]
    assert WatchHealth(path).pages["p1"].last_error == "e"


# --- pipeline -----------------------------------------------------------------


def _pipeline(tmp_path: Path) -> Pipeline:
    settings = Settings(
        openrouter_api_key="sk-test",
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        state_dir=tmp_path / "state",
        seen_urls_path=tmp_path / "state" / "seen_urls.json",
    )
    return Pipeline(
        settings=settings,
        sources_path=tmp_path / "s.yml",
        doc_watcher_path=tmp_path / "d.yml",
    )


async def test_check_doc_pages_writes_health(tmp_path: Path) -> None:
    watcher = AsyncMock(spec=DocWatcher)
    watcher.check.side_effect = RuntimeError("unexpected status 403")
    pipeline = _pipeline(tmp_path)
    await pipeline._check_doc_pages([mk_page()], watcher)
    data = json.loads((tmp_path / "state" / HEALTH_FILE).read_text(encoding="utf-8"))
    assert data["pages"]["p1"]["failing_days"] == 1
    assert "403" in data["pages"]["p1"]["last_error"]


# --- baseline implausibili ------------------------------------------------------


async def test_block_page_never_becomes_baseline(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=URL, text="<html><main>Enable JavaScript and cookies to continue</main></html>"
    )
    state = StateStore(tmp_path)
    async with HttpClient() as client:
        watcher = DocWatcher(http=client, state=state)
        with pytest.raises(DocExtractError, match="anti-bot"):
            await watcher.check(mk_page())
    assert state.load_hash("p1") is None


async def test_too_short_text_rejected(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=URL, text="<html><main>Home</main></html>")
    state = StateStore(tmp_path)
    async with HttpClient() as client:
        watcher = DocWatcher(http=client, state=state, min_text_chars=300)
        with pytest.raises(DocExtractError, match="troppo corto"):
            await watcher.check(mk_page())
    assert state.load_hash("p1") is None


async def test_long_page_mentioning_captcha_is_fine(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    body = "Google explains how to verify you are human with a captcha. " * 100
    httpx_mock.add_response(url=URL, text=f"<html><main>{body}</main></html>")
    state = StateStore(tmp_path)
    async with HttpClient() as client:
        watcher = DocWatcher(http=client, state=state, min_text_chars=300)
        result = await watcher.check(mk_page())
    assert result.changed is False
    assert state.load_hash("p1") is not None


def test_real_config_is_valid() -> None:
    from osservatorio_seo.config import load_doc_watcher

    pages = load_doc_watcher(Path("config/doc_watcher.yml"))
    ids = [p.id for p in pages]
    assert len(ids) == len(set(ids))
    assert "google_quality_rater_guidelines_en" in ids
    assert "google_quality_rater_guidelines" not in ids  # il finto PDF "IT"


# --- pagine renderizzate con Playwright ------------------------------------------


async def test_render_page_uses_renderer_and_selector(tmp_path: Path) -> None:
    body = "Bing Webmaster Guidelines. " * 40
    calls: list[tuple[str, str | None]] = []

    async def fake_render(url: str, wait_for: str | None) -> str:
        calls.append((url, wait_for))
        return f"<html><body><nav>menu</nav><div class='helpContent'>{body}</div></body></html>"

    page = DocWatcherPage(
        id="bing", name="Bing", url=URL, selector=".helpContent", importance=5, render=True
    )
    state = StateStore(tmp_path)
    async with HttpClient() as client:
        watcher = DocWatcher(http=client, state=state, min_text_chars=300, renderer=fake_render)
        result = await watcher.check(page)
    assert calls == [(URL, ".helpContent")]
    assert "menu" not in result.new_text
    assert "Bing Webmaster Guidelines" in result.new_text


async def test_render_page_without_renderer_fails_cleanly(tmp_path: Path) -> None:
    page = DocWatcherPage(id="bing", name="Bing", url=URL, importance=5, render=True)
    async with HttpClient() as client:
        watcher = DocWatcher(http=client, state=StateStore(tmp_path))
        with pytest.raises(DocExtractError, match="renderer"):
            await watcher.check(page)
