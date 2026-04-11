"""Premium writer: genera deep analysis editoriale per item 5-stelle.

Usa un modello premium (default Claude Sonnet 4.5 via OpenRouter) per
produrre in un singolo round:

- ``detailed_description``: 500-700 parole, corpo SEO dell'articolo
- ``implications``: 3-5 conseguenze operative concrete per un SEO
- ``examples``: 3 esempi concreti (cosa fare, cosa evitare, case)
- ``testing_steps``: 3-6 step testabili per verificare l'impatto
- ``faqs``: 4-6 domande/risposte in stile Google FAQ guidelines
- ``editorial_commentary``: commento editoriale "mix tone"
  (misurato / analitico / opinion forte a seconda del contesto)

L'output viene salvato come :class:`DeepAnalysis` e attaccato all'``Item``.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from datetime import UTC, datetime

import httpx

from osservatorio_seo.models import (
    DeepAnalysis,
    FAQEntry,
    Item,
    Pillar,
    PillarTakeaway,
)

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Rough pricing (USD per 1M token) — same conversion rate as summarizer
PREMIUM_PRICING: dict[str, tuple[float, float]] = {
    "anthropic/claude-sonnet-4-5": (3.0, 15.0),
    "anthropic/claude-opus-4-6": (15.0, 75.0),
    "anthropic/claude-haiku-4.5": (1.0, 5.0),
}
USD_TO_EUR = 0.92


PROMPT = """Sei un SEO senior italiano con 15 anni di esperienza che scrive per un \
hub editoriale di nicchia (Osservatorio SEO). Il lettore è un professionista SEO \
(agency, in-house, consulente freelance). NON è un principiante. Vuole capire cosa \
fare DOMANI e perché.

Ti do il titolo, il summary breve, l'URL originale e il contenuto di una notizia \
giudicata critica (5/5). Devi produrre una deep analysis editoriale in italiano, \
in un singolo JSON valido.

