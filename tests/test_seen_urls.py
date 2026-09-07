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


def test_titolo_gia_pubblicato_riconosciuto_tra_run(tmp_path: Path) -> None:
    """La sindacazione avviene il giorno dopo, con un URL diverso.

    Nell'archivio (155 giorni) ci sono 8 casi: cinque Growth Memo ripresi da
    Search Engine Journal a 24 ore, due notizie Microsoft Advertising uscite
    su SEJ e Roundtable. Per l'URL erano item nuovi, e uscivano due volte.
    """
    path = tmp_path / "seen_urls.json"
    store = SeenUrlStore(path)
    store.mark_seen("https://www.growth-memo.com/p/x", "The Ghost Citation Problem")
    store.save()

    domani = SeenUrlStore(path)
    assert "https://www.searchenginejournal.com/x" not in domani, "URL diverso: non basta"
    assert domani.seen_title("The Ghost Citation Problem") == "the ghost citation problem"
    assert domani.seen_title("Un'altra notizia del tutto diversa") is None


def test_titoli_scadono_con_la_retention(tmp_path: Path) -> None:
    path = tmp_path / "seen_urls.json"
    store = SeenUrlStore(path, retention_hours=96)
    now = datetime.now(UTC)
    store.mark_seen("https://a.example/1", "Titolo recente", seen_at=now - timedelta(hours=10))
    store.mark_seen("https://a.example/2", "Titolo vecchissimo", seen_at=now - timedelta(hours=200))
    store.save()

    reloaded = SeenUrlStore(path, retention_hours=96)
    assert reloaded.seen_title("Titolo recente") is not None
    assert reloaded.seen_title("Titolo vecchissimo") is None


def test_store_v1_senza_titoli_si_carica(tmp_path: Path) -> None:
    """I file scritti prima dell'aggiunta dei titoli non devono rompere il run."""
    path = tmp_path / "seen_urls.json"
    path.write_text(
        '{"schema_version": "1", "urls": {"https://a.example/1": "'
        + datetime.now(UTC).isoformat()
        + '"}}',
        encoding="utf-8",
    )
    store = SeenUrlStore(path)
    assert "https://a.example/1" in store
    assert store.seen_title("Qualsiasi titolo") is None
