"""Publisher: scrive feed.json, archivi, e copia verso site/."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from osservatorio_seo.models import Feed, Source

if TYPE_CHECKING:
    from osservatorio_seo.config import DocWatcherPage


class Publisher:
    def __init__(
        self,
        data_dir: Path,
        archive_dir: Path,
        site_data_dir: Path | None = None,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._archive_dir = Path(archive_dir)
        self._site_data_dir = Path(site_data_dir) if site_data_dir else None

    def publish(self, feed: Feed) -> Path:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._archive_dir.mkdir(parents=True, exist_ok=True)

        feed_json = feed.model_dump_json(indent=2)
        feed_file = self._data_dir / "feed.json"
        feed_file.write_text(feed_json, encoding="utf-8")

        date_str = feed.generated_at_local.strftime("%Y-%m-%d")
        archive_file = self._archive_dir / f"{date_str}.json"
        archive_file.write_text(feed_json, encoding="utf-8")

        # Indice archivio: elenco ordinato di tutte le date disponibili
        archive_index = self._build_archive_index()
        archive_index_file = self._archive_dir / "index.json"
        archive_index_file.write_text(json.dumps(archive_index, indent=2), encoding="utf-8")

        if self._site_data_dir:
            self._site_data_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(feed_file, self._site_data_dir / "feed.json")

            # Copia l'intera dir archive nel site/ per servirla da Cloudflare Pages
            site_archive_dir = self._site_data_dir / "archive"
            site_archive_dir.mkdir(parents=True, exist_ok=True)
            for src in self._archive_dir.glob("*.json"):
                shutil.copy2(src, site_archive_dir / src.name)

        return feed_file

    def _build_archive_index(self) -> list[dict[str, str]]:
        """Ritorna la lista di tutte le date archivio disponibili, ordine desc."""
        entries: list[dict[str, str]] = []
        for path in self._archive_dir.glob("*.json"):
            if path.stem == "index":
                continue
            # Il nome file è YYYY-MM-DD.json
            entries.append({"date": path.stem, "file": path.name})
        entries.sort(key=lambda e: e["date"], reverse=True)
        return entries

    def publish_config_snapshot(
        self,
        sources: list[Source],
        doc_pages: list[DocWatcherPage],
    ) -> Path:
        """Scrive uno snapshot leggibile del config (fonti + doc watcher pages).

        Il file è pensato per essere consumato dalla pagina /docs.html del
        frontend, che lo legge per mostrare l'elenco aggiornato delle fonti
        e delle pagine sorvegliate senza dover parsare YAML lato client.
        """
        self._data_dir.mkdir(parents=True, exist_ok=True)
        snapshot = {
            "sources": [
                {
                    "id": s.id,
                    "name": s.name,
                    "type": s.type,
                    "authority": s.authority,
                    "fetcher": s.fetcher,
                    "url": s.feed_url or s.target_url or "",
                    "category_hint": s.category_hint,
                    "enabled": s.enabled,
                }
                for s in sources
            ],
            "doc_watcher_pages": [
                {
                    "id": p.id,
                    "name": p.name,
                    "url": p.url,
                    "type": p.type,
                    "importance": p.importance,
                    "category": p.category,
                }
                for p in doc_pages
            ],
        }
        target = self._data_dir / "config_snapshot.json"
        target.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        if self._site_data_dir:
            self._site_data_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, self._site_data_dir / "config_snapshot.json")
        return target