REGOLE DI TONO (IMPORTANTI):
- Niente hype, niente clickbait, niente "scopri", "incredibile", "rivoluzione".
- Niente filler tipo "in un mondo in continua evoluzione".
- Asciutto, operativo, basato sui fatti della notizia.
- ⚠️ VIETATISSIMO usare la prima persona plurale editoriale. NON scrivere MAI:
  "noi di Osservatorio SEO", "noi pensiamo", "il nostro consiglio",
  "la nostra opinione", "crediamo che", "ci aspettiamo". NO firme tipo
  "la redazione". Scrivi in forma IMPERSONALE (terza persona) oppure in
  SECONDA PERSONA diretta rivolta al lettore ("se gestisci un sito di
  ricette, questo update ti impatta perché…"). Il testo non deve contenere
  mai le parole "noi", "nostro/a/i/e", "pensiamo", "crediamo".
- ⚠️ MIX TONE: alterna tre registri in base al contesto:
  1. MISURATO — quando descrivi i fatti (cosa Google/fonte ha detto)
  2. ANALITICO — quando spieghi le implicazioni tecniche/di ranking
  3. OPINION FORTE — nel commentary finale, se c'è motivo di dissentire, \
     avvertire, o suggerire un'azione controcorrente, DILLO chiaramente \
     sempre in forma impersonale o in seconda persona. Esempi validi: \
     "non abboccare al hype", "questo è marketing di Google, non un cambio \
     reale", "fermati prima di seguire questa best practice se ti trovi in \
     questa situazione", "chi ha costruito traffico su questa pratica \
     dovrebbe preoccuparsi". ESEMPI VIETATI: "noi pensiamo che…", \
     "il nostro consiglio è…".

REGOLE DI LEGGIBILITÀ:
- detailed_description va scritta in PARAGRAFI BREVI, da 2-4 frasi ciascuno \
(massimo ~60 parole per paragrafo). Separa ogni paragrafo con ESATTAMENTE due \
newline "\\n\\n". Evita muri di testo monolitici.
- editorial_commentary: 100-200 parole spezzate in 2-3 paragrafi brevi \
separati da "\\n\\n".

SCHEMA JSON DI OUTPUT (NESSUN CAMPO IN PIÙ, NESSUN CAMPO IN MENO):

{{
  "detailed_description": "string, 500-700 parole, corpo editoriale dell'articolo. \
Va scritto come un articleBody SEO in PARAGRAFI BREVI (2-4 frasi, max ~60 parole \
ciascuno), separati da \\n\\n. Niente heading markdown, niente bullet. \
Ben argomentato, con almeno un riferimento numerico o fattuale preso dalla notizia. \
Primo paragrafo: un lead forte che sintetizza l'impatto. NON ripetere il titolo. \
NON iniziare con 'Google ha annunciato'. Inizia con l'INSIGHT, non con la cronaca. \
VIETATO 'noi' / 'nostro' in qualsiasi forma.",
  "implications": [
    "3-5 bullet, ciascuno 1-2 frasi. Conseguenze OPERATIVE dirette per un SEO. \
Non 'potrebbe avere impatto', ma 'cosa cambia concretamente'. Se non c'è \
impatto operativo diretto, dillo. Forma impersonale o seconda persona."
  ],
  "examples": [
    "3 esempi concreti. Ciascuno è UN paragrafo di 2-4 frasi. Se possibile \
uno 'cosa fare', uno 'cosa evitare', uno 'caso di studio / scenario tipo'. \
Forma impersonale o seconda persona."
  ],
  "testing_steps": [
    "3-6 step actionable testabili per verificare l'impatto sul proprio sito. \
Ciascuno una frase imperativa. Es: 'Apri GSC → Prestazioni e filtra per query branded'."
  ],
  "faqs": [
    {{
      "question": "Una domanda reale che un SEO si farebbe, non marketing fluff",
      "answer": "Risposta sintetica (40-80 parole) e specifica, seguendo le \
Google FAQ guidelines: niente frasi vuote, niente rinvii a 'dipende dal caso', \
risposta diretta anche se breve. Forma impersonale o seconda persona."
    }}
  ],
  "editorial_commentary": "string, 100-200 parole di commento editoriale in \
forma IMPERSONALE o in SECONDA PERSONA diretta, spezzate in 2-3 paragrafi \
brevi separati da \\n\\n. È QUI che il tono può diventare OPINION FORTE se il \
contesto lo giustifica. Se non c'è motivo di dissentire, resta ANALITICO ma \
mai generico. VIETATO 'noi', 'nostro', firme tipo 'la redazione'."
}}

Il JSON deve essere SEMPRE valido e parsabile. Non includere codefence markdown, \
non includere testo prima o dopo il JSON.

--- NOTIZIA ---

Titolo: {title}
Fonte: {source_name}
Pubblicato: {published_at}
URL originale: {url}
Category: {category}
Tags: {tags}

Summary breve (italiano, già tradotto):
{summary_it}

Contenuto originale (primi {content_chars} caratteri):
{content}
"""


PILLAR_PROMPT = """Sei un SEO senior italiano che scrive il dossier editoriale \
pillar di Osservatorio SEO sul tema "{tag_display}". Il lettore è un \
professionista SEO (agency, in-house, consultant) che cerca una vista \
d'insieme autorevole e operativa sul tema. NON è un principiante.

Devi produrre un dossier pillar strutturato in JSON. Usa TUTTI i fatti e le \
notizie incluse sotto come riferimenti cronologici per costruire una narrazione \
coerente. Il dossier NON è un riassunto degli item — è una visione editoriale \
che li contestualizza.

REGOLE DI TONO (VIETATISSIMO):
- VIETATO prima persona plurale: "noi di", "noi pensiamo", "il nostro consiglio", \
"la nostra opinione", "crediamo", "ci aspettiamo", firme "la redazione".
- Scrivi sempre in forma IMPERSONALE (terza persona) o SECONDA PERSONA diretta \
al lettore ("se gestisci un sito…", "chi lavora su…").
- Niente hype, niente clickbait, niente "scopri", "incredibile".
- Tono autorevole, analitico, operativo. Quando serve, opinion forte.

REGOLE DI LEGGIBILITÀ:
- intro_long, context_section, timeline_narrative, outlook: PARAGRAFI BREVI \
(2-4 frasi, max ~60 parole), separati da \\n\\n. No muri di testo.
- No heading markdown dentro questi campi. No bullet. Testo continuo strutturato \
in paragrafi.

SCHEMA JSON OBBLIGATORIO (nessun campo extra, nessun campo mancante):

{{
  "title_it": "Titolo H1 del dossier, 5-9 parole, no marketing, es. \
'Core Update: il dossier di Osservatorio SEO'. Non mettere punti finali.",
  "subtitle_it": "Sottotitolo 1 frase (~120 caratteri) che cattura il valore \
editoriale del dossier. Es: 'Cosa sono, come evolvono e cosa fare prima, durante \
e dopo un core update di Google.'",
  "intro_long": "800-1200 parole in paragrafi brevi separati da \\n\\n. \
È il lead del dossier: definisce il tema, spiega perché è critico per un SEO, \
posiziona il dossier rispetto alla letteratura esistente. Primo paragrafo = \
hook forte con un fatto specifico. NO 'in questo articolo vedremo'. Inizia \
con l'INSIGHT.",
  "context_section": "400-600 parole in paragrafi brevi. Contesto storico e \
tecnico: cosa è successo in passato, perché l'argomento è diventato rilevante, \
quali framework/pattern esistono per interpretarlo. Se applicabile, cita date \
e riferimenti specifici.",
  "timeline_narrative": "400-600 parole in paragrafi brevi. Narrazione \
cronologica basata SUGLI ITEM forniti sotto. Non elencarli: costruisci una \
storia. Cita i titoli degli item come riferimenti naturali nel testo quando \
rilevanti. Evidenzia pattern o discontinuità.",
  "takeaways": [
    {{
      "title": "Takeaway 1 (max 8 parole, imperativo o dichiarativo)",
      "body": "Corpo del takeaway, 40-80 parole, concreto e operativo. \
Impersonale o seconda persona."
    }}
  ],
  "outlook": "200-400 parole in paragrafi brevi. Prospettive future: cosa \
aspettarsi nei prossimi mesi, quali segnali monitorare, quali scenari sono \
plausibili. Tono analitico con eventuale opinion forte. Niente predizioni hype."
}}

La lista "takeaways" deve contenere ESATTAMENTE 5 takeaway. Il JSON deve essere \
valido, parsabile, senza codefence markdown, senza testo extra prima/dopo.

--- ITEM DI RIFERIMENTO (ordinati per data) ---

{items_block}
"""


class _TagDisplay:
    """Mapping tag → display italiano per prompt. Fallback: title case del tag."""

    _MAP = {
        "core_update": "Core Update di Google",
        "e_e_a_t": "E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness)",
        "googlebot": "Googlebot e crawling",
        "ai_overviews": "AI Overviews di Google",
        "llm_seo": "SEO per LLM e AI Search",
        "technical_seo": "SEO tecnico",
    }

    @classmethod
    def render(cls, tag: str) -> str:
        return cls._MAP.get(tag, tag.replace("_", " ").title())


class PremiumWriterError(Exception):
    pass


@dataclass
class _RawResult:
    parsed: dict[str, Any]
    model: str
    cost_eur: float


class PremiumWriter:
    """Genera DeepAnalysis usando un modello premium via OpenRouter."""

    def __init__(
        self,
        api_key: str,
        primary_model: str = "anthropic/claude-sonnet-4-5",
        fallback_models: list[str] | None = None,
        max_retries_per_model: int = 2,
    ) -> None:
        self._api_key = api_key
        self._primary = primary_model
        self._fallbacks = fallback_models or ["anthropic/claude-haiku-4.5"]
        self._max_retries = max_retries_per_model

    async def analyze(
        self,
        item: Item,
        raw_content: str | None = None,
    ) -> DeepAnalysis:
        """Produce DeepAnalysis per ``item``.

        ``raw_content`` è il testo originale dell'articolo (facoltativo).
        Se non disponibile, il prompt usa solo ``item.summary_it`` come base.
        """
        content = (raw_content or item.summary_it or "")[:6000]
        prompt = PROMPT.format(
            title=item.title_it,
            source_name=item.source.name,
            published_at=item.published_at.isoformat(),
            url=item.url,
            category=item.category,
            tags=", ".join(item.tags) or "—",
            summary_it=item.summary_it,
            content_chars=len(content),
            content=content,
        )
        result = await self._call_with_fallback(prompt)
        parsed = result.parsed
        faqs = [FAQEntry(question=f["question"], answer=f["answer"]) for f in parsed.get("faqs", [])]
        return DeepAnalysis(
            detailed_description=parsed["detailed_description"],
            implications=list(parsed.get("implications", []))[:6],
            examples=list(parsed.get("examples", []))[:4],
            testing_steps=list(parsed.get("testing_steps", []))[:8],
            faqs=faqs[:8],
            editorial_commentary=parsed["editorial_commentary"],
            premium_model_used=result.model,
            cost_eur=result.cost_eur,
        )

    async def write_pillar(self, tag: str, items: list[Item]) -> Pillar:
        """Genera un :class:`Pillar` dato un tag e la lista di item che lo riguardano.

        ``items`` va passato già filtrato e ordinato cronologicamente. Lo script
        chiamante è responsabile del filtro per tag.
        """
        if not items:
            raise PremiumWriterError("write_pillar requires at least 1 item")

        items_sorted = sorted(items, key=lambda i: i.published_at)
        items_block_lines = []
        for i, it in enumerate(items_sorted, start=1):
            published = it.published_at.strftime("%Y-%m-%d")
            items_block_lines.append(
                f"[{i}] {published} · {it.source.name} · importance={it.importance}\n"
                f"    Titolo: {it.title_it}\n"
                f"    URL: {it.url}\n"
                f"    Summary: {it.summary_it}\n"
            )
        items_block = "\n".join(items_block_lines)

        prompt = PILLAR_PROMPT.format(
            tag_display=_TagDisplay.render(tag),
            items_block=items_block,
        )
        result = await self._call_with_fallback(prompt)
        parsed = result.parsed

        takeaways = [
            PillarTakeaway(title=t["title"], body=t["body"])
            for t in parsed.get("takeaways", [])
        ]

        slug = tag.replace("_", "-")
        return Pillar(
            tag=tag,
            slug=slug,
            title_it=parsed["title_it"],
            subtitle_it=parsed["subtitle_it"],
            intro_long=parsed["intro_long"],
            context_section=parsed["context_section"],
            timeline_narrative=parsed["timeline_narrative"],
            takeaways=takeaways[:8],
            outlook=parsed["outlook"],
            item_refs=[i.id for i in items_sorted],
            generated_at=datetime.now(UTC),
            model_used=result.model,
            cost_eur=result.cost_eur,
        )

    async def _call_with_fallback(self, prompt: str) -> _RawResult:
        models = [self._primary, *self._fallbacks]
        last_error: Exception | None = None
        for model in models:
            try:
                return await self._call_model(model, prompt)
            except Exception as e:  # noqa: BLE001
                logger.warning("premium model %s failed: %s", model, e)
                last_error = e
        raise PremiumWriterError(f"all premium models failed: {last_error}")

    async def _call_model(self, model: str, prompt: str) -> _RawResult:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "HTTP-Referer": "https://github.com/osservatorioseo",
            "X-Title": "OsservatorioSEO",
            "Content-Type": "application/json",
        }
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
            "max_tokens": 4000,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            for attempt in range(self._max_retries):
                resp = await client.post(OPENROUTER_URL, headers=headers, json=body)
                if resp.status_code >= 500:
                    if attempt < self._max_retries - 1:
                        continue
                    raise PremiumWriterError(f"server error {resp.status_code}")
                resp.raise_for_status()
                data = resp.json()
                try:
                    content = data["choices"][0]["message"]["content"]
                    parsed = _parse_json_loose(content)
                except (KeyError, json.JSONDecodeError, ValueError) as e:
                    if attempt < self._max_retries - 1:
                        logger.warning("malformed JSON from %s, retrying: %s", model, e)
                        continue
                    raise PremiumWriterError(f"malformed JSON from {model}") from e
                usage = data.get("usage", {}) or {}
                cost = self._compute_cost(
                    model,
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                )
                return _RawResult(parsed=parsed, model=model, cost_eur=cost)
            raise PremiumWriterError("retries exhausted")

    @staticmethod
    def _compute_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
        in_price, out_price = PREMIUM_PRICING.get(model, (0.0, 0.0))
        usd = (prompt_tokens / 1_000_000) * in_price + (completion_tokens / 1_000_000) * out_price
        return usd * USD_TO_EUR


def _parse_json_loose(content: str) -> dict[str, Any]:
    """Parse JSON tollerando testo extra intorno al blocco JSON.

    Stessa logica del summarizer: alcuni modelli aggiungono testo o
    codefence intorno al JSON, quindi estraiamo il primo blocco bilanciato.
    """
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    stripped = re.sub(r"```(?:json)?\s*", "", content)
    stripped = stripped.replace("```", "")
    try:
        return json.loads(stripped.strip())
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    if start == -1:
        raise ValueError("no JSON object found in response")
    depth = 0
    for i, ch in enumerate(stripped[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(stripped[start : i + 1])
    raise ValueError("unbalanced JSON object in response")
