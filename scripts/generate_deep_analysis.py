#!/usr/bin/env python3
"""Genera una DeepAnalysis per un singolo item dell'archivio.

Usage:
    .venv/bin/python scripts/generate_deep_analysis.py <archive_date> <item_index>

Esempio (prototipo su Core Update febbraio 2026):
    .venv/bin/python scripts/generate_deep_analysis.py 2026-02-05 0

Lo script:
1. Apre ``data/archive/<archive_date>.json``
2. Estrae l'item all'indice passato
3. Refetch del contenuto dall'URL originale (se fetch fallisce, usa summary_it)
4. Invoca ``PremiumWriter.analyze(item, raw_content)``
5. Scrive il risultato dentro l'item, salvando il file
6. Stampa un preview del contenuto generato

Richiede ``OPENROUTER_API_KEY`` in env.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import httpx
from selectolax.parser import HTMLParser

from osservatorio_seo.config import load_settings
from osservatorio_seo.models import Feed, Item
from osservatorio_seo.premium_writer import PremiumWriter

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def fetch_article_text(url: str) -> str | None:
    """Best-effort fetch + plain-text extract per il body dell'articolo."""
    try:
        resp = httpx.get(
            url,
            headers={"User-Agent": UA},
            follow_redirects=True,
            timeout=20,
        )
        if resp.status_code != 200:
            return None
        tree = HTMLParser(resp.text)
        article = tree.css_first("article") or tree.css_first("main") or tree.body
        if article is None:
            return None
        text = article.text()
        for cut in ("Was this helpful?", "Send feedback", "Send a comment"):
            if cut in text:
                text = text.split(cut)[0]
        return " ".join(text.split())[:6000]
    except Exception as e:
        print(f"  (fetch error: {e})")
        return None


async def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: generate_deep_analysis.py <YYYY-MM-DD> <item_index>")
        sys.exit(2)
    date_iso = sys.argv[1]
    idx = int(sys.argv[2])

    repo_root = Path(__file__).resolve().parent.parent
    archive_file = repo_root / "data" / "archive" / f"{date_iso}.json"
    if not archive_file.exists():
        print(f"archive file not found: {archive_file}")
        sys.exit(1)

    raw = json.loads(archive_file.read_text(encoding="utf-8"))
    feed = Feed.model_validate(raw)
    if idx < 0 or idx >= len(feed.items):
        print(f"index out of range: {idx} (items={len(feed.items)})")
        sys.exit(1)
    item: Item = feed.items[idx]
    print(f"Target: [{idx}] {item.title_it}")
    print(f"  url: {item.url}")
    print(f"  importance: {item.importance}")

    if item.deep_analysis is not None:
        print("  NOTE: item has existing deep_analysis, will overwrite")

    print(f"\nRefetching article body from {item.url}…")
    body = fetch_article_text(item.url)
    if body:
        print(f"  fetched {len(body)} chars")
    else:
        print("  no body fetched, falling back to summary_it only")

    settings = load_settings()
    writer = PremiumWriter(api_key=settings.openrouter_api_key)

    print("\nCalling Claude Sonnet 4.5 via OpenRouter…")
    analysis = await writer.analyze(item, raw_content=body)
    print(f"  model: {analysis.premium_model_used}")
    print(f"  cost:  €{analysis.cost_eur:.5f}")
    print(f"  detailed_description: {len(analysis.detailed_description.split())} words")
    print(f"  implications: {len(analysis.implications)}")
    print(f"  examples: {len(analysis.examples)}")
    print(f"  testing_steps: {len(analysis.testing_steps)}")
    print(f"  faqs: {len(analysis.faqs)}")

    # Attach + save
    item.deep_analysis = analysis
    feed.items[idx] = item
    archive_file.write_text(
        feed.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nSaved to {archive_file}")

    # Preview
    print("\n--- DETAILED DESCRIPTION (first 400 chars) ---")
    print(analysis.detailed_description[:400] + "…")
    print("\n--- EDITORIAL COMMENTARY ---")
    print(analysis.editorial_commentary)
    print("\n--- FAQS ---")
    for f in analysis.faqs[:3]:
        print(f"Q: {f.question}")
        print(f"A: {f.answer[:200]}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
