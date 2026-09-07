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
    def __init__(
        self,
        path: Path,
        retention_hours: int = 96,
        bootstrap_archive_dir: Path | None = None,
    ) -> None:
        self._path = Path(path)
        self._retention = timedelta(hours=retention_hours)
        self._seen: dict[str, str] = self._load()
        if not self._seen and bootstrap_archive_dir is not None:
            self._bootstrap(Path(bootstrap_archive_dir))

    def _bootstrap(self, archive_dir: Path) -> None:
        """Semina lo store dagli archivi recenti quando il file non esiste.

        Senza questo passaggio, il primo run dopo l'introduzione dello store
        parte con memoria vuota mentre la finestra di freschezza e' gia' a 72
        ore: tutti gli item pubblicati nei giorni precedenti risulterebbero
        nuovi e verrebbero riassunti e ripubblicati come notizie di oggi.
        Con l'archivio attuale sarebbero una cinquantina.

        Si guardano gli archivi che coprono la finestra di retention, e si
        marcano i loro URL con la data dell'archivio: cosi' la potatura in
        ``save()`` li fa scadere con la stessa regola degli altri.
        """
        if not archive_dir.is_dir():
            return
        cutoff = datetime.now(UTC) - self._retention
        files = sorted(
            (p for p in archive_dir.glob("*.json") if p.stem != "index"),
            reverse=True,
        )
        for path in files[:14]:
            try:
                day = datetime.fromisoformat(path.stem).replace(tzinfo=UTC)
            except ValueError:
                continue
            if day < cutoff:
                break
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            stamp = day.isoformat()
            for item in data.get("items", []):
                url = item.get("url")
                if url:
                    self._seen.setdefault(str(url), stamp)

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
