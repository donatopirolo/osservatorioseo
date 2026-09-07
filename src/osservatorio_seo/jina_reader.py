"""Arricchimento del content via Jina Reader (r.jina.ai).

Le fonti RSS attive espongono spesso solo un excerpt breve dell'articolo
(vedi ``RSSFetcher._extract_content``: prende ``summary``/``description``
del feed, non il testo integrale della pagina). Il summarizer lavora quindi
su poche centinaia di caratteri invece che sull'articolo vero. Jina Reader
scarica la pagina e ne restituisce il contenuto pulito in testo semplice
(gestisce anche il rendering JS), dando al summarizer un content molto piu'
ricco per riassunti migliori.

Stadio best-effort dopo la dedup del Normalizer, mai bloccante: se
``JINA_API_KEY`` manca, se la richiesta fallisce (timeout, 4xx/5xx) o se il
testo ottenuto non e' piu' ricco dell'originale, l'item prosegue con il
content del fetcher originale.
"""

from __future__ import annotations

import asyncio
import logging

from osservatorio_seo.http_client import HttpClient
from osservatorio_seo.models import RawItem

logger = logging.getLogger(__name__)

JINA_READER_BASE = "https://r.jina.ai/"


class JinaReader:
    def __init__(
        self,
        http: HttpClient,
        api_key: str | None,
        min_gain_chars: int = 500,
        max_chars: int = 12000,
    ) -> None:
        self._http = http
        self._api_key = api_key
        self._min_gain_chars = min_gain_chars
        self._max_chars = max_chars

    async def enrich(self, items: list[RawItem]) -> tuple[list[RawItem], int, int]:
        """Arricchisce ``items`` dove Jina Reader migliora davvero il content.

        Ritorna ``(items arricchiti dove possibile, tentativi, falliti)``.
        Senza ``api_key`` e' un no-op immediato (nessuna chiamata HTTP).
        """
        if not self._api_key or not items:
            return items, 0, 0

        texts = await asyncio.gather(*(self._fetch_text(item.url) for item in items))

        enriched: list[RawItem] = []
        failed = 0
        for item, text in zip(items, texts, strict=True):
            if text is None:
                enriched.append(item)
                failed += 1
            elif len(text) < len(item.content) + self._min_gain_chars:
                # Non abbastanza guadagno rispetto all'excerpt originale:
                # non vale il rischio di sostituire con testo di boilerplate
                # (cookie banner, nav) mal estratto.
                enriched.append(item)
            else:
                enriched.append(item.model_copy(update={"content": text[: self._max_chars]}))
        return enriched, len(items), failed

    async def _fetch_text(self, url: str) -> str | None:
        try:
            resp = await self._http.get(
                JINA_READER_BASE + url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "X-Return-Format": "text",
                },
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("jina reader failed for %s: %s", url, e)
            return None
        return resp.text.strip()
