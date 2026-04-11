"""Normalizzazione URL/titoli + dedup."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from rapidfuzz import fuzz

from osservatorio_seo.models import RawItem, Source

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "igshid",
}


class Normalizer:
    def __init__(
        self,
        max_age_hours: int = 24,
        min_content_chars: int = 20,
        title_similarity_threshold: int = 85,
    ) -> None:
        self._max_age = timedelta(hours=max_age_hours)
        self._min_content_chars = min_content_chars
        self._title_threshold = title_similarity_threshold

    def normalize(self, raw_items: list[RawItem], sources: dict[str, Source]) -> list[RawItem]:
        cleaned: list[RawItem] = []
        now = datetime.now(UTC)
        for item in raw_items:
            if len(item.content) < self._min_content_chars:
                continue
            if now - item.published_at > self._max_age:
                continue
            cleaned.append(
                item.model_copy(
                    update={
                        "url": self._canonical_url(item.url),
                        "title": self._clean_title(item.title),
                    }
                )
            )

        deduped = self._dedup_by_url(cleaned, sources)
        deduped = self._dedup_by_title(deduped, sources)
        return deduped

    @staticmethod
    def _canonical_url(url: str) -> str:
        parsed = urlparse(url)
        query = [(k, v) for k, v in parse_qsl(parsed.query) if k not in TRACKING_PARAMS]
        path = parsed.path.rstrip("/") or "/"
        return urlunparse(parsed._replace(query=urlencode(query), path=path, fragment=""))

    @staticmethod
    def _clean_title(title: str) -> str:
        import html

        title = html.unescape(title)
        title = re.sub(r"\s+", " ", title).strip()
        return title

    def _dedup_by_url(self, items: list[RawItem], sources: dict[str, Source]) -> list[RawItem]:
        best: dict[str, RawItem] = {}
        for item in items:
            existing = best.get(item.url)
            if existing is None:
                best[item.url] = item
                continue
            if sources[item.source_id].authority > sources[existing.source_id].authority:
                best[item.url] = item
        return list(best.values())

    def _dedup_by_title(self, items: list[RawItem], sources: dict[str, Source]) -> list[RawItem]:
        kept: list[RawItem] = []
        for item in items:
            duplicate_idx: int | None = None
            for i, existing in enumerate(kept):
                score = fuzz.ratio(item.title.lower(), existing.title.lower())
                if score >= self._title_threshold:
                    duplicate_idx = i
                    break
            if duplicate_idx is None:
                kept.append(item)
                continue
            existing = kept[duplicate_idx]
            if sources[item.source_id].authority > sources[existing.source_id].authority:
                kept[duplicate_idx] = item
        return kept
