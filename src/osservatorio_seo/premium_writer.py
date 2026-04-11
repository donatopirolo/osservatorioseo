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

import httpx

from osservatorio_seo.models import DeepAnalysis, FAQEntry, Item

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
- ⚠️ MIX TONE: alterna tre registri in base al contesto:
  1. MISURATO — quando descrivi i fatti (cosa Google/fonte ha detto)
  2. ANALITICO — quando spieghi le implicazioni tecniche/di ranking
  3. OPINION FORTE — nel commentary finale, se c'è motivo di dissentire, \
     avvertire, o suggerire un'azione controcorrente, DILLO chiaramente. \
     Esempi di cose da dire se appropriato: "non abboccate al hype", \
     "questo è marketing di Google, non un cambio reale", "fermatevi prima \
     di seguire questa best practice se siete in questa situazione".

SCHEMA JSON DI OUTPUT (NESSUN CAMPO IN PIÙ, NESSUN CAMPO IN MENO):

{{
  "detailed_description": "string, 500-700 parole, corpo editoriale dell'articolo. \
Va scritto come un articleBody SEO: paragrafi in testo continuo (no heading \
markdown, no bullet), ben argomentati, con almeno un riferimento numerico o \
fattuale preso dalla notizia. Prima riga: un lead forte che sintetizza l'impatto. \
NON ripetere il titolo. NON iniziare con 'Google ha annunciato'. Inizia con \
l'INSIGHT, non con la cronaca.",
  "implications": [
    "3-5 bullet, ciascuno 1-2 frasi. Conseguenze OPERATIVE dirette per un SEO. \
Non 'potrebbe avere impatto', ma 'cosa cambia concretamente per te'. Se non c'è \
impatto operativo diretto, dillo."
  ],
  "examples": [
    "3 esempi concreti. Ciascuno è UN paragrafo di 2-4 frasi. Se possibile \
uno 'cosa fare', uno 'cosa evitare', uno 'caso di studio / scenario tipo'."
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
risposta diretta anche se breve."
    }}
  ],
  "editorial_commentary": "string, 100-200 parole di commento editoriale in prima \
persona plurale ('noi di Osservatorio SEO pensiamo'). È QUI che il tono può \
diventare OPINION FORTE se il contesto lo giustifica. Se non c'è motivo di \
dissentire, resta ANALITICO ma mai generico. Firma implicita: 'la redazione'."
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
