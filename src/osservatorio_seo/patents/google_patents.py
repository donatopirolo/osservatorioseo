"""Client minimale per Google Patents: scheda del brevetto e ricerca.

Google Patents non ha un'API ufficiale e risponde con la pagina "Sorry..."
(HTTP 503 o 429) a chi fa troppe richieste ravvicinate. Il client quindi:

- aspetta ``delay_s`` secondi tra una richiesta e l'altra;
- al primo blocco solleva :class:`PatentsBlockedError` invece di insistere:
  lo script chiamante salva quello che ha gia' fatto e chiude il run in modo
  pulito, il prossimo run riprende da li'. Non proviamo ad aggirare il blocco.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import date
from typing import Any
from urllib.parse import quote

import httpx
from selectolax.parser import HTMLParser

from osservatorio_seo.patents.models import FamilyMember, PatentDoc

logger = logging.getLogger(__name__)

BASE_URL = "https://patents.google.com"
USER_AGENT = "Mozilla/5.0 (compatible; OsservatorioSEO/1.0; +https://osservatorioseo.pages.dev)"

# Tetto di sicurezza sulla descrizione: le piu' lunghe viste finora sono ~150k
# caratteri (~38k token), ben dentro il contesto del modello.
DESCRIPTION_MAX_CHARS = 250_000


class PatentsBlockedError(Exception):
    """Google Patents ha risposto con la pagina di blocco anti-bot."""


class PatentNotFoundError(Exception):
    pass


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_patent_page(number: str, html: str) -> PatentDoc:
    """Estrae un :class:`PatentDoc` dall'HTML di una pagina di Google Patents."""
    tree = HTMLParser(html)

    title_node = tree.css_first('span[itemprop="title"]') or tree.css_first('meta[name="DC.title"]')
    if title_node is None:
        raise PatentNotFoundError(f"{number}: titolo non trovato nella pagina")
    title = _clean(
        title_node.attributes.get("content") or ""
        if title_node.tag == "meta"
        else title_node.text()
    )

    abstract_node = tree.css_first('section[itemprop="abstract"] div.abstract') or tree.css_first(
        'section[itemprop="abstract"]'
    )
    abstract = _clean(abstract_node.text()) if abstract_node else ""
    abstract = re.sub(r"^Abstract\s*", "", abstract)

    claims: list[str] = []
    independent: list[str] = []
    for node in tree.css("div.claim[id]"):
        text = _clean(node.text(separator=" "))
        if not text:
            continue
        claims.append(text)
        # Una rivendicazione dipendente rimanda a un'altra con <claim-ref>; nei
        # brevetti piu' vecchi (es. US6285999B1) il rimando e' solo nel testo.
        is_dependent = node.css_first("claim-ref") is not None or re.search(
            r"\b(?:of|in|to|by) claims? \d+", text
        )
        if not is_dependent:
            independent.append(text)

    def texts(selector: str) -> list[str]:
        out: list[str] = []
        for n in tree.css(selector):
            t = _clean(n.text())
            if t and t not in out:
                out.append(t)
        return out

    def first_text(selector: str) -> str | None:
        n = tree.css_first(selector)
        return _clean(n.text()) if n else None

    family: list[FamilyMember] = []
    seen_family: set[str] = {number}
    # Prima figli e genitori, che portano il tipo di relazione (Continuation,
    # Division...); priorityApps ripete le stesse pubblicazioni senza relazione.
    directions = {
        "childApps": "child",
        "parentApps": "parent",
        "priorityApps": "priority",
    }
    for prop, direction in directions.items():
        for row in tree.css(f'tr[itemprop="{prop}"]'):
            pub = row.css_first('[itemprop="representativePublication"]')
            if pub is None:
                continue
            num = _clean(pub.text())
            if not num or num in seen_family:
                continue
            seen_family.add(num)
            relation = row.css_first('[itemprop="relationType"]')
            title_cell = row.css_first('td[itemprop="title"]')
            family.append(
                FamilyMember(
                    number=num,
                    relation=_clean(relation.text()) if relation else None,
                    direction=direction,
                    title=_clean(title_cell.text()) if title_cell else None,
                )
            )

    # Codici CPC: Google Patents li mostra come alberi (G, G06, G06F, ...);
    # teniamo solo i codici completi (con la barra), che sono quelli utili.
    cpc = [c for c in texts('[itemprop="Code"]') if "/" in c]

    cited_by = len(tree.css('tr[itemprop="forwardReferencesOrig"]')) + len(
        tree.css('tr[itemprop="forwardReferencesFamily"]')
    )

    description_node = tree.css_first('section[itemprop="description"]')
    description = _clean(description_node.text(separator=" ")) if description_node else ""
    description = re.sub(r"^Description\s*", "", description)

    return PatentDoc(
        number=number,
        title=title,
        abstract=abstract,
        claims=claims,
        independent_claims=independent,
        assignees=texts('dd[itemprop="assigneeOriginal"]'),
        inventors=texts('dd[itemprop="inventor"]'),
        priority_date=_parse_date(first_text('[itemprop="priorityDate"]')),
        filing_date=_parse_date(first_text('[itemprop="filingDate"]')),
        publication_date=_parse_date(first_text('[itemprop="publicationDate"]')),
        status=first_text('span[itemprop="status"]') or first_text('[itemprop="status"]'),
        cpc_codes=cpc[:20],
        family=family,
        cited_by_count=cited_by,
        description=description[:DESCRIPTION_MAX_CHARS],
    )


