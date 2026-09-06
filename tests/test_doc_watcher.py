# tests/test_doc_watcher.py
from pathlib import Path

import httpx
import pytest
from pytest_httpx import HTTPXMock

from osservatorio_seo.config import DocWatcherPage
from osservatorio_seo.doc_watcher.state import StateStore
from osservatorio_seo.doc_watcher.watcher import DocExtractError, DocWatcher
from osservatorio_seo.http_client import HttpClient

# Corpo lungo (~3900 char) per simulare una pagina reale tipo Spam Policies:
# una piccola frase aggiunta qui e' una frazione minuscola del totale, il
# caso esatto che la vecchia soglia relativa 0.003 non rilevava mai.
LONG_BODY = "Google Search spam policies paragraph. " * 100


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
    added = (
        " Added a completely new paragraph about AI Overviews and how site "
        "owners should handle scaled content abuse under the updated policy."
    )
    assert len(added) >= 80
    html_old = f"<html><body><main><article>{LONG_BODY}</article></main></body></html>"
    html_new = f"<html><body><main><article>{LONG_BODY}{added}</article></main></body></html>"
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


async def test_significant_change_does_not_commit_state(
    page: DocWatcherPage, tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    """Su significant change il watcher non aggiorna lo state.

    Il commit deve avvenire solo dopo che il summarizer ha avuto successo,
    per evitare di "consumare" il diff se il summarizer fallisce. Senza
    questa garanzia, un fail del summarizer farebbe perdere il diff per
    sempre (la run successiva confronterebbe la nuova versione con se
    stessa).
    """
    added = (
        " Added a new sentence about AI overviews and how it changes the "
        "guidance for scaled content abuse across the whole spam policy."
    )
    assert len(added) >= 80
    html_old = f"<html><body><main><article>{LONG_BODY}</article></main></body></html>"
    html_new = f"<html><body><main><article>{LONG_BODY}{added}</article></main></body></html>"
    httpx_mock.add_response(url="https://developers.google.com/spam", text=html_old)
    httpx_mock.add_response(url="https://developers.google.com/spam", text=html_new)

    state = StateStore(tmp_path)
    async with HttpClient() as client:
        watcher = DocWatcher(http=client, state=state)
        await watcher.check(page)
        bootstrap_hash = state.load_hash(page.id)

        result = await watcher.check(page)

    assert result.changed is True
    assert result.current_hash != bootstrap_hash
    # Lo state deve essere ancora il vecchio: il watcher non lo aggiorna
    # piu in autonomia su significant change.
    assert state.load_hash(page.id) == bootstrap_hash


def test_min_changed_chars_ignores_tiny_change() -> None:
    watcher = DocWatcher(http=None, state=None, min_changed_chars=80)  # type: ignore[arg-type]
    old = "a" * 10000
    new = old + "b"
    assert watcher._is_significant_change(old, new) is False


def test_changed_chars_counts_insert_delete_replace() -> None:
    watcher = DocWatcher(http=None, state=None)  # type: ignore[arg-type]
    assert watcher._changed_chars("abc", "abcXYZ") == 3  # insert
    assert watcher._changed_chars("abcXYZ", "abc") == 3  # delete
    # replace di 4 caratteri con altri 4: max(4,4), non 4+4
    old = "x" * 100 + "AAAA" + "y" * 100
    new = "x" * 100 + "BBBB" + "y" * 100
    assert watcher._changed_chars(old, new) == 4
    assert watcher._changed_chars("identical text", "identical text") == 0


def test_is_significant_exactly_at_threshold() -> None:
    watcher = DocWatcher(http=None, state=None, min_changed_chars=80)  # type: ignore[arg-type]
    assert watcher._is_significant_change(LONG_BODY, LONG_BODY + "z" * 80) is True
    assert watcher._is_significant_change(LONG_BODY, LONG_BODY + "z" * 79) is False


async def test_small_change_in_long_page_not_detected_and_baseline_kept(
    page: DocWatcherPage, tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    """Regressione: la vecchia soglia relativa 0.003 non rilevava mai una
    piccola frase aggiunta a una pagina lunga come le Spam Policies."""
    small_addition = " New short sentence about AI."
    assert len(small_addition) < 80
    html_old = f"<html><body><main><article>{LONG_BODY}</article></main></body></html>"
    html_new = (
        f"<html><body><main><article>{LONG_BODY}{small_addition}</article></main></body></html>"
    )
    httpx_mock.add_response(url="https://developers.google.com/spam", text=html_old)
    httpx_mock.add_response(url="https://developers.google.com/spam", text=html_new)

    state = StateStore(tmp_path)
    async with HttpClient() as client:
        watcher = DocWatcher(http=client, state=state)
        await watcher.check(page)
        bootstrap_hash = state.load_hash(page.id)
        bootstrap_text = state.load_text(page.id)
        result = await watcher.check(page)

    assert result.changed is False
    assert state.load_hash(page.id) == bootstrap_hash
    assert state.load_text(page.id) == bootstrap_text
    assert "New short sentence" not in (state.load_text(page.id) or "")


async def test_small_changes_accumulate_until_threshold(
    page: DocWatcherPage, tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    """Due modifiche sotto soglia in run separati, sommate, superano
    MIN_CHANGED_CHARS: al terzo run devono essere rilevate insieme."""
    sentence_one = " Sentence one about ranking systems and site quality."
    sentence_two = " Sentence two about scaled content abuse policies here."
    assert len(sentence_one) < 80
    assert len(sentence_one) + len(sentence_two) >= 80

    body_v1 = LONG_BODY
    body_v2 = LONG_BODY + sentence_one
    body_v3 = body_v2 + sentence_two

    def wrap(text: str) -> str:
        return f"<html><body><main><article>{text}</article></main></body></html>"

    httpx_mock.add_response(url="https://developers.google.com/spam", text=wrap(body_v1))
    httpx_mock.add_response(url="https://developers.google.com/spam", text=wrap(body_v2))
    httpx_mock.add_response(url="https://developers.google.com/spam", text=wrap(body_v3))

    state = StateStore(tmp_path)
    async with HttpClient() as client:
        watcher = DocWatcher(http=client, state=state)
        await watcher.check(page)
        bootstrap_hash = state.load_hash(page.id)

        result_v2 = await watcher.check(page)
        assert result_v2.changed is False
        assert state.load_hash(page.id) == bootstrap_hash

        result_v3 = await watcher.check(page)

    assert result_v3.changed is True
    assert "Sentence one" in result_v3.diff
    assert "Sentence two" in result_v3.diff
    # Il watcher non committa MAI lo state da solo: e' compito della pipeline
    # dopo un summary riuscito (vedi test_significant_change_does_not_commit_state).
    assert state.load_hash(page.id) == bootstrap_hash


async def test_http_error_status_raises_and_state_untouched(
    page: DocWatcherPage, tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    """Una pagina che risponde 403 e' un errore, non "nessun cambiamento":
    HttpClient solleva gia' su status != 200 (fix task 0.4), qui verifichiamo
    che il watcher propaghi l'errore senza toccare lo state."""
    httpx_mock.add_response(
        url="https://developers.google.com/spam", status_code=403, text="Forbidden"
    )
    state = StateStore(tmp_path)
    async with HttpClient() as client:
        watcher = DocWatcher(http=client, state=state)
        with pytest.raises(httpx.HTTPStatusError):
            await watcher.check(page)
    assert state.load_hash(page.id) is None


async def test_http_error_after_bootstrap_keeps_baseline(
    page: DocWatcherPage, tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    """Se la pagina inizia a rispondere 404 dopo un bootstrap riuscito, la
    baseline precedente non deve essere sovrascritta da un errore."""
    html_old = f"<html><body><main><article>{LONG_BODY}</article></main></body></html>"
    httpx_mock.add_response(url="https://developers.google.com/spam", text=html_old)
    httpx_mock.add_response(
        url="https://developers.google.com/spam", status_code=404, text="Not Found"
    )
    state = StateStore(tmp_path)
    async with HttpClient() as client:
        watcher = DocWatcher(http=client, state=state)
        await watcher.check(page)
        bootstrap_hash = state.load_hash(page.id)
        with pytest.raises(httpx.HTTPStatusError):
            await watcher.check(page)
    assert state.load_hash(page.id) == bootstrap_hash


async def test_selector_no_match_raises(
    page: DocWatcherPage, tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    """Se Google cambia la struttura HTML e il selettore non matcha piu'
    nulla, il watcher deve sollevare invece di ripiegare silenziosamente
    su tutta la pagina (header/nav/footer inclusi)."""
    httpx_mock.add_response(
        url="https://developers.google.com/spam",
        text="<html><body><div>No main article here</div></body></html>",
    )
    state = StateStore(tmp_path)
    async with HttpClient() as client:
        watcher = DocWatcher(http=client, state=state)
        with pytest.raises(DocExtractError, match="matched nothing"):
            await watcher.check(page)
    assert state.load_hash(page.id) is None
