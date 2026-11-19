"""Salute del Doc Watcher: quali pagine sorvegliate non si riescono a leggere.

Prima un errore su una pagina finiva solo come warning nel log: la policy di
OpenAI e' rimasta "sorvegliata" per mesi con una baseline anti-bot, e la
pagina releases di schema.org con un selettore che non trovava piu' nulla,
senza che nessuno se ne accorgesse.

Qui si tiene, per ogni pagina che fallisce, da quanti giorni consecutivi.
Il file ``_health.json`` sta accanto allo state del watcher, viene committato
dal workflow con il resto di ``data/`` e lo legge lo step che apre l'issue.
Si contano i giorni, non i run: un rilancio manuale nello stesso giorno non
deve far scattare l'allarme prima del tempo.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

ALERT_AFTER_DAYS = 3
HEALTH_FILE = "_health.json"


@dataclass
class PageHealth:
    failing_since: str  # YYYY-MM-DD
    last_failure: str  # YYYY-MM-DD
    failing_days: int
    last_error: str
    alert: bool = False


class WatchHealth:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self.pages: dict[str, PageHealth] = {}
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                self.pages = {k: PageHealth(**v) for k, v in raw.get("pages", {}).items()}
            except Exception:  # noqa: BLE001
                self.pages = {}

    def record_success(self, page_id: str) -> None:
        self.pages.pop(page_id, None)

    def record_failure(self, page_id: str, error: str, day: str, alert_enabled: bool) -> None:
        h = self.pages.get(page_id)
        if h is None:
            h = PageHealth(failing_since=day, last_failure=day, failing_days=1, last_error=error)
        elif h.last_failure != day:
            h.failing_days += 1
            h.last_failure = day
        h.last_error = error[:500]
        h.alert = alert_enabled and h.failing_days >= ALERT_AFTER_DAYS
        self.pages[page_id] = h

    def prune(self, page_ids: set[str]) -> None:
        """Toglie le pagine non piu' in config."""
        self.pages = {k: v for k, v in self.pages.items() if k in page_ids}

    def alerts(self) -> dict[str, PageHealth]:
        return {k: v for k, v in self.pages.items() if v.alert}

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "alert_after_days": ALERT_AFTER_DAYS,
            "pages": {k: asdict(v) for k, v in sorted(self.pages.items())},
        }
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", "utf-8")
