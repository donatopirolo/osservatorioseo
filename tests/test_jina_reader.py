from datetime import UTC, datetime

from pytest_httpx import HTTPXMock

from osservatorio_seo.http_client import HttpClient
from osservatorio_seo.jina_reader import JinaReader
from osservatorio_seo.models import RawItem


def mk_raw(url: str = "https://example.com/a", content: str = "excerpt breve") -> RawItem:
    return RawItem(
        title="t",
        url=url,
        source_id="s",
        published_at=datetime.now(UTC),
        content=content,
    )


async def test_enrich_replaces_content_on_meaningful_gain(httpx_mock: HTTPXMock) -> None:
    long_text = "Articolo completo. " * 100  # ben oltre i 500 char di guadagno minimo
    httpx_mock.add_response(url="https://r.jina.ai/https://example.com/a", text=long_text)
    async with HttpClient() as http:
        reader = JinaReader(http, api_key="k")
        items, attempted, failed = await reader.enrich([mk_raw()])

    assert attempted == 1
    assert failed == 0
    assert items[0].content == long_text.strip()


async def test_enrich_keeps_original_when_gain_too_small(httpx_mock: HTTPXMock) -> None:
    original = "excerpt breve"
    httpx_mock.add_response(url="https://r.jina.ai/https://example.com/a", text="poco piu' lungo")
    async with HttpClient() as http:
        reader = JinaReader(http, api_key="k", min_gain_chars=500)
        items, attempted, failed = await reader.enrich([mk_raw(content=original)])

    assert attempted == 1
    assert failed == 0
    assert items[0].content == original


async def test_enrich_falls_back_on_http_failure(httpx_mock: HTTPXMock) -> None:
    original = "excerpt breve"
    httpx_mock.add_response(url="https://r.jina.ai/https://example.com/a", status_code=500)
    httpx_mock.add_response(url="https://r.jina.ai/https://example.com/a", status_code=500)
    httpx_mock.add_response(url="https://r.jina.ai/https://example.com/a", status_code=500)
    async with HttpClient() as http:
        reader = JinaReader(http, api_key="k")
        items, attempted, failed = await reader.enrich([mk_raw(content=original)])

    assert attempted == 1
    assert failed == 1
    assert items[0].content == original


async def test_enrich_without_api_key_makes_no_request(httpx_mock: HTTPXMock) -> None:
    async with HttpClient() as http:
        reader = JinaReader(http, api_key=None)
        items, attempted, failed = await reader.enrich([mk_raw()])

    assert attempted == 0
    assert failed == 0
    assert len(httpx_mock.get_requests()) == 0
    assert items[0].content == "excerpt breve"


async def test_enrich_sends_bearer_authorization(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://r.jina.ai/https://example.com/a", text="Articolo completo. " * 100
    )
    async with HttpClient() as http:
        reader = JinaReader(http, api_key="segreto")
        await reader.enrich([mk_raw()])

    request = httpx_mock.get_request()
    assert request.headers["authorization"] == "Bearer segreto"


async def test_enrich_truncates_to_max_chars(httpx_mock: HTTPXMock) -> None:
    long_text = "x" * 20000
    httpx_mock.add_response(url="https://r.jina.ai/https://example.com/a", text=long_text)
    async with HttpClient() as http:
        reader = JinaReader(http, api_key="k", max_chars=1000)
        items, _, _ = await reader.enrich([mk_raw()])

    assert len(items[0].content) == 1000
