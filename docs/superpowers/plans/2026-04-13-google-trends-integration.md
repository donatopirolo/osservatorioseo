# Google Trends Integration for Tracker Section 1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken Cloudflare Radar cross-reference in Section 1 ("Quali AI usano gli italiani?") with Google Trends interest-over-time data, providing a real comparative popularity chart of AI platforms in Italy.

**Architecture:** Add a new `TrendsClient` that wraps the `trendspy` library. The collector calls it alongside existing Radar fetches. Google Trends data is stored in the snapshot as `trends_it` / `trends_global` (new fields with empty defaults for backward compatibility). The JS chart in Section 1 reads trends data to render a line chart of relative search interest (0-100).

**Tech Stack:** Python 3.12, trendspy, Pydantic v2, vanilla JS SVG charts

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `src/osservatorio_seo/tracker/trends_client.py` | Wrapper around trendspy; fetches interest_over_time for configured keywords |
| Modify | `src/osservatorio_seo/tracker/models.py` | Add `TrendsPoint`, `TrendsTimeseries` models + snapshot fields |
| Modify | `src/osservatorio_seo/tracker/collector.py` | Add `_fetch_trends_both()` method using TrendsClient |
| Modify | `config/tracker_platforms.yaml` | Add `trends_keyword` field to 5 main platforms |
| Modify | `site/tracker/tracker-charts.js` | Rewrite `renderSection1()` to use trends data |
| Modify | `templates/pages/tracker.html.jinja` | Update Section 1 methodology text |
| Modify | `pyproject.toml` | Add `trendspy` dependency |
| Create | `tests/test_trends_client.py` | Unit tests for TrendsClient |
| Modify | `tests/test_tracker_collector.py` | Add mock for trends fetch |
| Modify | `tests/test_tracker_models.py` | Add tests for new models |

---

### Task 1: Add Pydantic models for Google Trends data

**Files:**
- Modify: `src/osservatorio_seo/tracker/models.py:10-11` (new model classes after TimeseriesPoint)
- Modify: `src/osservatorio_seo/tracker/models.py:107-122` (new snapshot fields)
- Test: `tests/test_tracker_models.py`

- [ ] **Step 1: Write failing test for TrendsPoint and TrendsTimeseries**

In `tests/test_tracker_models.py`, add at the top imports:

```python
from osservatorio_seo.tracker.models import TrendsPoint, TrendsTimeseries
```

Then add test class at the end of the file:

```python
class TestTrendsModels:
    def test_trends_point_roundtrip(self):
        p = TrendsPoint(
            date=datetime(2026, 4, 6, tzinfo=UTC),
            values={"ChatGPT": 100, "Claude AI": 12, "Perplexity": 8},
        )
        restored = TrendsPoint.model_validate_json(p.model_dump_json())
        assert restored.values["ChatGPT"] == 100
        assert restored.values["Claude AI"] == 12

    def test_trends_timeseries_defaults_empty(self):
        ts = TrendsTimeseries()
        assert ts.keywords == []
        assert ts.points == []

    def test_trends_timeseries_roundtrip(self):
        ts = TrendsTimeseries(
            keywords=["ChatGPT", "Claude AI"],
            points=[
                TrendsPoint(
                    date=datetime(2026, 4, 6, tzinfo=UTC),
                    values={"ChatGPT": 100, "Claude AI": 12},
                ),
            ],
        )
        restored = TrendsTimeseries.model_validate_json(ts.model_dump_json())
        assert restored.keywords == ["ChatGPT", "Claude AI"]
        assert len(restored.points) == 1
        assert restored.points[0].values["ChatGPT"] == 100

    def test_snapshot_has_trends_fields_with_defaults(self):
        snap = TrackerSnapshot(
            year=2026,
            week=16,
            generated_at=datetime(2026, 4, 13, tzinfo=UTC),
            metadata=SnapshotMetadata(),
        )
        assert isinstance(snap.trends_it, TrendsTimeseries)
        assert snap.trends_it.keywords == []
        assert isinstance(snap.trends_global, TrendsTimeseries)

    def test_snapshot_with_trends_roundtrip(self):
        snap = TrackerSnapshot(
            year=2026,
            week=16,
            generated_at=datetime(2026, 4, 13, tzinfo=UTC),
            metadata=SnapshotMetadata(),
            trends_it=TrendsTimeseries(
                keywords=["ChatGPT"],
                points=[
                    TrendsPoint(
                        date=datetime(2026, 4, 6, tzinfo=UTC),
                        values={"ChatGPT": 100},
                    ),
                ],
            ),
        )
        restored = TrackerSnapshot.model_validate_json(snap.model_dump_json())
        assert restored.trends_it.keywords == ["ChatGPT"]
        assert restored.trends_it.points[0].values["ChatGPT"] == 100
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_tracker_models.py::TestTrendsModels -v`
Expected: ImportError for `TrendsPoint`, `TrendsTimeseries`

