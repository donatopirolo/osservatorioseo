#!/usr/bin/env python3
"""Aggiorna la sezione Brevetti a partire da ``config/patents.yml``.

Google Patents tollera pochissime richieste per volta dai runner di GitHub
(4 nel test del 29/10/2026, poi pagina "Sorry..."): lo script lavora quindi a
piccoli lotti, con al massimo ``max_requests_per_run`` richieste per run, e
gira ogni giorno. In ordine:

1. seed: i brevetti di ``seed`` ancora senza scheda (1 richiesta ciascuno);
2. coda: i brevetti gia' accettati dalla discovery in un run precedente;
3. discovery: UNA ricerca, a rotazione tra ``discovery.queries``. I risultati
   nuovi, US e con titolare Google, passano dal classificatore (titolo +
   snippet, nessuna richiesta a Google Patents); quelli con rilevanza SEO
   >= ``min_relevance`` entrano in coda, gli altri tra gli scartati.

Lo stato (coda, scartati, rotazione, blocchi consecutivi) vive in
``data/state/patents_discovery.json``. Se Google Patents blocca, lo script
salva ed esce senza errore; dopo ``max_blocked_streak`` run bloccati di fila
esce con codice 2, cosi' il workflow apre una issue.

Usage:
    uv run python scripts/update_patents.py                  # run giornaliero
    uv run python scripts/update_patents.py --no-discovery   # solo seed e coda
    uv run python scripts/update_patents.py --number US11769017B1 --force
    uv run python scripts/update_patents.py --from-html DIR  # seed da HTML gia' scaricato

``--from-html`` analizza le pagine salvate in DIR come ``<NUMERO>.html`` (es.
lette da un browser) senza chiamare Google Patents.

Richiede ``OPENROUTER_API_KEY`` in env.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from osservatorio_seo.patents.google_patents import (  # noqa: E402
    GooglePatentsClient,
    PatentNotFoundError,
    PatentsBlockedError,
    parse_patent_page,
)
from osservatorio_seo.patents.models import Patent, PatentDoc  # noqa: E402
from osservatorio_seo.patents.writer import PatentAnalysisError, analyze, classify  # noqa: E402
from osservatorio_seo.premium_writer import PremiumWriter  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
PATENTS_DIR = REPO_ROOT / "data" / "patents"
STATE_PATH = REPO_ROOT / "data" / "state" / "patents_discovery.json"
CONFIG_PATH = REPO_ROOT / "config" / "patents.yml"

FROM_HTML_CONCURRENCY = 3
CONFIG: dict[str, Any] = (
    yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) if CONFIG_PATH.exists() else {}
)

# Il classificatore legge titolo e snippet: un modello economico basta.
CLASSIFIER_MODEL = "anthropic/claude-haiku-4.5"


class RequestBudgetExhaustedError(Exception):
    pass


class BudgetedClient:
    """Avvolge il client contando le richieste: oltre il tetto non ne parte nessuna."""

    def __init__(self, client: GooglePatentsClient, budget: int) -> None:
        self._client = client
        self.remaining = budget

    def _spend(self) -> None:
        if self.remaining <= 0:
            raise RequestBudgetExhaustedError
        self.remaining -= 1

    async def fetch(self, number: str) -> PatentDoc:
        self._spend()
        return await self._client.fetch(number)

    async def search(self, query: str) -> list[dict[str, Any]]:
        self._spend()
        return await self._client.search(query)


def load_state() -> dict[str, Any]:
    state: dict[str, Any] = {}
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    state.setdefault("rejected", {})
    state.setdefault("pending", [])
    state.setdefault("next_query", 0)
    state.setdefault("query_last_run", {})
    state.setdefault("blocked_streak", 0)
    return state


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def save_patent(patent: Patent) -> None:
    PATENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = PATENTS_DIR / f"{patent.doc.number}.json"
    path.write_text(patent.model_dump_json(indent=2) + "\n", encoding="utf-8")


def existing_numbers() -> set[str]:
    return {p.stem for p in PATENTS_DIR.glob("*.json")} if PATENTS_DIR.exists() else set()


def build_query(base: str, since: date) -> str:
    """Query string per /xhr/query: spazi -> '+', virgolette -> %22, piu' data e ordinamento."""
    q = base.strip().replace('"', "%22").replace(" ", "+")
    return f"{q}&after=publication:{since:%Y%m%d}&sort=new&num=100"


