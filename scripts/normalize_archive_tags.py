#!/usr/bin/env python3
"""Normalizza i tag di tutti gli item in ``data/archive/*.json``.

Applica ``osservatorio_seo.tags.normalize_tags`` a ogni ``item.tags`` e
riscrive i file se ci sono differenze. Lo script è idempotente.

Usage:
    .venv/bin/python scripts/normalize_archive_tags.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from osservatorio_seo.models import Feed
from osservatorio_seo.tags import normalize_tags


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    archive_dir = repo_root / "data" / "archive"
    touched = 0
    item_count = 0
    tag_changes = 0

    for f in sorted(archive_dir.glob("2*.json")):
        if f.stem == "index":
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        try:
            feed = Feed.model_validate(data)
        except Exception as e:
            print(f"SKIP {f.name}: {e}")
            continue
        changed = False
        for item in feed.items:
            item_count += 1
            before = list(item.tags)
            after = normalize_tags(before)
            if before != after:
                item.tags = after
                tag_changes += 1
                changed = True
        if changed:
            f.write_text(feed.model_dump_json(indent=2) + "\n", encoding="utf-8")
            print(f"  updated {f.name}")
            touched += 1

    # Anche feed.json corrente
    current = repo_root / "data" / "feed.json"
    if current.exists():
        data = json.loads(current.read_text(encoding="utf-8"))
        try:
            feed = Feed.model_validate(data)
            changed = False
            for item in feed.items:
                before = list(item.tags)
                after = normalize_tags(before)
                if before != after:
                    item.tags = after
                    tag_changes += 1
                    changed = True
            if changed:
                current.write_text(
                    feed.model_dump_json(indent=2) + "\n", encoding="utf-8"
                )
                print("  updated data/feed.json")
                touched += 1
        except Exception as e:
            print(f"SKIP feed.json: {e}")

    print(
        f"\nDone. files touched={touched}, items scanned={item_count}, "
        f"items with tag changes={tag_changes}"
    )


if __name__ == "__main__":
    main()