- [ ] **Step 3: Implement models**

In `src/osservatorio_seo/tracker/models.py`, add after `TimeseriesPoint` class (after line 13):

```python
class TrendsPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: datetime
    values: dict[str, int]


class TrendsTimeseries(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keywords: list[str] = Field(default_factory=list)
    points: list[TrendsPoint] = Field(default_factory=list)
```

In the `TrackerSnapshot` class, add after `ai_platforms_global` (after line 110):

```python
    trends_it: TrendsTimeseries = Field(default_factory=TrendsTimeseries)
    trends_global: TrendsTimeseries = Field(default_factory=TrendsTimeseries)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_tracker_models.py -v`
Expected: All pass including new TestTrendsModels tests

- [ ] **Step 5: Verify existing snapshot loads with new fields**

Run: `python -c "from osservatorio_seo.tracker.models import TrackerSnapshot; import json; s = TrackerSnapshot.model_validate_json(open('data/tracker/snapshots/2026-W16.json').read()); print('trends_it:', s.trends_it); print('trends_global:', s.trends_global)"`
Expected: Both show empty TrendsTimeseries (backward compatible)

- [ ] **Step 6: Commit**

```bash
git add src/osservatorio_seo/tracker/models.py tests/test_tracker_models.py
git commit -m "feat(tracker): add TrendsPoint/TrendsTimeseries models for Google Trends data"
```

---

### Task 2: Create TrendsClient wrapper

**Files:**
- Create: `src/osservatorio_seo/tracker/trends_client.py`
- Create: `tests/test_trends_client.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_trends_client.py`:

```python
"""Tests for Google Trends client wrapper."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from osservatorio_seo.tracker.trends_client import TrendsClient


class TestTrendsClient:
    def test_fetch_interest_returns_keywords_and_points(self):
        mock_df = MagicMock()
        mock_df.columns = ["ChatGPT", "Claude AI", "isPartial"]
        mock_df.index = [datetime(2026, 4, 6), datetime(2026, 4, 13)]
        mock_df.__len__ = lambda self: 2
        mock_df.__getitem__ = lambda self, key: {
            "ChatGPT": MagicMock(__iter__=lambda s: iter([100, 95])),
            "Claude AI": MagicMock(__iter__=lambda s: iter([12, 14])),
        }[key]
        mock_df.iterrows = lambda: iter([
            (datetime(2026, 4, 6), {"ChatGPT": 100, "Claude AI": 12}),
            (datetime(2026, 4, 13), {"ChatGPT": 95, "Claude AI": 14}),
        ])

        with patch("osservatorio_seo.tracker.trends_client.Trends") as MockTrends:
            mock_instance = MockTrends.return_value
            mock_instance.interest_over_time.return_value = mock_df

            client = TrendsClient(request_delay=0.0)
            keywords, points = client.fetch_interest(
                keywords=["ChatGPT", "Claude AI"],
                geo="IT",
                timeframe="today 12-m",
            )

        assert keywords == ["ChatGPT", "Claude AI"]
        assert len(points) == 2
        assert points[0]["date"] == datetime(2026, 4, 6)
        assert points[0]["values"]["ChatGPT"] == 100
        assert points[0]["values"]["Claude AI"] == 12

    def test_fetch_interest_returns_empty_on_error(self):
        with patch("osservatorio_seo.tracker.trends_client.Trends") as MockTrends:
            mock_instance = MockTrends.return_value
            mock_instance.interest_over_time.side_effect = Exception("429 Too Many Requests")

            client = TrendsClient(request_delay=0.0)
            keywords, points = client.fetch_interest(
                keywords=["ChatGPT"],
                geo="IT",
            )

        assert keywords == []
        assert points == []

    def test_default_keywords_from_yaml(self):
        client = TrendsClient.__new__(TrendsClient)
        # Test the class-level constant
        assert len(TrendsClient.DEFAULT_KEYWORDS) == 5
        assert "ChatGPT" in TrendsClient.DEFAULT_KEYWORDS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_trends_client.py -v`
