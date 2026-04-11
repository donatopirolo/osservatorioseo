"""Publisher: scrive feed.json, archivi, e copia verso site/."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from osservatorio_seo.models import Feed


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
