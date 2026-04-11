"""Ranker: scoring e top-10."""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import NamedTuple

from osservatorio_seo.models import Item

CATEGORY_BONUS: dict[str, int] = {
    "google_updates": 5,
    "google_docs_change": 10,
    "ai_models": 3,
}


class RankedOutput(NamedTuple):
    top10: list[str]
    categories: dict[str, list[str]]


class Ranker:
    def rank(self, items: list[Item]) -> RankedOutput:
        scored = [(item, self._score(item)) for item in items]
        scored.sort(key=lambda t: t[1], reverse=True)

        top10 = [item.id for item, _ in scored[:10]]

        by_cat: dict[str, list[str]] = defaultdict(list)
        for item, _ in scored:
            by_cat[item.category].append(item.id)

        return RankedOutput(top10=top10, categories=dict(by_cat))

    @staticmethod
    def _score(item: Item) -> int:
        now = datetime.now(UTC)
        age_hours = (now - item.published_at).total_seconds() / 3600
        freshness = 5 if age_hours < 6 else (2 if age_hours < 24 else 0)
        doc_bonus = 20 if item.is_doc_change else 0
        cat_bonus = CATEGORY_BONUS.get(item.category, 0)
        return (
            item.importance * 10
            + item.source.authority
            + freshness
            + doc_bonus
            + cat_bonus
        )