Expected: ImportError for `TrendsClient`

- [ ] **Step 3: Implement TrendsClient**

Create `src/osservatorio_seo/tracker/trends_client.py`:

```python
"""Client wrapper for Google Trends via trendspy.

Provides a simple interface to fetch interest-over-time data
for AI platform keywords, with graceful error handling.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Top 5 AI platforms by relevance — Google Trends max 5 per query
DEFAULT_KEYWORDS = ["ChatGPT", "Claude AI", "Perplexity", "Gemini AI", "DeepSeek"]


class TrendsClient:
    """Wrapper around trendspy for fetching Google Trends data."""

    DEFAULT_KEYWORDS = DEFAULT_KEYWORDS

    def __init__(self, request_delay: float = 5.0) -> None:
        self._request_delay = request_delay

    def fetch_interest(
        self,
        *,
        keywords: list[str] | None = None,
        geo: str = "",
        timeframe: str = "today 12-m",
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """Fetch interest-over-time for keywords.

        Returns (keywords_list, points_list) where each point is
        {date: datetime, values: {keyword: int}}.

        On any error (rate limit, network, etc.) returns ([], []).
        """
        from trendspy import Trends

        kws = keywords or self.DEFAULT_KEYWORDS

        try:
            tr = Trends(request_delay=self._request_delay)
            df = tr.interest_over_time(kws, geo=geo, timeframe=timeframe)
        except Exception:
            logger.warning("Google Trends fetch failed for geo=%s", geo, exc_info=True)
            return [], []

        if len(df) == 0:
            return [], []

        # Filter out the 'isPartial' column if present
        value_cols = [c for c in df.columns if c != "isPartial"]
        points: list[dict[str, Any]] = []
        for date_idx, row in df.iterrows():
            dt = date_idx if isinstance(date_idx, datetime) else datetime.fromisoformat(str(date_idx))
            values = {col: int(row[col]) for col in value_cols}
            points.append({"date": dt, "values": values})

        return value_cols, points
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_trends_client.py -v`
Expected: All 3 tests pass

- [ ] **Step 5: Commit**

```bash
git add src/osservatorio_seo/tracker/trends_client.py tests/test_trends_client.py
git commit -m "feat(tracker): add TrendsClient wrapper for Google Trends data"
```

---

### Task 3: Add trendspy dependency

**Files:**
- Modify: `pyproject.toml:7-20` (dependencies list)

- [ ] **Step 1: Add trendspy to pyproject.toml**

In `pyproject.toml`, add `"trendspy>=0.1.6",` to the `dependencies` list after `"pyyaml>=6.0",`:

