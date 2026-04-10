from pathlib import Path

from osservatorio_seo.doc_watcher.state import StateStore


def test_load_missing_returns_none(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    assert store.load_hash("google_spam") is None
    assert store.load_text("google_spam") is None


def test_save_and_load(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    store.save("google_spam", "sha256:abc", "Some content")
    assert store.load_hash("google_spam") == "sha256:abc"
    assert store.load_text("google_spam") == "Some content"


def test_save_diff(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    store.save_diff("google_spam", "2026-04-11", "--- old\n+++ new\n@@\n-a\n+b\n")
    diff_files = list(tmp_path.glob("google_spam_*.diff"))
    assert len(diff_files) == 1
    assert "2026-04-11" in diff_files[0].name
