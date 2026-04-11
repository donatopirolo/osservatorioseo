import json
from datetime import UTC, datetime

from pytest_httpx import HTTPXMock

from osservatorio_seo.models import RawItem, Source
from osservatorio_seo.summarizer import (
    AISummary,
    DocChangeSummary,
    Summarizer,
    _parse_json_loose,
)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def mk_raw() -> RawItem:
    return RawItem(
        title="March 2026 core update done",
        url="https://example.com/a",
        source_id="google_search_central",
        published_at=datetime.now(UTC),
        content="Google announced today that the March 2026 core update is fully rolled out.",
    )


def mk_source() -> Source:
    return Source(
        id="google_search_central",
        name="Google Search Central Blog",
        authority=10,
        type="official",
        fetcher="rss",
        feed_url="https://example.com/feed",
    )


def mock_response(payload: dict) -> dict:
    return {
        "choices": [{"message": {"content": json.dumps(payload)}}],
        "usage": {"prompt_tokens": 500, "completion_tokens": 80},
        "model": "google/gemini-2.0-flash",
    }


async def test_summarize_item_success(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=OPENROUTER_URL,
        json=mock_response(
            {
                "title_it": "Core update marzo 2026 completato",
                "summary_it": "Google ha completato il rollout del core update di marzo 2026.",
                "category": "google_updates",
                "tags": ["core_update", "ranking"],
                "importance": 5,
            }
        ),
    )
    summarizer = Summarizer(api_key="sk-test")
    result = await summarizer.summarize_item(mk_raw(), mk_source())
    assert isinstance(result, AISummary)
    assert result.importance == 5
    assert "marzo" in result.summary_it.lower()


async def test_summarize_item_retries_on_malformed_json(httpx_mock: HTTPXMock) -> None:
    # prima risposta: JSON malformato
    httpx_mock.add_response(
        url=OPENROUTER_URL,
        json={"choices": [{"message": {"content": "NOT JSON"}}], "usage": {}},
    )
    # retry: JSON corretto
    httpx_mock.add_response(
        url=OPENROUTER_URL,
        json=mock_response(
            {
                "title_it": "Test",
                "summary_it": "Test summary.",
                "category": "google_updates",
                "tags": [],
                "importance": 3,
            }
        ),
    )
    summarizer = Summarizer(api_key="sk-test")
    result = await summarizer.summarize_item(mk_raw(), mk_source())
    assert result.importance == 3


async def test_summarize_falls_back_to_next_model(httpx_mock: HTTPXMock) -> None:
    # primo modello fallisce (errore)
    httpx_mock.add_response(url=OPENROUTER_URL, status_code=500)
    httpx_mock.add_response(url=OPENROUTER_URL, status_code=500)
    # fallback model risponde ok
    httpx_mock.add_response(
        url=OPENROUTER_URL,
        json=mock_response(
            {
                "title_it": "Fallback ok",
                "summary_it": "Riassunto dal fallback model.",
                "category": "ai_models",
                "tags": [],
                "importance": 2,
            }
        ),
    )
    summarizer = Summarizer(
        api_key="sk-test",
        primary_model="google/gemini-2.0-flash",
        fallback_models=["anthropic/claude-haiku-4.5"],
    )
    result = await summarizer.summarize_item(mk_raw(), mk_source())
    assert result.importance == 2


async def test_summarize_doc_change(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=OPENROUTER_URL,
        json=mock_response(
            {
                "title_it": "⚠️ Google ha aggiornato Spam Policies",
                "summary_it": "Aggiunta nuova sezione sul scaled content abuse.",
                "tags": ["spam_policies"],
                "importance": 5,
            }
        ),
    )
    summarizer = Summarizer(api_key="sk-test")
    result = await summarizer.summarize_doc_change(
        page_name="Google Spam Policies",
        page_url="https://developers.google.com/spam",
        diff="+new section about scaled content\n-old sentence removed",
    )
    assert isinstance(result, DocChangeSummary)
    assert result.title_it.startswith("⚠️")


def test_parse_json_loose_plain() -> None:
    assert _parse_json_loose('{"a": 1}') == {"a": 1}


def test_parse_json_loose_with_markdown_fence() -> None:
    content = 'Here is the JSON:\n```json\n{"a": 1, "b": [2, 3]}\n```\nHope this helps!'
    assert _parse_json_loose(content) == {"a": 1, "b": [2, 3]}


def test_parse_json_loose_with_prefix_text() -> None:
    content = 'Certo, ecco:\n{"importance": 3, "tags": ["x"]}\nFine.'
    assert _parse_json_loose(content) == {"importance": 3, "tags": ["x"]}


def test_parse_json_loose_raises_on_no_json() -> None:
    import pytest

    with pytest.raises(ValueError, match="no JSON"):
        _parse_json_loose("just plain text no braces at all")
