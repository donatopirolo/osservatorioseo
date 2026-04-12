#!/usr/bin/env python3
"""Genera un :class:`Pillar` dossier su un tag specifico.

Usage:
    .venv/bin/python scripts/generate_pillar.py <tag>

Esempio:
    .venv/bin/python scripts/generate_pillar.py core_update

Lo script:
1. Enumera tutti gli item in ``data/archive/*.json`` con il tag specificato
2. Filtra solo item con importance >= 3 (esclude rumore)
3. Ordina cronologicamente
4. Invoca ``PremiumWriter.write_pillar(tag, items)``
5. Salva il risultato in ``data/pillars/<tag>.json``

Richiede ``OPENROUTER_API_KEY`` in env.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from osservatorio_seo.config import load_settings
from osservatorio_seo.models import Feed, Item
from osservatorio_seo.premium_writer import PremiumWriter


def collect_items_by_tag(archive_dir: Path, tag: str, min_importance: int = 3) -> list[Item]:
    items: list[Item] = []
    seen_ids: set[str] = set()
    for f in sorted(archive_dir.glob("2*.json")):
        try:
            feed = Feed.model_validate(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"  SKIP {f.name}: {e}")
            continue
        for it in feed.items:
            if it.id in seen_ids:
                continue
            if (
                tag not in [t.lower() for t in it.tags]
                and tag.replace("_", " ") not in it.title_it.lower()
            ):
                continue
            if it.importance < min_importance:
                continue
            items.append(it)
            seen_ids.add(it.id)
    return items


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: generate_pillar.py <tag>")
        sys.exit(2)
    tag = sys.argv[1].lower()

    repo_root = Path(__file__).resolve().parent.parent
    archive_dir = repo_root / "data" / "archive"
    pillars_dir = repo_root / "data" / "pillars"
    pillars_dir.mkdir(parents=True, exist_ok=True)

    print(f"Scanning archive for tag={tag}…")
    items = collect_items_by_tag(archive_dir, tag)
    print(f"  found {len(items)} items with tag '{tag}' (importance>=3)")
    for it in items:
        print(
            f"    - {it.published_at.strftime('%Y-%m-%d')} · imp={it.importance} · {it.title_it[:70]}"
        )
    if not items:
        print("No items to build a pillar on. Aborting.")
        sys.exit(1)

    settings = load_settings()
    writer = PremiumWriter(api_key=settings.openrouter_api_key)

    print(f"\nCalling Claude Sonnet 4.5 to write pillar '{tag}'…")
    pillar = await writer.write_pillar(tag, items)
    print(f"  model: {pillar.model_used}")
    print(f"  cost:  €{pillar.cost_eur:.5f}")
    print(f"  intro_long: {len(pillar.intro_long.split())} words")
    print(f"  context: {len(pillar.context_section.split())} words")
    print(f"  timeline: {len(pillar.timeline_narrative.split())} words")
    print(f"  takeaways: {len(pillar.takeaways)}")
    print(f"  outlook: {len(pillar.outlook.split())} words")

    out = pillars_dir / f"{tag}.json"
    out.write_text(pillar.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"\nSaved to {out}")
    print(f"\n--- TITLE ---\n{pillar.title_it}")
    print(f"\n--- SUBTITLE ---\n{pillar.subtitle_it}")
    print(f"\n--- INTRO (first 400 chars) ---\n{pillar.intro_long[:400]}…")
    print("\n--- TAKEAWAYS ---")
    for t in pillar.takeaways:
        print(f"• {t.title}: {t.body[:100]}…")


if __name__ == "__main__":
    asyncio.run(main())