```toml
dependencies = [
    "feedparser>=6.0",
    "httpx>=0.27",
    "selectolax>=0.3",
    "beautifulsoup4>=4.12",
    "playwright>=1.45",
    "html2text>=2024.2",
    "pdfplumber>=0.11",
    "pydantic>=2.7",
    "pyyaml>=6.0",
    "trendspy>=0.1.6",
    "rapidfuzz>=3.9",
    "python-dateutil>=2.9",
    "jinja2>=3.1",
    "python-slugify>=8.0",
]
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from trendspy import Trends; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore(deps): add trendspy for Google Trends integration"
```

---

### Task 4: Integrate TrendsClient into TrackerCollector

**Files:**
- Modify: `src/osservatorio_seo/tracker/collector.py:22-38` (imports)
- Modify: `src/osservatorio_seo/tracker/collector.py:49-60` (constructor)
- Modify: `src/osservatorio_seo/tracker/collector.py:74-109` (collect method)
- Modify: `src/osservatorio_seo/tracker/collector.py` (add new fetch methods after line 178)
- Modify: `tests/test_tracker_collector.py`

- [ ] **Step 1: Write failing test for trends in collector**

In `tests/test_tracker_collector.py`, add import at the top:

```python
from unittest.mock import AsyncMock, MagicMock, patch
```

(Replace the existing `from unittest.mock import AsyncMock` line.)

Add a new test after `test_persist_writes_json`:

```python
@pytest.mark.asyncio
async def test_collect_includes_trends_data(mock_radar, platforms_config):
    mock_trends = MagicMock()
    mock_trends.fetch_interest.return_value = (
        ["ChatGPT", "Claude AI"],
        [
            {
                "date": datetime(2026, 4, 6, tzinfo=UTC),
                "values": {"ChatGPT": 100, "Claude AI": 12},
            },
        ],
    )

    collector = TrackerCollector(
        radar=mock_radar,
        platforms_config=platforms_config,
        trends_client=mock_trends,
    )
    snapshot = await collector.collect(year=2026, week=16)

    assert snapshot.trends_it.keywords == ["ChatGPT", "Claude AI"]
    assert len(snapshot.trends_it.points) == 1
    assert snapshot.trends_it.points[0].values["ChatGPT"] == 100
    assert mock_trends.fetch_interest.call_count == 2  # IT + global


@pytest.mark.asyncio
async def test_collect_works_without_trends_client(mock_radar, platforms_config):
    collector = TrackerCollector(radar=mock_radar, platforms_config=platforms_config)
    snapshot = await collector.collect(year=2026, week=16)

    assert snapshot.trends_it.keywords == []
    assert snapshot.trends_global.keywords == []
```

Also add these imports at the top of the file:

```python
from datetime import UTC, datetime
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tracker_collector.py::test_collect_includes_trends_data -v`
Expected: TypeError — `TrackerCollector.__init__()` got unexpected keyword argument `trends_client`

- [ ] **Step 3: Implement trends integration in collector**

In `src/osservatorio_seo/tracker/collector.py`:

Add to imports (after line 38):
```python
from osservatorio_seo.tracker.models import TrendsPoint, TrendsTimeseries
```

Modify constructor (replace lines 51-59):
```python
    def __init__(
        self,
        radar: Any,
        platforms_config: Path | None = None,
        trends_client: Any | None = None,
    ) -> None:
        self._radar = radar
        self._trends = trends_client
        self._cfg_path = platforms_config or _DEFAULT_PLATFORMS
        self._platforms: list[dict[str, str]] = self._load_platforms()
        self._warnings: list[str] = []
```

In `collect()` method, add after `os_it, os_global = await self._fetch_os_both()` (after line 85):
```python
        trends_it, trends_global = self._fetch_trends_both()
```

And add to the `TrackerSnapshot` constructor call (after `os_global=os_global,`):
```python
            trends_it=trends_it,
            trends_global=trends_global,
```

