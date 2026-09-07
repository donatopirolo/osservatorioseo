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
            # Il filtro sul contenuto corto puo' essere disattivato
            # (min_content_chars=0) quando a valle c'e' Jina Reader: alcune
            # fonti espongono un feed senza testo (Moz e Hugging Face: 10 su
            # 10 e 859 su 859 senza contenuto) e scartarle qui significa non
            # dare mai a Jina la possibilita' di recuperarle. Il filtro viene
            # riapplicato dopo l'arricchimento, in pipeline.
            if self._min_content_chars and len(item.content) < self._min_content_chars:
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
                # Solo ratio: confronto sulla formulazione intera.
                #
                # NON usare token_set_ratio: restituisce 100 quando un titolo e'
                # sottoinsieme dell'altro, e sui titoli reali dell'archivio
                # produce 3 falsi positivi su 5 collassi (verificato il
                # 2026-09-06 su 155 giorni). Collasserebbe fra l'altro
                # "...in Google AI Overviews" con "...in Grok", che sono due
                # studi diversi. I duplicati veri hanno titoli diversi per
                # costruzione: la strada e' la pagina-evento, non una soglia
                # piu' aggressiva. Vedi tests/test_normalizer.py.
                if fuzz.ratio(item.title.lower(), existing.title.lower()) >= self._title_threshold:
                    duplicate_idx = i
                    break
            if duplicate_idx is None:
                kept.append(item)
                continue
            existing = kept[duplicate_idx]
            if sources[item.source_id].authority > sources[existing.source_id].authority:
                kept[duplicate_idx] = item
        return kept
