#!/usr/bin/env python3
"""Aggiorna i dossier (pillar pages) elencati in ``config/pillars.yml``.

Per ogni tag configurato:
1. Raccoglie gli item qualificanti dall'archivio (stesso filtro di
   ``generate_pillar.py``).
2. Decide se (ri)generare il dossier:
   - se il JSON non esiste -> genera;
   - se esiste ma ci sono almeno ``min_new_items`` item nuovi rispetto a
     ``Pillar.item_refs`` -> rigenera;
   - altrimenti -> skip (nessun materiale nuovo, niente costi).
3. Salva il risultato in ``data/pillars/<tag>.json``.

Usage:
    .venv/bin/python scripts/update_pillars.py            # tutti i tag in config
    .venv/bin/python scripts/update_pillars.py --force    # rigenera tutto
    .venv/bin/python scripts/update_pillars.py --tag core_update [--force]

Richiede ``OPENROUTER_API_KEY`` in env.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # per import di generate_pillar

from generate_pillar import collect_items_by_tag  # noqa: E402

from osservatorio_seo.config import load_settings  # noqa: E402
from osservatorio_seo.models import Pillar  # noqa: E402
from osservatorio_seo.premium_writer import PremiumWriter  # noqa: E402


def load_pillar_config(path: Path) -> tuple[list[str], int, int]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tags = [str(t).lower() for t in data.get("tags", [])]
    min_importance = int(data.get("min_importance", 3))
    min_new_items = int(data.get("min_new_items", 3))
    return tags, min_importance, min_new_items


def load_existing_pillar(path: Path) -> Pillar | None:
    if not path.exists():
        return None
    try:
        return Pillar.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"  WARN: pillar esistente illeggibile ({e}), verra' rigenerato")
        return None


async def main() -> None:
    parser = argparse.ArgumentParser(description="Aggiorna i dossier pillar.")
    parser.add_argument("--tag", help="Aggiorna solo questo tag (deve essere in config).")
    parser.add_argument(
        "--force", action="store_true", help="Rigenera anche senza item nuovi."
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    archive_dir = repo_root / "data" / "archive"
    pillars_dir = repo_root / "data" / "pillars"
    pillars_dir.mkdir(parents=True, exist_ok=True)
    config_path = repo_root / "config" / "pillars.yml"

    tags, min_importance, min_new_items = load_pillar_config(config_path)
    if args.tag:
        tag = args.tag.lower()
        if tag not in tags:
            print(f"Tag '{tag}' non presente in {config_path}. Aborting.")
            sys.exit(2)
        tags = [tag]

    if not tags:
        print("Nessun tag configurato in config/pillars.yml. Niente da fare.")
        return

    settings = load_settings()
    writer = PremiumWriter(api_key=settings.openrouter_api_key)

    generated = 0
    skipped = 0
    failed = 0
    total_cost = 0.0

    for tag in tags:
        slug = tag.replace("_", "-")
        out = pillars_dir / f"{tag}.json"
        print(f"\n=== {tag} (/dossier/{slug}/) ===")

        items = collect_items_by_tag(archive_dir, tag, min_importance=min_importance)
        current_ids = {it.id for it in items}
        print(f"  item qualificanti (importance>={min_importance}): {len(items)}")

        if not items:
            print("  nessun item, skip.")
            skipped += 1
            continue

        existing = load_existing_pillar(out)
        if existing is not None and not args.force:
            new_ids = current_ids - set(existing.item_refs)
            if len(new_ids) < min_new_items:
                print(
                    f"  solo {len(new_ids)} item nuovi (< {min_new_items}), skip "
                    f"(ultimo: {existing.generated_at:%Y-%m-%d})."
                )
                skipped += 1
                continue
            print(f"  {len(new_ids)} item nuovi >= {min_new_items}: rigenero.")
        elif existing is None:
            print("  dossier assente: genero ex novo.")
        else:
            print("  --force: rigenero.")

        try:
            pillar = await writer.write_pillar(tag, items)
        except Exception as e:  # noqa: BLE001
            print(f"  ERRORE generazione: {e}")
            failed += 1
            continue

        out.write_text(pillar.model_dump_json(indent=2) + "\n", encoding="utf-8")
        total_cost += pillar.cost_eur
        generated += 1
        print(
            f"  OK: {pillar.title_it!r} · modello {pillar.model_used} · "
            f"€{pillar.cost_eur:.5f} · {len(pillar.takeaways)} takeaway"
        )

    print(
        f"\n--- Riepilogo: {generated} generati, {skipped} saltati, "
        f"{failed} falliti · costo totale €{total_cost:.5f} ---"
    )
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