Add new section methods before the `_safe` helper (before line 317):
```python
    # ------------------------------------------------------------------
    # Section 1b: Google Trends interest data
    # ------------------------------------------------------------------

    def _fetch_trends_both(
        self,
    ) -> tuple[TrendsTimeseries, TrendsTimeseries]:
        if self._trends is None:
            return TrendsTimeseries(), TrendsTimeseries()

        it = self._fetch_trends(geo="IT")
        glb = self._fetch_trends(geo="")
        return it, glb

    def _fetch_trends(self, geo: str) -> TrendsTimeseries:
        label = f"google_trends(geo={geo or 'global'})"
        try:
            keywords, raw_points = self._trends.fetch_interest(geo=geo)
            if not keywords:
                self._warnings.append(f"{label}: no data returned")
                return TrendsTimeseries()
            points = [
                TrendsPoint(date=p["date"], values=p["values"])
                for p in raw_points
            ]
            return TrendsTimeseries(keywords=keywords, points=points)
        except Exception as exc:  # noqa: BLE001
            msg = f"{label}: {exc}"
            self._warnings.append(msg)
            logger.warning("tracker collector %s", msg)
            return TrendsTimeseries()
```

- [ ] **Step 4: Run all collector tests**

Run: `python -m pytest tests/test_tracker_collector.py -v`
Expected: All 5 tests pass (3 existing + 2 new)

- [ ] **Step 5: Commit**

```bash
git add src/osservatorio_seo/tracker/collector.py tests/test_tracker_collector.py
git commit -m "feat(tracker): integrate TrendsClient into TrackerCollector"
```

---

### Task 5: Wire TrendsClient in update_tracker.py script

**Files:**
- Modify: `scripts/update_tracker.py`

- [ ] **Step 1: Update the script to create and pass TrendsClient**

In `scripts/update_tracker.py`, add import after line 22:

```python
from osservatorio_seo.tracker.trends_client import TrendsClient
```

Modify the `main()` function — after `radar = RadarClient(api_token=token)` (line 32), add:

```python
    trends = TrendsClient(request_delay=5.0)
```

Modify the collector instantiation (line 33) to:

```python
    collector = TrackerCollector(radar=radar, trends_client=trends)
```

- [ ] **Step 2: Verify script still parses correctly**

Run: `python -c "import ast; ast.parse(open('scripts/update_tracker.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add scripts/update_tracker.py
git commit -m "feat(tracker): wire TrendsClient into weekly update script"
```

---

### Task 6: Rewrite Section 1 chart to show Google Trends data

**Files:**
- Modify: `site/tracker/tracker-charts.js:610-707` (renderSection1 function)

- [ ] **Step 1: Rewrite renderSection1()**

Replace the entire `renderSection1()` function (lines 614-707) with:

