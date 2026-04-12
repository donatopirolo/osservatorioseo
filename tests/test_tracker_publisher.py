"""Integration test for publisher._ssg_tracker."""

import json
from pathlib import Path

import pytest

from osservatorio_seo.publisher import Publisher
from osservatorio_seo.renderer import HtmlRenderer
from osservatorio_seo.tracker.models import TrackerSnapshot


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def snapshot(fixtures_dir: Path) -> TrackerSnapshot:
    data = json.loads((fixtures_dir / "tracker_snapshot.json").read_text())
    return TrackerSnapshot.model_validate(data)


def test_ssg_tracker_writes_dashboard(tmp_path: Path, repo_root: Path, snapshot: TrackerSnapshot):
    data_dir = tmp_path / "data"
    tracker_dir = data_dir / "tracker" / "snapshots"
    tracker_dir.mkdir(parents=True)
    (tracker_dir / "2026-W15.json").write_text(snapshot.model_dump_json(indent=2))

    archive_dir = data_dir / "archive"
    archive_dir.mkdir()
    site_dir = tmp_path / "site"
    site_dir.mkdir()

    pub = Publisher(
        data_dir=data_dir,
        archive_dir=archive_dir,
        site_data_dir=site_dir / "data",
    )
    renderer = HtmlRenderer(repo_root / "templates")

    pub._ssg_tracker(renderer=renderer, site_dir=site_dir, allow_indexing=False)

    dashboard = site_dir / "tracker" / "index.html"
    assert dashboard.exists()
    html = dashboard.read_text()
    assert "TRACKER SETTIMANALE" in html
    assert "METODOLOGIA" in html
    assert "AI VS INTERNET IN ITALIA" in html
