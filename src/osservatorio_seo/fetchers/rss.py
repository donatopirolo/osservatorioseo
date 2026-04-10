"""RSS/Atom fetcher via feedparser."""
from __future__ import annotations

from datetime import UTC, datetime
from time import mktime

import feedparser

from osservatorio_seo.http_client import HttpClient
from osservatorio_seo.models import RawItem, Source


class RSSFetcher:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def fetch(self, source: Source) -> list[RawItem]:
        if not source.feed_url:
            return []
        resp = await self._http.get(source.feed_url)
        parsed = feedparser.parse(resp.text)
        items: list[RawItem] = []
        for entry in parsed.entries:
            title = entry.get("title", "").strip()
            url = entry.get("link", "").strip()
            if not title or not url:
                continue
            content = self._extract_content(entry)
            published = self._extract_date(entry)
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
    def _extract_content(entry) -> str:
        for key in ("content", "summary", "description"):
            val = entry.get(key)
            if not val:
                continue
            if isinstance(val, list) and val:
                return str(val[0].get("value", "")).strip()
            return str(val).strip()
        return ""

    @staticmethod
    def _extract_date(entry) -> datetime:
        for key in ("published_parsed", "updated_parsed"):
            struct = entry.get(key)
            if struct:
                return datetime.fromtimestamp(mktime(struct), tz=UTC)
        return datetime.now(UTC)
