"""Pagine /modifiche/ del Doc Watcher: diff per parola, estratti, abbinamento, SSG."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from osservatorio_seo import doc_changes as dc
from osservatorio_seo.config import DocWatcherPage
from osservatorio_seo.models import DocChange, Feed, FeedStats, Item, Source
from osservatorio_seo.publisher import Publisher

GOOGLE_URL = "https://developers.google.com/search/docs/crawling-indexing/robots/robots_txt"
OTHER_URL = "https://www.anthropic.com/legal/aup"

DIFF = """--- prev
+++ curr
@@ -10,4 +10,4 @@
 ## Heading

-Google uses the path value in rules.
+Google uses the path value in rules. Percent-encoding is recommended.

"""


def mk_doc_item(item_id: str, page_id: str, url: str, day: str) -> Item:
    when = datetime.fromisoformat(f"{day}T05:00:00+00:00")
    return Item(
        id=item_id,
        title_original="Pagina",
        title_it="⚠️ Titolo della modifica",
        summary_it="Riassunto della modifica.",
        url=url,
        source=Source(
            id="doc_watcher",
            name="OsservatorioSEO Doc Watcher",
            authority=10,
            type="doc_change",
            fetcher="rss",
        ),
        category="google_docs_change",
        tags=[],
        importance=4,
        published_at=when,
        fetched_at=when,
        is_doc_change=True,
        doc_change=DocChange(
            page_id=page_id,
            previous_hash="a",
            current_hash="b",
            lines_added=1,
            lines_removed=1,
        ),
        summarizer_model="x",
        raw_hash="b",
    )


def mk_feed(day: str, items: list[Item]) -> Feed:
    when = datetime.fromisoformat(f"{day}T05:00:00+00:00")
    return Feed(
        generated_at=when,
        generated_at_local=when,
        timezone="Europe/Rome",
        run_id=f"{day}-0700",
        stats=FeedStats(
            sources_checked=1,
            sources_failed=0,
            items_collected=1,
            items_after_dedup=1,
            doc_changes_detected=len(items),
            ai_cost_eur=0.0,
        ),
        top10=[i.id for i in items],
        categories={"google_docs_change": [i.id for i in items]},
        items=items,
        doc_watcher_status=[],
        failed_sources=[],
    )


# --- diff per parola -------------------------------------------------------


def test_word_diff_marks_only_changed_words() -> None:
    segs = dc.word_diff("the old value here", "the new value here")
    assert ("del", "old") in segs
    assert ("ins", "new") in segs
    assert segs[0] == ("eq", "the ")


def test_segs_html_escapes_source_text() -> None:
    html = str(dc.segs_html([("ins", "<script>")]))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_display_mode_full_only_for_google_docs() -> None:
    assert dc.display_mode(GOOGLE_URL) == "full"
    assert dc.display_mode(OTHER_URL) == "excerpt"
    assert dc.display_mode("https://static.googleusercontent.com/x.pdf") == "excerpt"


# --- render_diff -------------------------------------------------------------


def test_render_full_keeps_context_and_pairs_changed_line() -> None:
    out = dc.render_diff(DIFF, "full")
    assert len(out.hunks) == 1
    kinds = [r.kind for r in out.hunks[0].rows]
    assert "ctx" in kinds
    assert kinds.count("chg") == 1
    chg = next(r for r in out.hunks[0].rows if r.kind == "chg")
    assert "<ins" in str(chg.html) and "Percent-encoding" in str(chg.html)
    assert out.truncated is False


def test_render_excerpt_drops_context() -> None:
    out = dc.render_diff(DIFF, "excerpt")
    assert all(r.kind != "ctx" for h in out.hunks for r in h.rows)


def test_render_excerpt_caps_long_lines_and_total() -> None:
    long_line = "x" * 1000
    hunks = "".join(f"@@ -{i},1 +{i},1 @@\n+{long_line} {i}\n" for i in range(1, 40))
    out = dc.render_diff("--- prev\n+++ curr\n" + hunks, "excerpt")
    shown = sum(len(str(r.html)) for h in out.hunks for r in h.rows)
    assert out.truncated is True
    assert out.hidden_hunks > 0
    # ogni riga accorciata, e il totale molto sotto il diff originale
    assert all(
        len(str(r.html)) < dc.EXCERPT_MAX_LINE_CHARS + 120 for h in out.hunks for r in h.rows
    )
    assert shown < 40 * 1000 / 4


def test_render_detects_pipeline_truncation() -> None:
    out = dc.render_diff(DIFF + "... [diff truncated]\n", "full")
    assert out.truncated is True


# --- load_doc_changes ---------------------------------------------------------


def test_load_matches_item_with_one_day_offset(tmp_path: Path) -> None:
    state = tmp_path / "state"
    archive = tmp_path / "archive"
    state.mkdir()
    archive.mkdir()
    # diff salvato con la data UTC del 18, item nell'archivio del 19
    (state / "google_robots_txt_2026-11-18.diff").write_text(DIFF, encoding="utf-8")
    item = mk_doc_item("doc_2026-11-19_001", "google_robots_txt", GOOGLE_URL, "2026-11-19")
    (archive / "2026-11-19.json").write_text(
        mk_feed("2026-11-19", [item]).model_dump_json(), encoding="utf-8"
    )
    records = dc.load_doc_changes(state, archive)
    assert len(records) == 1
    r = records[0]
    assert r.item is not None and r.item.id == item.id
    assert r.day == "2026-11-19"
    assert r.path == "/modifiche/google-robots-txt/2026-11-19/"
    assert dc.doc_change_links(records) == {item.id: r.path}


def test_load_keeps_diff_without_item_and_uses_config_name(tmp_path: Path) -> None:
    state = tmp_path / "state"
    archive = tmp_path / "archive"
    state.mkdir()
    archive.mkdir()
    (state / "google_spam_policies_2026-04-13.diff").write_text(DIFF, encoding="utf-8")
    records = dc.load_doc_changes(
        state, archive, {"google_spam_policies": ("Google Spam Policies", GOOGLE_URL)}
    )
    assert len(records) == 1
    assert records[0].item is None
    assert records[0].page_name == "Google Spam Policies"
    assert records[0].page_url == GOOGLE_URL


# --- SSG -----------------------------------------------------------------------


def test_publish_ssg_writes_doc_change_pages_and_links(tmp_path: Path) -> None:
    data = tmp_path / "data"
    archive = data / "archive"
    state = data / "state" / "doc_watcher"
    state.mkdir(parents=True)
    archive.mkdir(parents=True)
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    item = mk_doc_item(f"doc_{day}_001", "google_robots_txt", GOOGLE_URL, day)
    feed = mk_feed(day, [item])
    (archive / f"{day}.json").write_text(feed.model_dump_json(), encoding="utf-8")
    (state / f"google_robots_txt_{day}.diff").write_text(DIFF, encoding="utf-8")

    pages = [
        DocWatcherPage(
            id="google_robots_txt",
            name="Google robots.txt Specification",
            url=GOOGLE_URL,
            importance=5,
        )
    ]
    site = tmp_path / "site"
    pub = Publisher(data_dir=data, archive_dir=archive)
    pub.publish_ssg(feed, [], pages, templates_dir=Path("templates"), site_dir=site)

    change = site / "modifiche" / "google-robots-txt" / day / "index.html"
    assert (site / "modifiche" / "index.html").exists()
    assert (site / "modifiche" / "google-robots-txt" / "index.html").exists()
    assert change.exists()
    html = change.read_text(encoding="utf-8")
    assert "Titolo della modifica" in html
    assert "⚠️ Titolo" not in html
    assert "CC BY 4.0" in html
    assert "Percent-encoding" in html

    # La card in home porta alla pagina della modifica, non alla fonte.
    home = (site / "index.html").read_text(encoding="utf-8")
    assert f'href="/modifiche/google-robots-txt/{day}/"' in home
    sitemap = (site / "sitemap.xml").read_text(encoding="utf-8")
    assert f"/modifiche/google-robots-txt/{day}/" in sitemap


def test_excerpt_page_has_no_cc_notice(tmp_path: Path) -> None:
    data = tmp_path / "data"
    archive = data / "archive"
    state = data / "state" / "doc_watcher"
    state.mkdir(parents=True)
    archive.mkdir(parents=True)
    day = "2026-10-09"
    item = mk_doc_item("doc_2026-10-09_001", "anthropic_usage_policies", OTHER_URL, day)
    feed = mk_feed(day, [item])
    (archive / f"{day}.json").write_text(feed.model_dump_json(), encoding="utf-8")
    (state / f"anthropic_usage_policies_{day}.diff").write_text(DIFF, encoding="utf-8")

    site = tmp_path / "site"
    pub = Publisher(data_dir=data, archive_dir=archive)
    pub.publish_ssg(feed, [], [], templates_dir=Path("templates"), site_dir=site)
    html = (site / "modifiche" / "anthropic-usage-policies" / day / "index.html").read_text(
        encoding="utf-8"
    )
    assert "ESTRATTO DELLE RIGHE CAMBIATE" in html
    assert "CC BY 4.0" not in html
    # pagina non piu' in config: nome preso dall'item d'archivio
    assert "Pagina" in html
