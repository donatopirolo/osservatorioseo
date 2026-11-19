"""Pagine /modifiche/: storico delle modifiche rilevate dal Doc Watcher.

Le fonti sono due, entrambe gia' su disco:

- ``data/state/doc_watcher/<page_id>_<YYYY-MM-DD>.diff``: il diff unificato
  salvato dalla pipeline quando una modifica viene pubblicata;
- gli item ``is_doc_change`` dell'archivio, con titolo e riassunto in italiano.

Non serve nessuna chiamata AI: le pagine si ricostruiscono da questi file.

Quanto testo della fonte mostrare (scelta di policy, vedi README): i docs di
Google Search Central sono in licenza CC BY 4.0 e il diff si mostra per intero,
con attribuzione. Per tutte le altre fonti (policy di OpenAI e Anthropic, PDF
delle Quality Rater Guidelines, schema.org) solo un estratto: le righe
cambiate, accorciate attorno al punto modificato, con un tetto complessivo.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from markupsafe import Markup, escape

from osservatorio_seo.models import Feed, Item

BASE_PATH = "/modifiche/"

# Host i cui contenuti sono in CC BY 4.0: diff mostrato per intero.
FULL_DIFF_HOSTS = frozenset({"developers.google.com"})

# Modalita' estratto: caratteri di contesto attorno a una modifica dentro una
# riga, lunghezza massima di una riga del tutto nuova o tolta, e tetto di
# caratteri della fonte su tutta la pagina.
EXCERPT_CONTEXT_CHARS = 80
EXCERPT_MAX_LINE_CHARS = 160
EXCERPT_MAX_TOTAL_CHARS = 1_500

_DIFF_NAME_RE = re.compile(r"^(?P<page_id>.+)_(?P<date>\d{4}-\d{2}-\d{2})$")
_HUNK_RE = re.compile(r"^@@ -(?P<old>\d+)(?:,\d+)? \+(?P<new>\d+)(?:,\d+)? @@")
_TOKEN_RE = re.compile(r"\s+|\w+|[^\w\s]", re.UNICODE)
_TRUNCATED_MARK = "... [diff truncated]"

DisplayMode = Literal["full", "excerpt"]
SegOp = Literal["eq", "del", "ins"]
Segment = tuple[SegOp, str]


def doc_slug(page_id: str) -> str:
    return page_id.replace("_", "-")


def doc_path(page_id: str) -> str:
    return f"{BASE_PATH}{doc_slug(page_id)}/"


def change_path(page_id: str, day: str) -> str:
    return f"{BASE_PATH}{doc_slug(page_id)}/{day}/"


def display_mode(url: str) -> DisplayMode:
    host = (urlparse(url).hostname or "").lower()
    return "full" if host in FULL_DIFF_HOSTS else "excerpt"


# ---------------------------------------------------------------------------
# Diff a livello di parola
# ---------------------------------------------------------------------------


def word_diff(old: str, new: str) -> list[Segment]:
    """Una riga sola: tratti uguali, tolti (del) e aggiunti (ins) in ordine."""
    a = _TOKEN_RE.findall(old)
    b = _TOKEN_RE.findall(new)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    segs: list[Segment] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            segs.append(("eq", "".join(a[i1:i2])))
            continue
        if i2 > i1:
            segs.append(("del", "".join(a[i1:i2])))
        if j2 > j1:
            segs.append(("ins", "".join(b[j1:j2])))
    return _merge(segs)


def _merge(segs: list[Segment]) -> list[Segment]:
    out: list[Segment] = []
    for op, text in segs:
        if not text:
            continue
        if out and out[-1][0] == op:
            out[-1] = (op, out[-1][1] + text)
        else:
            out.append((op, text))
    return out


def crop(segs: list[Segment], context: int, max_changed: int) -> list[Segment]:
    """Tiene la parte cambiata della riga e ``context`` caratteri attorno.

    I tratti invariati prima della prima modifica e dopo l'ultima vengono
    accorciati con un'ellissi; un tratto cambiato piu' lungo di
    ``max_changed`` viene troncato.
    """
    changed = [i for i, (op, _) in enumerate(segs) if op != "eq"]
    if not changed:
        return segs
    first, last = changed[0], changed[-1]
    out: list[Segment] = []
    for i, (op, text) in enumerate(segs):
        if op == "eq":
            if i < first:
                if len(text) > context:
                    text = "…" + text[-context:]
            elif i > last:
                if len(text) > context:
                    text = text[:context] + "…"
            elif len(text) > 2 * context:
                text = text[:context] + " … " + text[-context:]
        elif len(text) > max_changed:
            text = text[:max_changed] + "…"
        out.append((op, text))
    return out


def _segs_len(segs: list[Segment]) -> int:
    return sum(len(t) for _, t in segs)


# Classi Tailwind scritte qui e non nei template: questo file e' tra le
# @source di tailwind_input.css, altrimenti le classi non finirebbero nel CSS.
_DEL_CLASS = "bg-[#4a1c1c] text-[#ffb4ab] line-through decoration-[#ffb4ab]/60"
_INS_CLASS = "bg-[#0f3a1a] text-[#8dffa8] no-underline"


def segs_html(segs: list[Segment]) -> Markup:
    parts: list[str] = []
    for op, text in segs:
        esc = str(escape(text))
        if op == "del":
            parts.append(f'<del class="{_DEL_CLASS}">{esc}</del>')
        elif op == "ins":
            parts.append(f'<ins class="{_INS_CLASS}">{esc}</ins>')
        else:
            parts.append(esc)
    return Markup("".join(parts))


# ---------------------------------------------------------------------------
# Parsing del diff unificato
# ---------------------------------------------------------------------------


@dataclass
class DiffRow:
    kind: Literal["ctx", "del", "add", "chg"]
    html: Markup


@dataclass
class DiffHunk:
    old_line: int
    new_line: int
    rows: list[DiffRow] = field(default_factory=list)


@dataclass
class RenderedDiff:
    mode: DisplayMode
    hunks: list[DiffHunk]
    # True se non tutto il diff e' mostrato: tetto dell'estratto, oppure
    # diff gia' troncato dalla pipeline (MAX_DIFF_CHARS).
    truncated: bool
    hidden_hunks: int = 0


def _parse_hunks(diff: str) -> tuple[list[tuple[int, int, list[str]]], bool]:
    hunks: list[tuple[int, int, list[str]]] = []
    truncated = False
    current: list[str] | None = None
    for line in diff.splitlines():
        if line == _TRUNCATED_MARK:
            truncated = True
            continue
        if line.startswith("--- ") or line.startswith("+++ "):
            continue
        m = _HUNK_RE.match(line)
        if m:
            current = []
            hunks.append((int(m["old"]), int(m["new"]), current))
            continue
        if current is not None and line[:1] in (" ", "-", "+", ""):
            current.append(line)
    return hunks, truncated


def render_diff(diff: str, mode: DisplayMode) -> RenderedDiff:
    raw_hunks, truncated = _parse_hunks(diff)
    hunks: list[DiffHunk] = []
    budget = EXCERPT_MAX_TOTAL_CHARS
    hidden = 0

    for idx, (old_line, new_line, lines) in enumerate(raw_hunks):
        if mode == "excerpt" and budget <= 0:
            hidden = len(raw_hunks) - idx
            truncated = True
            break
        hunk = DiffHunk(old_line=old_line, new_line=new_line)
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("-") or line.startswith("+"):
                dels: list[str] = []
                adds: list[str] = []
                while i < len(lines) and lines[i].startswith("-"):
                    dels.append(lines[i][1:])
                    i += 1
                while i < len(lines) and lines[i].startswith("+"):
                    adds.append(lines[i][1:])
                    i += 1
                pair_rows = _change_block(dels, adds, mode)
                for kind, segs in pair_rows:
                    if mode == "excerpt":
                        if budget <= 0:
                            truncated = True
                            break
                        budget -= _segs_len(segs)
                    hunk.rows.append(DiffRow(kind=kind, html=segs_html(segs)))
                continue
            # Riga di contesto: nell'estratto non si mostra.
            if mode == "full":
                hunk.rows.append(DiffRow(kind="ctx", html=segs_html([("eq", line[1:])])))
            i += 1
        if any(r.kind != "ctx" for r in hunk.rows):
            hunks.append(hunk)

    return RenderedDiff(mode=mode, hunks=hunks, truncated=truncated, hidden_hunks=hidden)


def _change_block(
    dels: list[str], adds: list[str], mode: DisplayMode
) -> list[tuple[Literal["del", "add", "chg"], list[Segment]]]:
    """Righe tolte e aggiunte di un blocco, con le parole cambiate evidenziate.

    Le righe vengono accoppiate in ordine (la prima tolta con la prima
    aggiunta...) solo se si somigliano abbastanza: la coppia diventa una
    riga sola ("chg") con tolto e aggiunto in linea. Righe troppo diverse
    restano separate: un diff per parola evidenzierebbe tutto.
    """
    rows: list[tuple[Literal["del", "add", "chg"], list[Segment]]] = []
    for k in range(max(len(dels), len(adds))):
        old = dels[k] if k < len(dels) else None
        new = adds[k] if k < len(adds) else None
        if old is not None and new is not None and _similar(old, new):
            rows.append(("chg", word_diff(old, new)))
            continue
        if old is not None and old.strip():
            rows.append(("del", [("del", old)]))
        if new is not None and new.strip():
            rows.append(("add", [("ins", new)]))
    if mode == "excerpt":
        rows = [
            (kind, crop(segs, EXCERPT_CONTEXT_CHARS, EXCERPT_MAX_LINE_CHARS)) for kind, segs in rows
        ]
    return rows


def _similar(a: str, b: str) -> bool:
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() >= 0.4


# ---------------------------------------------------------------------------
# Caricamento dello storico
# ---------------------------------------------------------------------------


@dataclass
class DocChangeRecord:
    page_id: str
    day: str  # YYYY-MM-DD, giorno di pubblicazione sul sito
    diff: str
    page_name: str
    page_url: str
    item: Item | None  # notizia pubblicata nel feed (titolo e riassunto IT)

    @property
    def path(self) -> str:
        return change_path(self.page_id, self.day)

    @property
    def lines_added(self) -> int:
        return sum(
            1
            for line in self.diff.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )

    @property
    def lines_removed(self) -> int:
        return sum(
            1
            for line in self.diff.splitlines()
            if line.startswith("-") and not line.startswith("---")
        )


def _archive_doc_items(archive_dir: Path) -> list[tuple[str, Item]]:
    """(giorno d'archivio, item) per ogni doc-change pubblicato."""
    out: list[tuple[str, Item]] = []
    for path in sorted(archive_dir.glob("*.json")):
        if path.stem == "index":
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                continue
            feed = Feed.model_validate(raw)
        except Exception:  # noqa: BLE001
            continue
        for item in feed.items:
            if item.is_doc_change and item.doc_change is not None:
                out.append((path.stem, item))
    return out


def load_doc_changes(
    state_dir: Path,
    archive_dir: Path,
    page_names: dict[str, tuple[str, str]] | None = None,
) -> list[DocChangeRecord]:
    """Tutte le modifiche con un diff salvato, piu' recenti prima.

    ``page_names`` mappa ``page_id -> (nome, url)`` dal config attuale; per
    le pagine non piu' sorvegliate nome e url si prendono dall'item d'archivio.

    Il diff e' salvato con la data del controllo, l'item con quella del giorno
    d'archivio: di solito coincidono, ma un run a cavallo della mezzanotte
    UTC le sfasa di un giorno, quindi l'abbinamento tollera +-1.
    """
    page_names = page_names or {}
    items_by_page: dict[str, list[tuple[str, Item]]] = {}
    for day, item in _archive_doc_items(archive_dir):
        assert item.doc_change is not None
        items_by_page.setdefault(item.doc_change.page_id, []).append((day, item))

    records: list[DocChangeRecord] = []
    used: set[str] = set()
    for diff_file in sorted(Path(state_dir).glob("*.diff")):
        m = _DIFF_NAME_RE.match(diff_file.stem)
        if not m:
            continue
        page_id, diff_day = m["page_id"], m["date"]
        diff = diff_file.read_text(encoding="utf-8")
        if not diff.strip():
            continue
        item, day = _match_item(items_by_page.get(page_id, []), diff_day, used)
        if item is not None:
            used.add(item.id)
        name, url = page_names.get(page_id, (None, None))
        if name is None:
            name = item.title_original if item else page_id
            url = item.url if item else ""
        records.append(
            DocChangeRecord(
                page_id=page_id,
                day=day,
                diff=diff,
                page_name=name,
                page_url=url or "",
                item=item,
            )
        )
    records.sort(key=lambda r: (r.day, r.page_id), reverse=True)
    return records


def _match_item(
    candidates: list[tuple[str, Item]], diff_day: str, used: set[str]
) -> tuple[Item | None, str]:
    d = date.fromisoformat(diff_day)
    for delta in (0, 1, -1):
        target = (d + timedelta(days=delta)).isoformat()
        for day, item in candidates:
            if day == target and item.id not in used:
                return item, day
    return None, diff_day


def doc_change_links(records: list[DocChangeRecord]) -> dict[str, str]:
    """``item.id -> path`` della pagina modifica, per linkarla dalle card."""
    return {r.item.id: r.path for r in records if r.item is not None}