```javascript
    function renderSection1() {
      var chartEl = clearAndGet("chart-s1");
      var tableEl = clearAndGet("table-s1");
      var textEl = clearAndGet("text-s1");

      /* Chart: Google Trends interest over time */
      if (chartEl) {
        var trends = DATA.trends_it || {};
        var keywords = trends.keywords || [];
        var points = trends.points || [];

        if (keywords.length === 0 || points.length === 0) {
          noData(chartEl);
        } else {
          var series = [];
          for (var ki = 0; ki < keywords.length; ki++) {
            var kw = keywords[ki];
            var data = [];
            for (var pi = 0; pi < points.length; pi++) {
              data.push({ x: points[pi].date, y: points[pi].values[kw] || 0 });
            }
            series.push({
              label: kw,
              data: data,
              color: PALETTE[ki % PALETTE.length]
            });
          }
          var chart = renderLineChart("chart-s1", series, { yLabel: "%" });
          chartEl.appendChild(chart.svg);
          chartEl.appendChild(chart.legendContainer);
        }
      }

      /* Table: current snapshot — IT vs Global bucket from Radar + Trends rank */
      if (tableEl) {
        var trendsIT = DATA.trends_it || {};
        var trendsGL = DATA.trends_global || {};
        var kwIT = trendsIT.keywords || [];
        var ptsIT = trendsIT.points || [];
        var ptsGL = (trendsGL.points || []);

        if (kwIT.length === 0) {
          /* Fallback to old Radar bucket table if no trends data */
          var platsIT = DATA.ai_platforms_it || [];
          var platsGL = DATA.ai_platforms_global || [];
          if (platsIT.length === 0) {
            noData(tableEl);
          } else {
            var glMap = {};
            for (var i = 0; i < platsGL.length; i++) {
              glMap[platsGL[i].domain] = platsGL[i];
            }
            var thtml = '<table class="w-full text-sm font-mono">';
            thtml += '<thead><tr class="text-outline text-[10px] uppercase tracking-widest">' +
              '<th class="text-left py-1 pr-4">Piattaforma</th>' +
              '<th class="text-left py-1 pr-4">Tipo</th>' +
              '<th class="text-right py-1 pr-4">Italia</th>' +
              '<th class="text-right py-1">Mondo</th></tr></thead><tbody>';
            for (i = 0; i < platsIT.length; i++) {
              var p = platsIT[i];
              var g = glMap[p.domain] || {};
              thtml += '<tr class="border-t border-outline-variant">' +
                '<td class="py-1.5 pr-4 text-white">' + escHtml(p.label || p.domain) + '</td>' +
                '<td class="py-1.5 pr-4 text-outline">' + escHtml(p.type || "") + '</td>' +
                '<td class="py-1.5 pr-4 text-right text-primary-container">' + escHtml(formatBucket(p.rank, p.bucket)) + '</td>' +
                '<td class="py-1.5 text-right text-outline">' + escHtml(formatBucket(g.rank, g.bucket)) + '</td></tr>';
            }
            thtml += '</tbody></table>';
            tableEl.innerHTML = thtml;
          }
        } else {
          /* Trends-based table: last data point, sorted by IT interest */
          var lastIT = ptsIT[ptsIT.length - 1] || {};
          var lastGL = ptsGL.length > 0 ? ptsGL[ptsGL.length - 1] : {};
          var valuesIT = lastIT.values || {};
          var valuesGL = lastGL.values || {};

          var sorted = kwIT.slice().sort(function (a, b) {
            return (valuesIT[b] || 0) - (valuesIT[a] || 0);
          });

          var thtml = '<table class="w-full text-sm font-mono">';
          thtml += '<thead><tr class="text-outline text-[10px] uppercase tracking-widest">' +
            '<th class="text-left py-1 pr-4">Piattaforma</th>' +
            '<th class="text-right py-1 pr-4">Italia</th>' +
            '<th class="text-right py-1 pr-4">Mondo</th>' +
            '<th class="text-center py-1">Segnale</th></tr></thead><tbody>';

          for (var si = 0; si < sorted.length; si++) {
            var kw = sorted[si];
            var itVal = valuesIT[kw] || 0;
            var glVal = valuesGL[kw] || 0;
            var signal = "";
            if (glVal > itVal + 5) {
              signal = '<span class="text-[#f5a623]" title="Interesse maggiore nel mondo">&#x26A0;</span>';
            }
            thtml += '<tr class="border-t border-outline-variant">' +
              '<td class="py-1.5 pr-4 text-white">' + escHtml(kw) + '</td>' +
              '<td class="py-1.5 pr-4 text-right text-primary-container">' + itVal + '</td>' +
              '<td class="py-1.5 pr-4 text-right text-outline">' + glVal + '</td>' +
              '<td class="py-1.5 text-center">' + signal + '</td></tr>';
          }
          thtml += '</tbody></table>';
          tableEl.innerHTML = thtml;
        }
      }

      /* Text */
      if (textEl) {
        var tIT = DATA.trends_it || {};
        var tKw = tIT.keywords || [];
        var tPts = tIT.points || [];

        if (tKw.length > 0 && tPts.length > 0) {
          var lastPt = tPts[tPts.length - 1];
          var vals = lastPt.values || {};
          var bestKw = tKw[0];
          var bestVal = vals[tKw[0]] || 0;
          for (var ti = 1; ti < tKw.length; ti++) {
            if ((vals[tKw[ti]] || 0) > bestVal) {
              bestKw = tKw[ti];
              bestVal = vals[tKw[ti]] || 0;
            }
          }
          textEl.innerHTML = '<p class="text-sm text-on-surface-variant leading-relaxed">' +
            'In Italia la piattaforma AI con più interesse di ricerca è <strong class="text-white">' + escHtml(bestKw) +
            '</strong> (indice ' + bestVal + '/100). ' +
            'I valori rappresentano l\'interesse relativo di ricerca su Google (100 = picco massimo nel periodo).</p>';
        } else {
          /* Fallback to Radar-based text */
          var best = null;
          var plats = DATA.ai_platforms_it || [];
          for (var i = 0; i < plats.length; i++) {
            if (typeof plats[i].rank === "number") {
              if (!best || plats[i].rank < best.rank) best = plats[i];
            }
          }
          if (best) {
            textEl.innerHTML = '<p class="text-sm text-on-surface-variant leading-relaxed">' +
              'La piattaforma AI più popolare in Italia è <strong class="text-white">' + escHtml(best.label || best.domain) +
              '</strong> (posizione #' + best.rank + '). ' +
              'Il ranking misura la popolarità come sito di destinazione, non il traffico referral verso altri siti.</p>';
          }
        }
      }
    }
```

