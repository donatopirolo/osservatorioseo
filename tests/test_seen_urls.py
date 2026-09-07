from datetime import UTC, datetime, timedelta
from pathlib import Path

from osservatorio_seo.seen_urls import SeenUrlStore


def test_new_store_contains_nothing(tmp_path: Path) -> None:
    store = SeenUrlStore(tmp_path / "seen_urls.json")
    assert "https://example.com/a" not in store


def test_mark_seen_and_save_persist_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "seen_urls.json"
    store = SeenUrlStore(path)
    store.mark_seen("https://example.com/a")
    store.save()

    reloaded = SeenUrlStore(path)
    assert "https://example.com/a" in reloaded
    assert "https://example.com/b" not in reloaded


def test_save_prunes_entries_older_than_retention(tmp_path: Path) -> None:
    path = tmp_path / "seen_urls.json"
    store = SeenUrlStore(path, retention_hours=96)
    now = datetime.now(UTC)
    store.mark_seen("https://example.com/fresh", seen_at=now - timedelta(hours=10))
    store.mark_seen("https://example.com/stale", seen_at=now - timedelta(hours=200))
    store.save()

    reloaded = SeenUrlStore(path, retention_hours=96)
    assert "https://example.com/fresh" in reloaded
    assert "https://example.com/stale" not in reloaded


def test_corrupt_file_is_treated_as_empty(tmp_path: Path) -> None:
    path = tmp_path / "seen_urls.json"
    path.write_text("{not valid json", encoding="utf-8")
    store = SeenUrlStore(path)
    assert "https://example.com/a" not in store