async def write_patent(writer: PremiumWriter, doc: PatentDoc, origin: str) -> Patent | None:
    try:
        patent = await analyze(writer, doc, origin)  # type: ignore[arg-type]
    except PatentAnalysisError as e:
        print(f"  WARN {e}")
        return None
    # Secondo filtro per la discovery: il classificatore vede solo titolo e
    # snippet, l'analisi legge tutto il documento. Se dopo la lettura completa
    # la rilevanza crolla, la scheda non si pubblica (i seed passano sempre).
    min_final = int(CONFIG.get("min_final_relevance", 3))
    if origin != "seed" and patent.analysis.seo_relevance < min_final:
        print(
            f"  SKIP {doc.number}: rilevanza {patent.analysis.seo_relevance} dopo la lettura "
            f"completa ({patent.analysis.scope})"
        )
        return None
    save_patent(patent)
    print(
        f"  OK {doc.number}: {patent.analysis.title_it} "
        f"[{patent.analysis.theme}, rilevanza {patent.analysis.seo_relevance}] "
        f"€{patent.cost_eur:.3f}"
    )
    return patent


async def fetch_and_write(
    client: BudgetedClient, writer: PremiumWriter, number: str, origin: str
) -> bool:
    """True se il brevetto e' stato gestito (scheda scritta o non recuperabile)."""
    try:
        doc = await client.fetch(number)
    except PatentNotFoundError:
        print(f"  WARN {number}: non trovato su Google Patents")
        return True
    # Una scheda non valida si ritenta al prossimo run: la richiesta e' spesa,
    # ma un errore del modello non deve far perdere il brevetto.
    return await write_patent(writer, doc, origin) is not None


async def discover(
    client: BudgetedClient,
    classifier: PremiumWriter,
    cfg: dict[str, Any],
    state: dict[str, Any],
) -> None:
    queries = cfg["queries"]
    idx = state["next_query"] % len(queries)
    base = queries[idx]
    today = datetime.now(UTC).date()
    last = state["query_last_run"].get(str(idx))
    if last:
        since = date.fromisoformat(last) - timedelta(days=cfg["overlap_days"])
    else:
        since = today - timedelta(days=cfg["initial_lookback_days"])
    print(f"Discovery: query {idx + 1}/{len(queries)}, pubblicazioni dal {since}")

    results = await client.search(build_query(base, since))
    state["next_query"] = idx + 1
    state["query_last_run"][str(idx)] = today.isoformat()

    known = existing_numbers() | set(state["rejected"]) | set(state["pending"])
    candidates = [
        r
        for r in results
        if r["number"] not in known
        and r["number"].startswith("US")
        and "google" in r["assignee"].lower()
    ]
    print(f"  {len(results)} risultati, {len(candidates)} candidati nuovi")

    for r in candidates[: cfg["max_classify_per_run"]]:
        c = await classify(
            classifier,
            number=r["number"],
            title=r["title"],
            abstract=r["snippet"],
            assignees=r["assignee"],
            cpc="",
        )
        if c.seo_relevance >= cfg["min_relevance"]:
            state["pending"].append(r["number"])
            print(f"  + in coda {r['number']} ({c.seo_relevance}) {r['title'][:70]}")
        else:
            state["rejected"][r["number"]] = {
                "title": r["title"],
                "seo_relevance": c.seo_relevance,
                "reason": c.reason,
                "checked_at": today.isoformat(),
            }


def _invention_key(doc: PatentDoc) -> tuple[str, object]:
    return (doc.title.strip().lower(), doc.priority_date)


def family_duplicates(docs: list[PatentDoc], have: list[PatentDoc]) -> dict[str, str]:
    """``{numero: parente}`` per i doc della stessa invenzione di uno gia' schedato o scelto.

    Due criteri, perche' nessuno dei due basta da solo:
    - famiglia: la pagina di Google Patents elenca solo genitore e figli
      diretti, non tutta la catena di continuation;
    - stesso titolo e stessa data di priorita': e' il caso tipico delle
      continuation, anche lontane nella catena.
    I doc vanno passati in ordine di priorita' (il primo di una famiglia vince).
    """
    taken_numbers = {d.number for d in have}
    taken_keys = {_invention_key(d): d.number for d in have}
    dupes: dict[str, str] = {}
    for doc in docs:
        relatives = {m.number for m in doc.family} & taken_numbers
        hit = min(relatives) if relatives else taken_keys.get(_invention_key(doc))
        if hit:
            dupes[doc.number] = hit
            continue
        taken_numbers.add(doc.number)
        taken_keys.setdefault(_invention_key(doc), doc.number)
    return dupes


