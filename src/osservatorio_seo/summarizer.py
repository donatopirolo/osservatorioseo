"""AI summarizer via OpenRouter con fallback chain."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, Field

from osservatorio_seo.models import CategoryId, RawItem, Source

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

ITEM_PROMPT = """Sei un analista SEO senior italiano. Devi riassumere una notizia \
per un hub giornaliero di SEO e AI. Il lettore è un professionista SEO.

Regole:
- Rispondi SEMPRE in JSON valido con lo schema esatto sotto
- summary_it: 2-4 frasi in italiano, niente hype, niente "scopri", niente "incredibile". \
Tono asciutto e informativo.
- Non ripetere il titolo nel summary.
- Se la notizia è marketing/PR vuoto, importance=1.
- category: scegli UNA tra [google_updates, ai_models, ai_overviews_llm_seo, \
technical_seo, content_eeat, tools_platforms, industry_news]
- tags: 1-4 tag snake_case in inglese
- importance: 1-5 (5 = core update / cambio di regole / release major)
- title_it: traduci il titolo in italiano naturale (non letterale)

Schema output:
{{"title_it": "string", "summary_it": "string", "category": "string", \
"tags": ["string"], "importance": int}}

Notizia:
Titolo: {title}
Fonte: {source_name} (autorevolezza {authority}/10, tipo {source_type})
Pubblicato: {published_at}
URL: {url}
Contenuto (primi 3000 caratteri):
{content}
"""

DOC_CHANGE_PROMPT = """Sei un analista SEO senior italiano. Una pagina ufficiale è \
stata modificata. Analizza SOLO il diff sotto e spiega in italiano cosa è cambiato \
e perché importa a un SEO.

Regole:
- JSON valido con schema sotto
- summary_it: 2-4 frasi. Dì CONCRETAMENTE cosa è stato aggiunto, rimosso, o \
riformulato. Non dire "sono stati fatti aggiornamenti".
- Se il cambio è solo cosmetico/stylistic, importance=1 e dillo.
- importance 5 = nuova regola o restrizione, cambio di policy, nuova feature documentata.

Schema:
{{"title_it": "string (inizia con ⚠️, max 80 char)", "summary_it": "string", \
"tags": ["string"], "importance": int}}

Pagina: {page_name}
URL: {page_url}
Diff unificato:
{diff}
"""


class AISummary(BaseModel):
    title_it: str
    summary_it: str
    category: CategoryId
    tags: list[str] = Field(default_factory=list, max_length=8)
    importance: int = Field(ge=1, le=5)
    model_used: str
    cost_eur: float


class DocChangeSummary(BaseModel):
    title_it: str
    summary_it: str
    tags: list[str] = Field(default_factory=list, max_length=8)
    importance: int = Field(ge=1, le=5)
    model_used: str
    cost_eur: float


class SummarizerError(Exception):
    pass


# Rough pricing per milione di token (input / output) in USD
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "google/gemini-2.0-flash": (0.075, 0.30),
    "anthropic/claude-haiku-4.5": (1.0, 5.0),
    "openai/gpt-5-mini": (0.25, 2.0),
}
USD_TO_EUR = 0.92


@dataclass
class _RawResult:
    parsed: dict[str, Any]
    model: str
    cost_eur: float


class Summarizer:
    def __init__(
        self,
        api_key: str,
        primary_model: str = "google/gemini-2.0-flash",
        fallback_models: list[str] | None = None,
        max_retries_per_model: int = 2,
    ) -> None:
        self._api_key = api_key
        self._primary = primary_model
        self._fallbacks = fallback_models or [
            "anthropic/claude-haiku-4.5",
            "openai/gpt-5-mini",
        ]
        self._max_retries = max_retries_per_model

    async def summarize_item(self, raw: RawItem, source: Source) -> AISummary:
        prompt = ITEM_PROMPT.format(
            title=raw.title,
            source_name=source.name,
            authority=source.authority,
            source_type=source.type,
            published_at=raw.published_at.isoformat(),
            url=raw.url,
            content=raw.content[:3000],
        )
        result = await self._call_with_fallback(prompt)
        return AISummary(
            model_used=result.model,
            cost_eur=result.cost_eur,
            **result.parsed,
        )

    async def summarize_doc_change(
        self, page_name: str, page_url: str, diff: str
    ) -> DocChangeSummary:
        prompt = DOC_CHANGE_PROMPT.format(
            page_name=page_name, page_url=page_url, diff=diff
        )
        result = await self._call_with_fallback(prompt)
        return DocChangeSummary(
            model_used=result.model,
            cost_eur=result.cost_eur,
            **result.parsed,
        )

    async def _call_with_fallback(self, prompt: str) -> _RawResult:
        models = [self._primary, *self._fallbacks]
        last_error: Exception | None = None
        for model in models:
            try:
                return await self._call_model(model, prompt)
            except Exception as e:  # noqa: BLE001
                logger.warning("model %s failed: %s", model, e)
                last_error = e
        raise SummarizerError(f"all models failed: {last_error}")

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
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            for attempt in range(self._max_retries):
                resp = await client.post(OPENROUTER_URL, headers=headers, json=body)
                if resp.status_code >= 500:
                    if attempt < self._max_retries - 1:
                        continue
                    raise SummarizerError(f"server error {resp.status_code}")
                resp.raise_for_status()
                data = resp.json()
                try:
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                except (KeyError, json.JSONDecodeError) as e:
                    if attempt < self._max_retries - 1:
                        logger.warning("malformed JSON from %s, retrying: %s", model, e)
                        continue
                    raise SummarizerError(f"malformed JSON from {model}") from e
                usage = data.get("usage", {}) or {}
                cost = self._compute_cost(
                    model,
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                )
                return _RawResult(parsed=parsed, model=model, cost_eur=cost)
            raise SummarizerError("retries exhausted")

    @staticmethod
    def _compute_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
        in_price, out_price = MODEL_PRICING.get(model, (0.0, 0.0))
        usd = (prompt_tokens / 1_000_000) * in_price + (
            completion_tokens / 1_000_000
        ) * out_price
        return usd * USD_TO_EUR
