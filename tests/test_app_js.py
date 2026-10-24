from pathlib import Path

APP_JS = Path(__file__).resolve().parent.parent / "site" / "app.js"


def _render_archive_search_result_body() -> str:
    text = APP_JS.read_text()
    start = text.index("function renderArchiveSearchResult(")
    end = text.index("\n}\n", start)
    return text[start:end]


def test_archive_search_result_never_falls_back_to_source_url() -> None:
    """Regressione 1.10: per gli item con importance < 4 (mai in
    item_index.json), il risultato di ricerca cross-archivio linkava ancora
    all'URL esterno della fonte invece che allo snapshot del giorno, che
    esiste per ogni giorno in archivio indipendentemente dall'importance."""
    body = _render_archive_search_result_body()
    path_line = next(line for line in body.splitlines() if "const path =" in line)
    assert "item.url" not in path_line
    assert "item.importance" not in path_line
