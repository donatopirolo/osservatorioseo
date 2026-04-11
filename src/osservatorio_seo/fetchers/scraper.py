"""Generic HTML scraper basato su CSS selector configurati."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urljoin

from dateutil import parser as date_parser
from selectolax.parser import HTMLParser

from osservatorio_seo.http_client import HttpClient
from osservatorio_seo.models import RawItem, Source


class ScraperFetcher:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def fetch(self, source: Source) -> list[RawItem]:
        if not source.target_url or not source.selectors:
            return []
        resp = await self._http.get(source.target_url)
        tree = HTMLParser(resp.text)
        sel = source.selectors

        articles = tree.css(sel.get("article", "article"))
        items: list[RawItem] = []
        for node in articles:
            title_sel = sel.get("title") or "h2"
            link_sel = sel.get("link")
            content_sel = sel.get("content") or None
            date_sel = sel.get("date") or "time"

            title_node = node.css_first(title_sel)
            # Empty string or missing link selector = the article node itself carries href
            link_node = node.css_first(link_sel) if link_sel else node
            content_node = node.css_first(content_sel) if content_sel else None
            date_node = node.css_first(date_sel)

            title = title_node.text(strip=True) if title_node else ""
            raw_link = ""
            if link_node:
                raw_link = link_node.attributes.get("href", "") or ""
            if not title or not raw_link:
                continue

            url = urljoin(source.target_url, raw_link)
            content = content_node.text(strip=True) if content_node else ""
            published = self._extract_date(date_node)

            items.append(
                RawItem(
                    title=title,
                    url=url,
                    source_id=source.id,
                    published_at=published,
                    content=content,
                )
            )
        return items

    @staticmethod
    def _extract_date(node) -> datetime:
        if not node:
            return datetime.now(UTC)
        dt_attr = node.attributes.get("datetime", "")
        if dt_attr:
            try:
                parsed = date_parser.isoparse(dt_attr)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                return parsed
            except (ValueError, TypeError):
                pass
        try:
            parsed = date_parser.parse(node.text(strip=True))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed
        except (ValueError, TypeError):
            return datetime.now(UTC)
