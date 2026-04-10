"""HTTP client async con UA rotation, rate limiting, retry."""
from __future__ import annotations

import asyncio
import random
from collections import defaultdict
from types import TracebackType
from urllib.parse import urlparse

import httpx

BROWSER_USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36",
]


class HttpClient:
    """Async HTTP client con limiti per host e retry.

    - Ruota User-Agent browser-like
    - Max N concurrent per host (default 3)
    - Delay 1-2s + jitter tra richieste sequenziali sullo stesso host
    - Retry 2x su 5xx e timeout con exponential backoff
    """

    def __init__(
        self,
        max_concurrent_per_host: int = 3,
        timeout_s: int = 15,
        max_retries: int = 3,
    ) -> None:
        self.max_concurrent_per_host = max_concurrent_per_host
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(
            timeout=timeout_s,
            follow_redirects=True,
            http2=False,
        )
        self._host_semaphores: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(max_concurrent_per_host)
        )
        self._host_last_request: dict[str, float] = {}
        self._host_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def __aenter__(self) -> HttpClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self._client.aclose()

    async def get(self, url: str, **kwargs) -> httpx.Response:
        host = urlparse(url).netloc
        headers = {
            "User-Agent": random.choice(BROWSER_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,it;q=0.8",
            **kwargs.pop("headers", {}),
        }
        async with self._host_semaphores[host]:
            await self._rate_limit_per_host(host)
            return await self._get_with_retry(url, headers, **kwargs)

    async def _rate_limit_per_host(self, host: str) -> None:
        async with self._host_locks[host]:
            last = self._host_last_request.get(host, 0.0)
            now = asyncio.get_event_loop().time()
            min_delay = 1.0 + random.uniform(0.0, 1.0)
            wait = max(0.0, last + min_delay - now)
            if wait > 0:
                await asyncio.sleep(wait)
            self._host_last_request[host] = asyncio.get_event_loop().time()

    async def _get_with_retry(
        self, url: str, headers: dict, **kwargs
    ) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = await self._client.get(url, headers=headers, **kwargs)
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"server {resp.status_code}", request=resp.request, response=resp
                    )
                return resp
            except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
                last_exc = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2**attempt + random.uniform(0.0, 0.5))
        raise RuntimeError(f"max retries exceeded for {url}: {last_exc}")
