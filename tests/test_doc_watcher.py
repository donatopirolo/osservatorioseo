# tests/test_doc_watcher.py
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from osservatorio_seo.config import DocWatcherPage
from osservatorio_seo.doc_watcher.state import StateStore
from osservatorio_seo.doc_watcher.watcher import DocWatcher
from osservatorio_seo.http_client import HttpClient


@pytest.fixture
def page() -> DocWatcherPage:
    return DocWatcherPage(
        id="google_spam_policies",
        name="Google Spam Policies",
        url="https://developers.google.com/spam",
        selector="main article",
        type="html",
        category="google_docs_change",
        importance=5,
    )


async def test_first_run_saves_but_no_change(
    page: DocWatcherPage, tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        url="https://developers.google.com/spam",
        text="<html><body><main><article>Some spam policy v1</article></main></body></html>",
    )
    state = StateStore(tmp_path)
    async with HttpClient() as client:
        watcher = DocWatcher(http=client, state=state)
        result = await watcher.check(page)

    assert result.changed is False
    assert state.load_hash("google_spam_policies") is not None


async def test_second_run_same_content_no_change(
    page: DocWatcherPage, tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    html = "<html><body><main><article>Stable content</article></main></body></html>"
    httpx_mock.add_response(url="https://developers.google.com/spam", text=html)
    httpx_mock.add_response(url="https://developers.google.com/spam", text=html)

    state = StateStore(tmp_path)
    async with HttpClient() as client:
        watcher = DocWatcher(http=client, state=state)
        await watcher.check(page)
        result = await watcher.check(page)
    assert result.changed is False


async def test_second_run_changed_content_detected(
    page: DocWatcherPage, tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    html_old = "<html><body><main><article>Old text here.</article></main></body></html>"
    html_new = "<html><body><main><article>Old text here. Added new sentence about AI.</article></main></body></html>"
    httpx_mock.add_response(url="https://developers.google.com/spam", text=html_old)
    httpx_mock.add_response(url="https://developers.google.com/spam", text=html_new)

    state = StateStore(tmp_path)
    async with HttpClient() as client:
        watcher = DocWatcher(http=client, state=state)
        await watcher.check(page)
        result = await watcher.check(page)

    assert result.changed is True
    assert result.previous_hash != result.current_hash
    assert result.lines_added >= 1
    assert "+" in result.diff


def test_similarity_threshold_ignores_tiny_change() -> None:
    watcher = DocWatcher(http=None, state=None, similarity_threshold=0.003)  # type: ignore[arg-type]
    old = "a" * 10000
    new = old + "b"
    assert watcher._is_significant_change(old, new) is False
