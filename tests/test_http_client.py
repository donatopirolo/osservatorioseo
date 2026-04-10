# tests/test_http_client.py
import pytest
from pytest_httpx import HTTPXMock

from osservatorio_seo.http_client import BROWSER_USER_AGENTS, HttpClient


async def test_get_success(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://example.com/a", text="hello")
    async with HttpClient() as client:
        resp = await client.get("https://example.com/a")
        assert resp.status_code == 200
        assert resp.text == "hello"


async def test_user_agent_is_browser_like(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://example.com/a", text="x")
    async with HttpClient() as client:
        await client.get("https://example.com/a")
    request = httpx_mock.get_request()
    ua = request.headers["user-agent"]
    assert ua in BROWSER_USER_AGENTS
    assert "bot" not in ua.lower()


async def test_retry_on_500(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://example.com/a", status_code=500)
    httpx_mock.add_response(url="https://example.com/a", status_code=500)
    httpx_mock.add_response(url="https://example.com/a", status_code=200, text="ok")
    async with HttpClient() as client:
        resp = await client.get("https://example.com/a")
        assert resp.status_code == 200


async def test_retry_gives_up_after_max(httpx_mock: HTTPXMock) -> None:
    for _ in range(3):
        httpx_mock.add_response(url="https://example.com/a", status_code=500)
    async with HttpClient() as client:
        with pytest.raises(RuntimeError, match="max retries"):
            await client.get("https://example.com/a")