def _strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return _clean(text.replace("&hellip;", "…").replace("&#39;", "'").replace("&amp;", "&"))


class GooglePatentsClient:
    def __init__(self, delay_s: float = 20.0, timeout_s: float = 30.0) -> None:
        self._delay_s = delay_s
        self._last_request: float | None = None
        self._client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=timeout_s,
            follow_redirects=True,
        )

    async def __aenter__(self) -> GooglePatentsClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._client.aclose()

    async def _get(self, url: str) -> httpx.Response:
        if self._last_request is not None:
            wait = self._delay_s - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
        self._last_request = time.monotonic()
        resp = await self._client.get(url)
        if resp.status_code in (429, 503) or "<title>Sorry...</title>" in resp.text[:2000]:
            raise PatentsBlockedError(
                f"Google Patents ha bloccato la richiesta ({resp.status_code})"
            )
        return resp

    async def fetch(self, number: str) -> PatentDoc:
        resp = await self._get(f"{BASE_URL}/patent/{number}/en")
        if resp.status_code == 404:
            raise PatentNotFoundError(number)
        resp.raise_for_status()
        return parse_patent_page(number, resp.text)

    async def search(self, query: str) -> list[dict[str, Any]]:
        """Esegue una ricerca e ritorna ``[{number, title, publication_date, snippet}]``.

        ``query`` e' la query string di patents.google.com, la stessa che si
        vede nella barra degli indirizzi dopo il ``?``, es.
        ``q=(ranking)&assignee=Google+Llc&country=US&after=publication:20260101``.
        """
        resp = await self._get(f"{BASE_URL}/xhr/query?url={quote(query, safe='')}&exp=")
        resp.raise_for_status()
        results = resp.json().get("results", {})
        out: list[dict[str, Any]] = []
        for cluster in results.get("cluster", []):
            for r in cluster.get("result", []):
                p = r.get("patent", {})
                number = p.get("publication_number")
                if not number:
                    continue
                out.append(
                    {
                        "number": number,
                        "title": _strip_tags(p.get("title", "")),
                        "publication_date": _parse_date(p.get("publication_date")),
                        "assignee": _strip_tags(p.get("assignee", "")),
                        "snippet": _strip_tags(p.get("snippet", "")),
                    }
                )
        return out
