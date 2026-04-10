"""Persistenza stato del Doc Watcher (hash, testi, diff)."""
from __future__ import annotations

from pathlib import Path


class StateStore:
    def __init__(self, base_dir: Path) -> None:
        self._dir = Path(base_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def load_hash(self, page_id: str) -> str | None:
        p = self._dir / f"{page_id}.hash"
        return p.read_text(encoding="utf-8").strip() if p.exists() else None

    def load_text(self, page_id: str) -> str | None:
        p = self._dir / f"{page_id}.txt"
        return p.read_text(encoding="utf-8") if p.exists() else None

    def save(self, page_id: str, hash_value: str, text: str) -> None:
        (self._dir / f"{page_id}.hash").write_text(hash_value, encoding="utf-8")
        (self._dir / f"{page_id}.txt").write_text(text, encoding="utf-8")

    def save_diff(self, page_id: str, date_str: str, diff: str) -> None:
        (self._dir / f"{page_id}_{date_str}.diff").write_text(diff, encoding="utf-8")
