"""Playwright-based fetcher per siti con anti-bot (X, LinkedIn)."""

from __future__ import annotations

import random
import re
from datetime import UTC, datetime
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from osservatorio_seo.http_client import BROWSER_USER_AGENTS
from osservatorio_seo.models import RawItem, Source

# Twitter/X snowflake epoch: 2010-11-04 01:42:54.657 UTC
TWITTER_EPOCH_MS = 1288834974657
_STATUS_ID_RE = re.compile(r"/status/(\d+)")


class PlaywrightFetcher:
    def __init__(self, timeout_s: int = 30) -> None:
        self._timeout_ms = timeout_s * 1000

    async def fetch(self, source: Source) -> list[RawItem]:
        if not source.target_url or not source.selectors:
            return []
        html = await self._render_page(source.target_url)
        return self._parse_html(html, source)

    async def _render_page(self, url: str) -> str:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    user_agent=random.choice(BROWSER_USER_AGENTS),
                    viewport={"width": 1280, "height": 800},
                    locale="en-US",
                )
                page = await context.new_page()
                await page.goto(url, timeout=self._timeout_ms, wait_until="domcontentloaded")
                await page.wait_for_timeout(2500)  # let JS render
                return await page.content()
            finally:
                await browser.close()

    def _parse_html(self, html: str, source: Source) -> list[RawItem]:
        sel = source.selectors or {}
        tree = HTMLParser(html)
        post_nodes = tree.css(sel.get("post", "article"))
        items: list[RawItem] = []
        for node in post_nodes[:20]:  # limita rumore
            text_node = node.css_first(sel.get("text", ""))
            link_node = node.css_first(sel.get("link", "a"))
            if not text_node or not link_node:
                continue
            text = text_node.text(strip=True)
            href = link_node.attributes.get("href", "") or ""
            if not text or not href:
                continue
            url = urljoin(source.target_url or "", href)

            # Data affidabile obbligatoria: se nessuna fonte la fornisce, skippiamo
            # l'item. Meglio nascondere una notizia che pubblicarla con data sbagliata.
            published = self._extract_date(node, url)
            if published is None:
                continue

            title = text[:120] + ("..." if len(text) > 120 else "")
            items.append(
                RawItem(
                    title=title,
                    url=url,
                    source_id=source.id,
                    published_at=published,
                    content=text,
                )
            )
        return items

    @staticmethod
    def _extract_date(node, url: str) -> datetime | None:
        """Estrae la data di pubblicazione del post.

        Ordine di priorità:
        1. Elemento ``<time datetime="ISO">`` dentro il nodo articolo
        2. Decodifica dello snowflake Twitter/X dall'URL ``/status/<id>``
        3. None (fallisce) → il chiamante skippa l'item
        """
        time_node = node.css_first("time")
        if time_node:
            dt_attr = time_node.attributes.get("datetime") or ""
            if dt_attr:
                try:
                    parsed = datetime.fromisoformat(dt_attr.replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=UTC)
                    return parsed
                except ValueError:
                    pass

        match = _STATUS_ID_RE.search(url)
        if match:
            try:
                tweet_id = int(match.group(1))
                ms = (tweet_id >> 22) + TWITTER_EPOCH_MS
                return datetime.fromtimestamp(ms / 1000, tz=UTC)
            except (ValueError, OSError, OverflowError):
                pass

        return None
