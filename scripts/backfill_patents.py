#!/usr/bin/env python3
"""Classifica in blocco i candidati di un recupero storico della sezione Brevetti.

La discovery giornaliera guarda solo le pubblicazioni recenti. Per recuperare
i brevetti storici si raccolgono a mano i risultati di ricerca di Google
Patents (es. da un browser, senza limiti di data) in un JSON:

    [{"number", "title", "snippet", "assignee", ...}, ...]

Questo script li fa valutare al classificatore (stesso prompt della
discovery) e scrive due cose:

- ``--out``: i candidati con voto e filone, ordinati per voto;
- in ``data/state/patents_discovery.json`` gli scartati (voto sotto
  ``min_relevance``), cosi' la discovery giornaliera non li riesamina.

I brevetti accettati vanno poi scaricati (pagine salvate) e analizzati con
``update_patents.py --from-html``.

Usage:
    uv run python scripts/backfill_patents.py candidates.json --out scored.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from update_patents import CLASSIFIER_MODEL, CONFIG_PATH, load_state, save_state  # noqa: E402

from osservatorio_seo.patents.writer import classify  # noqa: E402
from osservatorio_seo.premium_writer import PremiumWriter  # noqa: E402

CONCURRENCY = 8


async def main() -> int:
    parser = argparse.ArgumentParser(description="Classifica i candidati di un backfill.")
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERRORE: OPENROUTER_API_KEY non impostata")
        return 1

    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    min_relevance = int(cfg["discovery"]["min_relevance"])
    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    classifier = PremiumWriter(api_key=api_key, primary_model=CLASSIFIER_MODEL, fallback_models=[])
    sem = asyncio.Semaphore(CONCURRENCY)
    total_cost = 0.0

    async def one(c: dict) -> dict:
        nonlocal total_cost
        async with sem:
            try:
                r = await classify(
                    classifier,
                    number=c["number"],
                    title=c["title"],
                    abstract=c.get("snippet", ""),
                    assignees=c.get("assignee", ""),
                    cpc="",
                )
            except Exception as e:  # noqa: BLE001
                print(f"  WARN {c['number']}: {e}")
                return {**c, "seo_relevance": None}
            total_cost += r.cost_eur
            return {**c, "seo_relevance": r.seo_relevance, "theme": r.theme, "reason": r.reason}

    scored = await asyncio.gather(*(one(c) for c in candidates))
    scored.sort(key=lambda c: -(c["seo_relevance"] or 0))
    args.out.write_text(json.dumps(scored, ensure_ascii=False, indent=1), encoding="utf-8")

    state = load_state()
    today = datetime.now(UTC).date().isoformat()
    for c in scored:
        if c["seo_relevance"] is not None and c["seo_relevance"] < min_relevance:
            state["rejected"][c["number"]] = {
                "title": c["title"],
                "seo_relevance": c["seo_relevance"],
                "reason": c["reason"],
                "checked_at": today,
            }
    save_state(state)

    by_score: dict[object, int] = {}
    for c in scored:
        by_score[c["seo_relevance"]] = by_score.get(c["seo_relevance"], 0) + 1
    accepted = sum(1 for c in scored if (c["seo_relevance"] or 0) >= min_relevance)
    print(f"Classificati {len(scored)}: {by_score} — accettati (>= {min_relevance}): {accepted}")
    print(f"Costo classificazione: €{total_cost:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
