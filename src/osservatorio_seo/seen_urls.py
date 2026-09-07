"""Memoria cross-run degli URL gia' riassunti dalla pipeline.

Il Normalizer applica una finestra di freschezza (``max_age_hours``, vedi
Settings) sugli item in base a ``published_at``: con una finestra larga
(72h, per non perdere le fonti che pubblicano nel weekend o con ritardo)
lo stesso item puo' ricomparire in ``normalized`` per piu' run consecutivi.
Senza questo store, ogni ricomparsa verrebbe rimandata al summarizer AI e
pagata di nuovo. Lo store ricorda quali URL sono gia' stati riassunti con
successo e per quanto tempo, cosi' la pipeline puo' saltarli.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path


class SeenUrlStore:
    def __init__(self, path: Path, retention_hours: int = 96) -> None:
        self._path = Path(path)
        self._retention = timedelta(hours=retention_hours)
        self._seen: dict[str, str] = self._load()

    def _load(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return {str(k): str(v) for k, v in data.get("urls", {}).items()}
        except Exception:  # noqa: BLE001
            return {}

    def __contains__(self, url: str) -> bool:
        return url in self._seen

    def mark_seen(self, url: str, seen_at: datetime | None = None) -> None:
        self._seen[url] = (seen_at or datetime.now(UTC)).isoformat()

    def save(self) -> None:
        """Pota le entry piu' vecchie della finestra di retention e scrive su disco."""
        cutoff = datetime.now(UTC) - self._retention
        pruned: dict[str, str] = {}
        for url, seen_at in self._seen.items():
            try:
                ts = datetime.fromisoformat(seen_at)
            except ValueError:
                continue
            if ts >= cutoff:
                pruned[url] = seen_at
        self._seen = pruned

        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"schema_version": "1", "urls": self._seen}, indent=2, sort_keys=True),
            encoding="utf-8",
        )