async def run_from_html(
    writer: PremiumWriter, html_dir: Path, seeds: list[str], force: bool
) -> None:
    have = existing_numbers()
    docs: list[PatentDoc] = []
    for path in sorted(html_dir.glob("*.html")):
        if path.stem in have and not force:
            print(f"  {path.stem}: scheda gia' presente, salto")
            continue
        docs.append(parse_patent_page(path.stem, path.read_text(encoding="utf-8")))
    # I seed passano sempre; gli altri saltano se la loro invenzione e' gia' coperta,
    # da una scheda esistente o da un seed dello stesso lotto.
    published = [
        Patent.model_validate_json(p.read_text(encoding="utf-8")).doc
        for p in PATENTS_DIR.glob("*.json")
    ]
    seed_docs = [d for d in docs if d.number in seeds]
    dupes = family_duplicates([d for d in docs if d.number not in seeds], published + seed_docs)
    for number, relative in dupes.items():
        print(f"  {number}: stessa invenzione di {relative}, salto")
    todo = [d for d in docs if d.number not in dupes]

    # Qualche analisi in parallelo: con decine di brevetti in sequenza il
    # recupero storico durerebbe ore. Oltre si va a sbattere sui 429.
    sem = asyncio.Semaphore(FROM_HTML_CONCURRENCY)

    async def one(doc: PatentDoc) -> None:
        async with sem:
            await write_patent(writer, doc, "seed" if doc.number in seeds else "discovery")

    await asyncio.gather(*(one(d) for d in todo))


async def main() -> int:
    parser = argparse.ArgumentParser(description="Aggiorna la sezione Brevetti.")
    parser.add_argument("--number", help="Genera solo questo brevetto.")
    parser.add_argument("--force", action="store_true", help="Rigenera anche se esiste.")
    parser.add_argument("--no-discovery", action="store_true", help="Salta la ricerca automatica.")
    parser.add_argument("--from-html", type=Path, help="Analizza le pagine salvate in questa dir.")
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERRORE: OPENROUTER_API_KEY non impostata")
        return 1

    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    seeds = [str(s) for s in cfg.get("seed", [])]
    writer = PremiumWriter(api_key=api_key)

    if args.from_html:
        await run_from_html(writer, args.from_html, seeds, args.force)
        return 0

    classifier = PremiumWriter(api_key=api_key, primary_model=CLASSIFIER_MODEL, fallback_models=[])
    state = load_state()
    budget = int(cfg.get("max_requests_per_run", 3))
    exit_code = 0

    async with GooglePatentsClient(delay_s=float(cfg.get("request_delay_s", 20))) as raw:
        client = BudgetedClient(raw, budget)
        try:
            if args.number:
                number = args.number.strip().upper()
                if number in existing_numbers() and not args.force:
                    print(f"{number}: scheda gia' presente (usa --force per rigenerarla)")
                    return 0
                await fetch_and_write(
                    client, writer, number, "seed" if number in seeds else "discovery"
                )
                return 0

            have = existing_numbers()
            todo_seed = [n for n in seeds if args.force or n not in have]
            print(f"Seed da generare: {len(todo_seed)} · in coda: {len(state['pending'])}")
            for n in todo_seed:
                await fetch_and_write(client, writer, n, "seed")
            for n in list(state["pending"]):
                if await fetch_and_write(client, writer, n, "discovery"):
                    state["pending"].remove(n)
            if not args.no_discovery:
                await discover(client, classifier, cfg["discovery"], state)
            state["blocked_streak"] = 0
        except RequestBudgetExhaustedError:
            print(f"Tetto di {budget} richieste raggiunto, il resto al prossimo run.")
            state["blocked_streak"] = 0
        except PatentsBlockedError as e:
            state["blocked_streak"] += 1
            streak = state["blocked_streak"]
            print(f"::warning::{e} (run bloccati di fila: {streak}). Riprovo al prossimo run.")
            if streak >= int(cfg.get("max_blocked_streak", 3)):
                print(f"::error::Google Patents blocca da {streak} run consecutivi.")
                exit_code = 2
        finally:
            save_state(state)
    return exit_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