- [ ] **Step 2: Verify JS syntax is valid**

Run: `node -c site/tracker/tracker-charts.js`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add site/tracker/tracker-charts.js
git commit -m "feat(tracker): rewrite Section 1 chart to show Google Trends data"
```

---

### Task 7: Update Section 1 template text and methodology

**Files:**
- Modify: `templates/pages/tracker.html.jinja` (Section 1 details text + methodology)

- [ ] **Step 1: Update the Section 1 "Perché lo monitoriamo" text**

In `templates/pages/tracker.html.jinja`, find the Section 1 `<details>` content (around line 37-40) and replace the `<p>` inside with:

```html
      <p>Per fare SEO nell'era dell'AI, serve sapere dove vanno gli utenti. Il grafico mostra l'interesse di ricerca relativo su Google per le principali piattaforme AI, misurato da Google Trends (indice 0-100, dove 100 &egrave; il picco massimo nel periodo). Confrontando Italia e Mondo si possono anticipare i trend: i mercati anglofoni adottano prima, l'Italia segue di qualche mese.</p>
```

- [ ] **Step 2: Update the methodology section (Section 10)**

In the methodology details section, find the data source text and add a note about Google Trends. Look for "Cloudflare Radar API" mention in the methodology and add after it:

```html
          <li><strong>Sezione 1 (popolarit&agrave; AI):</strong> dati Google Trends (indice di interesse relativo 0-100). Fonte aggiuntiva rispetto a Cloudflare Radar.</li>
```

- [ ] **Step 3: Commit**

```bash
git add templates/pages/tracker.html.jinja
git commit -m "docs(tracker): update Section 1 methodology for Google Trends data"
```

---

### Task 8: Run full test suite and verify

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Run linter**

Run: `python -m ruff check src/osservatorio_seo/tracker/ tests/test_trends_client.py tests/test_tracker_collector.py tests/test_tracker_models.py`
Expected: No errors

- [ ] **Step 3: Verify backward compatibility with existing snapshot**

Run: `python -c "from osservatorio_seo.tracker.models import TrackerSnapshot; s = TrackerSnapshot.model_validate_json(open('data/tracker/snapshots/2026-W16.json').read()); print('Schema:', s.schema_version); print('Trends IT keywords:', s.trends_it.keywords); print('Top10 IT:', len(s.top10_it), 'domains')"`
Expected: Schema 3.0, empty trends, existing data intact

- [ ] **Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix(tracker): address lint/test issues from Google Trends integration"
```
