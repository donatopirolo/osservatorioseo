"""Normalizzazione URL/titoli + dedup."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from rapidfuzz import fuzz

from osservatorio_seo.models import AlsoIn, RawItem, Source

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


BYLINE_SUFFIX = re.compile(r"\s+via\s+@[\w.-]+(?:\s*,\s*@[\w.-]+)*\s*$", re.IGNORECASE)


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
        # Search Engine Journal appende la firma redazionale al titolo RSS
        # ("... via @sejournal, @MattGSouthern"): 691 titoli su 1936
        # nell'archivio. E' rumore per il lettore e, soprattutto, impedisce
        # di riconoscere la sindacazione: lo stesso pezzo di Kevin Indig sul
        # suo blog e su SEJ si fermava a ratio 73 solo per via del suffisso,
        # e usciva due volte. Senza, e' 100.
        title = BYLINE_SUFFIX.sub("", title)
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
                # studi diversi.
                if fuzz.ratio(item.title.lower(), existing.title.lower()) >= self._title_threshold:
                    duplicate_idx = i
                    break
            if duplicate_idx is None:
                kept.append(item)
                continue
            kept[duplicate_idx] = self._merge(kept[duplicate_idx], item, sources)
        return kept

    def _merge(self, a: RawItem, b: RawItem, sources: dict[str, Source]) -> RawItem:
        """Fonde due item sullo stesso fatto: vince l'autorita' piu' alta.

        Il perdente non viene buttato: diventa una voce `also_in` sul
        vincitore, cosi' l'accorpamento aggiunge una fonte invece di
        perderla. E' la ragione per cui la soglia di somiglianza puo'
        stare a 75 senza rischi: nel caso peggiore la pagina mostra un
        "Anche su" di troppo, mai una notizia in meno.
        """
        winner, loser = (
            (a, b) if sources[a.source_id].authority >= sources[b.source_id].authority else (b, a)
        )
        also: list[AlsoIn] = []
        known = {winner.url}
        # Le catene di accorpamenti sono transitive: A assorbe B, poi C
        # assorbe A e deve ereditare anche B.
        for entry in [*winner.also_in, *loser.also_in]:
            if entry.url not in known and entry.source_id != winner.source_id:
                also.append(entry)
                known.add(entry.url)
        if loser.url not in known and loser.source_id != winner.source_id:
            also.append(
                AlsoIn(
                    source_id=loser.source_id,
                    source_name=sources[loser.source_id].name,
                    url=loser.url,
                )
            )
        return winner.model_copy(update={"also_in": also})
