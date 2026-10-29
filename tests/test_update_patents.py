import importlib.util
import json
import sys
from pathlib import Path

import pytest

from osservatorio_seo.patents.google_patents import PatentsBlockedError

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "update_patents.py"


@pytest.fixture
def up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location("update_patents", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = tmp_path / "patents.yml"
    config.write_text(
        "seed: [US1B1, US2B1, US3B1, US4B1]\n"
        "discovery:\n"
        "  queries: [q=(search)]\n"
        "  initial_lookback_days: 30\n"
        "  overlap_days: 10\n"
        "  min_relevance: 4\n"
        "  max_classify_per_run: 5\n"
        "max_requests_per_run: 3\n"
        "request_delay_s: 0\n"
        "max_blocked_streak: 2\n"
    )
    monkeypatch.setattr(module, "CONFIG_PATH", config)
    monkeypatch.setattr(module, "PATENTS_DIR", tmp_path / "patents")
    monkeypatch.setattr(module, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setattr(sys, "argv", ["update_patents.py"])
    return module


class FakeClient:
    def __init__(self, *args, block: bool = False, **kwargs) -> None:
        self.block = block
        self.fetched: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def fetch(self, number: str):
        if self.block:
            raise PatentsBlockedError("Sorry")
        self.fetched.append(number)
        return number  # write_patent e' sostituito: basta un segnaposto

    async def search(self, query: str):
        return []


async def test_run_stops_at_request_budget(up, monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient()
    monkeypatch.setattr(up, "GooglePatentsClient", lambda **kw: client)

    async def fake_write(writer, doc, origin):
        return object()

    monkeypatch.setattr(up, "write_patent", fake_write)

    assert await up.main() == 0
    # 4 seed in config ma tetto a 3 richieste: il quarto resta per domani.
    assert client.fetched == ["US1B1", "US2B1", "US3B1"]


async def test_blocked_runs_increment_streak_and_fail_at_threshold(
    up, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(up, "GooglePatentsClient", lambda **kw: FakeClient(block=True))

    assert await up.main() == 0
    assert json.loads(up.STATE_PATH.read_text())["blocked_streak"] == 1
    # Secondo blocco di fila = soglia (2): exit 2, il workflow apre la issue.
    assert await up.main() == 2
    assert json.loads(up.STATE_PATH.read_text())["blocked_streak"] == 2


async def test_successful_run_resets_streak(up, monkeypatch: pytest.MonkeyPatch) -> None:
    up.STATE_PATH.write_text(json.dumps({"blocked_streak": 1}))
    monkeypatch.setattr(up, "GooglePatentsClient", lambda **kw: FakeClient())

    async def fake_write(writer, doc, origin):
        return object()

    monkeypatch.setattr(up, "write_patent", fake_write)

    assert await up.main() == 0
    assert json.loads(up.STATE_PATH.read_text())["blocked_streak"] == 0


def test_build_query_encodes_quotes_and_adds_date(up) -> None:
    from datetime import date

    q = up.build_query('q=("search results")&assignee=Google+Llc', date(2026, 9, 1))
    assert q == (
        "q=(%22search+results%22)&assignee=Google+Llc&after=publication:20260901&sort=new&num=100"
    )
