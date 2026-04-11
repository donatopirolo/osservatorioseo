#!/usr/bin/env python3
"""Rigenera tutti gli HTML SSG a partire dai JSON in ``data/archive/*.json``
e dal feed corrente ``data/feed.json``.

Usage:
    .venv/bin/python scripts/rebuild_seo_html.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from osservatorio_seo.config import load_doc_watcher, load_sources
from osservatorio_seo.models import Feed
from osservatorio_seo.publisher import Publisher


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    data_dir = repo_root / "data"
    site_dir = repo_root / "site"
    archive_dir = data_dir / "archive"
    templates_dir = repo_root / "templates"

    sources = load_sources(repo_root / "config" / "sources.yml")
    doc_pages = load_doc_watcher(repo_root / "config" / "doc_watcher.yml")

    pub = Publisher(
        data_dir=data_dir,
        archive_dir=archive_dir,
        site_data_dir=site_dir / "data",
    )

    # Rigenera snapshot + articoli per ogni file archive
    for json_path in sorted(archive_dir.glob("20*.json")):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            feed = Feed.model_validate(data)
        except Exception as exc:
            print(f"SKIP {json_path.name}: {exc}")
            continue
        print(f"Rendering archive {json_path.stem}…")
        pub.publish_ssg(
            feed,
            sources,
            doc_pages,
            templates_dir=templates_dir,
            site_dir=site_dir,
            allow_indexing=False,
        )

    # Render finale con il feed corrente (sovrascrive homepage + sitemap con
    # l'ultimo state consistente)
    current_feed_path = data_dir / "feed.json"
    if current_feed_path.exists():
        data = json.loads(current_feed_path.read_text(encoding="utf-8"))
        feed = Feed.model_validate(data)
        print(f"Rendering current feed ({feed.run_id})…")
        pub.publish_ssg(
            feed,
            sources,
            doc_pages,
            templates_dir=templates_dir,
            site_dir=site_dir,
            allow_indexing=False,
        )

    print("Done.")


if __name__ == "__main__":
    main()
