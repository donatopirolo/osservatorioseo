"""SVG chart generators for the tracker dashboard.

Each public function takes a typed pydantic model and returns a self-
contained SVG string. The SVGs are inlined into ``tracker.html.jinja``
via ``|safe`` and styled by the existing CSS theme (terminal retro
green-on-black), so we avoid hardcoding ``font-family``.

All charts use ``viewBox`` + ``preserveAspectRatio`` for responsive
rendering on mobile. Max width typically 700px, height scaled.
"""

from __future__ import annotations

from osservatorio_seo.tracker.models import (
    AnalyticsReferrer,
    Big4PanelData,
    BumpChartData,
    CategoryHeatmapRow,
    IndexTimeseries,
    MarketCompositionPoint,
    TopMovers,
)

# Theme colors (keep in sync with tailwind_input.css)
PRIMARY_GREEN = "#00f63e"
ACCENT_ORANGE = "#f5a623"
OUTLINE_GREY = "#919191"
OUTLINE_VARIANT = "#474747"
BG_DARK = "#0e0e0e"
ON_SURFACE = "#e2e2e2"


def _empty_svg(message: str = "Nessun dato disponibile") -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 60" '
        'role="img" aria-label="chart placeholder">'
        f'<rect width="700" height="60" fill="{BG_DARK}"/>'
        f'<text x="350" y="35" text-anchor="middle" fill="{OUTLINE_GREY}" '
        f'font-size="12" font-family="monospace">{message}</text>'
        "</svg>"
    )


def _normalize_to_100(points) -> list[float]:
    """Rescale a list of TimeseriesPoint values so the first = 100."""
    if not points:
        return []
    base = points[0].value or 1.0
    return [round(p.value / base * 100, 2) for p in points]


def _polyline_points(xs: list[float], ys: list[float]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys, strict=False))


# ---------------------------------------------------------------------------
# Chart 1: AI vs Internet in Italia (dual line, 24 months)
# ---------------------------------------------------------------------------


def render_ai_vs_internet_chart(
    ai: IndexTimeseries,
    internet: IndexTimeseries,
) -> str:
    """Chart 1: dual-line showing AI index vs total internet index over 24mo."""
    if not ai.points or not internet.points:
        return _empty_svg("Nessun dato disponibile — AI vs Internet")

    width, height = 700, 320
    margin_x, margin_y = 60, 40
    inner_w = width - 2 * margin_x
    inner_h = height - 2 * margin_y

    ai_norm = _normalize_to_100(ai.points)
    int_norm = _normalize_to_100(internet.points)

    all_values = ai_norm + int_norm
    y_max = max(all_values) * 1.1
    y_min = min(all_values) * 0.9

    def scale_y(v: float) -> float:
        return margin_y + inner_h * (1 - (v - y_min) / (y_max - y_min))

    def scale_x(i: int, n: int) -> float:
        return margin_x + (inner_w * i / max(n - 1, 1))

    ai_xs = [scale_x(i, len(ai_norm)) for i in range(len(ai_norm))]
    ai_ys = [scale_y(v) for v in ai_norm]
    int_xs = [scale_x(i, len(int_norm)) for i in range(len(int_norm))]
    int_ys = [scale_y(v) for v in int_norm]

    ai_poly = _polyline_points(ai_xs, ai_ys)
    int_poly = _polyline_points(int_xs, int_ys)

    # Y-axis gridlines
    y_ticks = [y_min + (y_max - y_min) * t / 4 for t in range(5)]
    grid_lines = ""
    y_labels = ""
    for yt in y_ticks:
        y = scale_y(yt)
        grid_lines += (
            f'<line x1="{margin_x}" y1="{y:.1f}" x2="{width - margin_x}" y2="{y:.1f}" '
            f'stroke="{OUTLINE_VARIANT}" stroke-dasharray="2,3" stroke-width="1"/>'
        )
        y_labels += (
            f'<text x="{margin_x - 8}" y="{y + 3:.1f}" text-anchor="end" '
            f'fill="{OUTLINE_GREY}" font-size="10" font-family="monospace">'
            f"{int(yt)}</text>"
        )

    ai_last_label = (
        f'<text x="{ai_xs[-1] + 6:.1f}" y="{ai_ys[-1] + 4:.1f}" '
        f'fill="{PRIMARY_GREEN}" font-size="11" font-family="monospace" '
        f'font-weight="bold">AI (Italia)</text>'
    )
    int_last_label = (
        f'<text x="{int_xs[-1] + 6:.1f}" y="{int_ys[-1] + 4:.1f}" '
        f'fill="{OUTLINE_GREY}" font-size="11" font-family="monospace">'
        f"Internet tot.</text>"
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="AI vs Internet, trend 24 mesi Italia" '
        f'preserveAspectRatio="xMidYMid meet">'
        f'<rect width="{width}" height="{height}" fill="{BG_DARK}"/>'
        f"{grid_lines}"
        f"{y_labels}"
        f'<polyline points="{int_poly}" fill="none" stroke="{OUTLINE_GREY}" '
        f'stroke-width="2" stroke-linejoin="round"/>'
        f'<polyline points="{ai_poly}" fill="none" stroke="{PRIMARY_GREEN}" '
        f'stroke-width="2.5" stroke-linejoin="round"/>'
        f"{int_last_label}"
        f"{ai_last_label}"
        "</svg>"
    )


# ---------------------------------------------------------------------------
# Chart 2: Market composition — stacked area (Google / other-search / AI)
# ---------------------------------------------------------------------------


def render_market_composition_chart(
    points: list[MarketCompositionPoint],
) -> str:
    """Chart 2: stacked area showing Google / other-search / AI share over 12mo."""
    if not points:
        return _empty_svg("Nessun dato disponibile — composizione mercato")

    width, height = 700, 320
    margin_x, margin_y = 60, 40
    inner_w = width - 2 * margin_x
    inner_h = height - 2 * margin_y

    n = len(points)

    def scale_x(i: int) -> float:
        return margin_x + (inner_w * i / max(n - 1, 1))

    def scale_y(v: float) -> float:
        return margin_y + inner_h * (1 - v)

    google_tops = [p.google_share for p in points]
    other_tops = [p.google_share + p.other_search_share for p in points]
    all_tops = [p.google_share + p.other_search_share + p.ai_share for p in points]

    def polygon_for(lows: list[float], tops: list[float]) -> str:
        pts_top = " ".join(f"{scale_x(i):.1f},{scale_y(v):.1f}" for i, v in enumerate(tops))
        pts_low = " ".join(
            f"{scale_x(i):.1f},{scale_y(v):.1f}" for i, v in list(enumerate(lows))[::-1]
        )
        return pts_top + " " + pts_low

    zeros = [0.0] * n

    google_pts = polygon_for(zeros, google_tops)
    other_pts = polygon_for(google_tops, other_tops)
    ai_pts = polygon_for(other_tops, all_tops)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="Composizione mercato search e AI Italia, 12 mesi" '
        f'preserveAspectRatio="xMidYMid meet">'
        f'<rect width="{width}" height="{height}" fill="{BG_DARK}"/>'
        f'<polygon points="{google_pts}" fill="{PRIMARY_GREEN}" fill-opacity="0.55" stroke="{PRIMARY_GREEN}" stroke-width="1"/>'
        f'<polygon points="{other_pts}" fill="{OUTLINE_GREY}" fill-opacity="0.55" stroke="{OUTLINE_GREY}" stroke-width="1"/>'
        f'<polygon points="{ai_pts}" fill="{ACCENT_ORANGE}" fill-opacity="0.65" stroke="{ACCENT_ORANGE}" stroke-width="1"/>'
        f'<text x="{margin_x}" y="{margin_y - 8}" fill="{PRIMARY_GREEN}" font-size="11" font-family="monospace">\u25a0 Google</text>'
        f'<text x="{margin_x + 90}" y="{margin_y - 8}" fill="{OUTLINE_GREY}" font-size="11" font-family="monospace">\u25a0 Altri search</text>'
        f'<text x="{margin_x + 220}" y="{margin_y - 8}" fill="{ACCENT_ORANGE}" font-size="11" font-family="monospace">\u25a0 AI services</text>'
        "</svg>"
    )


# ---------------------------------------------------------------------------
# Chart 3: Bump chart — top 10 AI domains, 6 months
# ---------------------------------------------------------------------------

_BUMP_PALETTE = [
    "#00f63e",  # primary green
    "#f5a623",  # accent orange
    "#2ec4f1",  # cyan
    "#f040ff",  # magenta
    "#ffeb3b",  # yellow
    "#ff5252",  # red
    "#00e5bf",  # teal
    "#b388ff",  # violet
    "#ff80ab",  # pink
    "#a4de02",  # lime
]


def render_bump_chart(data: BumpChartData) -> str:
    """Chart 3: bump chart showing rank trajectories of top 10 AI domains."""
    if not data.weeks or not data.domains:
        return _empty_svg("Nessun dato disponibile — bump chart AI")

    width, height = 700, 380
    margin_x, margin_y = 90, 40
    inner_w = width - 2 * margin_x
    inner_h = height - 2 * margin_y

    max_rank = 10
    n_weeks = len(data.weeks)

    def scale_x(i: int) -> float:
        return margin_x + (inner_w * i / max(n_weeks - 1, 1))

    def scale_y(rank: int) -> float:
        return margin_y + inner_h * ((rank - 1) / (max_rank - 1))

    grid = ""
    for r in range(1, max_rank + 1):
        y = scale_y(r)
        grid += (
            f'<line x1="{margin_x}" y1="{y:.1f}" x2="{width - margin_x}" y2="{y:.1f}" '
            f'stroke="{OUTLINE_VARIANT}" stroke-dasharray="2,4" stroke-width="0.5"/>'
            f'<text x="{margin_x - 8}" y="{y + 3:.1f}" text-anchor="end" fill="{OUTLINE_GREY}" '
            f'font-size="10" font-family="monospace">#{r}</text>'
        )

    polylines = ""
    labels = ""
    for idx, domain in enumerate(data.domains[:max_rank]):
        color = _BUMP_PALETTE[idx % len(_BUMP_PALETTE)]
        pts = []
        for week_i, week in enumerate(data.weeks):
            rank = week.ranks.get(domain)
            if rank is None or rank > max_rank:
                continue
            pts.append((scale_x(week_i), scale_y(rank)))
        if not pts:
            continue
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        polylines += (
            f'<polyline points="{poly}" fill="none" stroke="{color}" '
            f'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
        )
        last_x, last_y = pts[-1]
        labels += (
            f'<text x="{last_x + 5:.1f}" y="{last_y + 3:.1f}" fill="{color}" '
            f'font-size="10" font-family="monospace">{domain}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="Bump chart top 10 AI Italia, 6 mesi" '
        f'preserveAspectRatio="xMidYMid meet">'
        f'<rect width="{width}" height="{height}" fill="{BG_DARK}"/>'
        f"{grid}"
        f"{polylines}"
        f"{labels}"
        "</svg>"
    )


# ---------------------------------------------------------------------------
# Chart 4: Category heatmap (6 months x N categories)
# ---------------------------------------------------------------------------


def _heatmap_color(delta_pct: float | None) -> str:
    if delta_pct is None:
        return OUTLINE_VARIANT
    if delta_pct > 10:
        return "#00f63e"  # strong growth
    if delta_pct > 3:
        return "#82e5a3"  # moderate growth
    if delta_pct >= -3:
        return "#5a5a5a"  # stable
    if delta_pct >= -10:
        return "#f5a623"  # moderate decline
    return "#ff5252"  # strong decline


def render_category_heatmap(rows: list[CategoryHeatmapRow]) -> str:
    """Chart 4: heatmap showing traffic % change per category per month."""
    if not rows:
        return _empty_svg("Nessun dato disponibile — heatmap categorie")

    cell_w, cell_h = 80, 32
    label_w = 140
    header_h = 30
    margin_x, margin_y = 20, 20

    months = rows[0].cells
    n_cols = len(months)
    n_rows = len(rows)

    width = margin_x * 2 + label_w + cell_w * n_cols + 40
    height = margin_y * 2 + header_h + cell_h * n_rows + 40

    header = ""
    for i, m in enumerate(months):
        x = margin_x + label_w + i * cell_w + cell_w / 2
        y = margin_y + header_h - 8
        header += (
            f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" '
            f'fill="{OUTLINE_GREY}" font-size="10" font-family="monospace">{m.month}</text>'
        )

    body = ""
    for ri, row in enumerate(rows):
        y_label = margin_y + header_h + ri * cell_h + cell_h / 2 + 4
        body += (
            f'<text x="{margin_x + label_w - 10:.1f}" y="{y_label:.1f}" '
            f'text-anchor="end" fill="{ON_SURFACE}" font-size="11" '
            f'font-family="monospace">{row.category}</text>'
        )
        for ci, cell in enumerate(row.cells):
            x = margin_x + label_w + ci * cell_w
            y = margin_y + header_h + ri * cell_h
            color = _heatmap_color(cell.delta_pct)
            body += (
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_w - 2}" height="{cell_h - 2}" '
                f'fill="{color}" fill-opacity="0.7"/>'
            )
            if cell.delta_pct is not None:
                label = f"{cell.delta_pct:+.1f}%"
                body += (
                    f'<text x="{x + cell_w / 2:.1f}" y="{y + cell_h / 2 + 4:.1f}" '
                    f'text-anchor="middle" fill="{BG_DARK}" font-size="10" '
                    f'font-family="monospace" font-weight="bold">{label}</text>'
                )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="Heatmap traffico per categoria Italia, 6 mesi" '
        f'preserveAspectRatio="xMidYMid meet">'
        f'<rect width="{width}" height="{height}" fill="{BG_DARK}"/>'
        f"{header}"
        f"{body}"
        "</svg>"
    )


# ---------------------------------------------------------------------------
# Chart 5: Biggest movers — dual horizontal bar chart (30d)
# ---------------------------------------------------------------------------


def render_movers_chart(movers: TopMovers) -> str:
    """Chart 5: dual horizontal bar chart — biggest movers (up/down) 30d."""
    if not movers.up and not movers.down:
        return _empty_svg("Nessun mover significativo questa settimana")

    width, height = 700, 280
    col_w = (width - 60) / 2
    margin_x = 20
    bar_h = 22
    row_gap = 8
    label_w = 140

    all_abs = [abs(m.delta_pct) for m in (*movers.up, *movers.down)]
    max_abs = max(all_abs) if all_abs else 1.0

    def bar_width(pct: float) -> float:
        return (col_w - label_w - 60) * (abs(pct) / max_abs)

    body = ""
    # Up column (left)
    body += (
        f'<text x="{margin_x + 10}" y="30" fill="{PRIMARY_GREEN}" font-size="12" '
        f'font-family="monospace" font-weight="bold">\u2191 SALITI</text>'
    )
    for i, m in enumerate(movers.up[:5]):
        y = 50 + i * (bar_h + row_gap)
        bw = bar_width(m.delta_pct)
        body += (
            f'<text x="{margin_x + 10}" y="{y + bar_h / 2 + 4:.1f}" '
            f'fill="{ON_SURFACE}" font-size="11" font-family="monospace">{m.domain}</text>'
            f'<rect x="{margin_x + label_w}" y="{y}" width="{bw:.1f}" height="{bar_h}" '
            f'fill="{PRIMARY_GREEN}" fill-opacity="0.75"/>'
            f'<text x="{margin_x + label_w + bw + 6:.1f}" y="{y + bar_h / 2 + 4:.1f}" '
            f'fill="{PRIMARY_GREEN}" font-size="11" font-family="monospace" font-weight="bold">'
            f"+{m.delta_pct:.1f}%</text>"
        )

    # Down column (right)
    col2_x = margin_x + col_w + 30
    body += (
        f'<text x="{col2_x + 10}" y="30" fill="{ACCENT_ORANGE}" font-size="12" '
        f'font-family="monospace" font-weight="bold">\u2193 SCESI</text>'
    )
    for i, m in enumerate(movers.down[:5]):
        y = 50 + i * (bar_h + row_gap)
        bw = bar_width(m.delta_pct)
        body += (
            f'<text x="{col2_x + 10}" y="{y + bar_h / 2 + 4:.1f}" '
            f'fill="{ON_SURFACE}" font-size="11" font-family="monospace">{m.domain}</text>'
            f'<rect x="{col2_x + label_w}" y="{y}" width="{bw:.1f}" height="{bar_h}" '
            f'fill="{ACCENT_ORANGE}" fill-opacity="0.75"/>'
            f'<text x="{col2_x + label_w + bw + 6:.1f}" y="{y + bar_h / 2 + 4:.1f}" '
            f'fill="{ACCENT_ORANGE}" font-size="11" font-family="monospace" font-weight="bold">'
            f"{m.delta_pct:.1f}%</text>"
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="Biggest movers AI Italia, ultimi 30 giorni" '
        f'preserveAspectRatio="xMidYMid meet">'
        f'<rect width="{width}" height="{height}" fill="{BG_DARK}"/>'
        f"{body}"
        "</svg>"
    )


# ---------------------------------------------------------------------------
# Chart 6: Big 4 AI — small multiples 2x2
# ---------------------------------------------------------------------------


def render_big4_small_multiples(panels: list[Big4PanelData]) -> str:
    """Chart 6: 2x2 small multiples of traffic index for the 4 big AI services."""
    if not panels:
        return _empty_svg("Nessun dato disponibile — big 4 AI")

    width, height = 700, 400
    panel_w = (width - 60) / 2
    panel_h = (height - 80) / 2
    margin = 20

    rendered_panels = ""
    for idx, panel in enumerate(panels[:4]):
        col = idx % 2
        row = idx // 2
        px = margin + col * (panel_w + 20)
        py = margin + row * (panel_h + 40)

        rendered_panels += _render_single_big4_panel(panel=panel, x=px, y=py, w=panel_w, h=panel_h)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="Big 4 AI trend 6 mesi" '
        f'preserveAspectRatio="xMidYMid meet">'
        f'<rect width="{width}" height="{height}" fill="{BG_DARK}"/>'
        f"{rendered_panels}"
        "</svg>"
    )


def _render_single_big4_panel(
    panel: Big4PanelData,
    x: float,
    y: float,
    w: float,
    h: float,
) -> str:
    ts = panel.traffic_timeseries
    inner_x = x + 8
    inner_y = y + 40
    inner_w = w - 16
    inner_h = h - 60

    if not ts:
        return (
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" '
            f'stroke="{OUTLINE_VARIANT}" stroke-dasharray="3,3"/>'
            f'<text x="{x + w / 2}" y="{y + h / 2}" text-anchor="middle" '
            f'fill="{OUTLINE_GREY}" font-size="11" font-family="monospace">no data</text>'
        )

    values = [p.value for p in ts]
    v_max = max(values) or 1.0
    v_min = min(values)

    def sx(i: int) -> float:
        return inner_x + inner_w * i / max(len(ts) - 1, 1)

    def sy(v: float) -> float:
        span = v_max - v_min or 1.0
        return inner_y + inner_h * (1 - (v - v_min) / span)

    poly = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(values))

    rank_now = f"#{panel.current_rank}"
    rank_old = f"(era #{panel.previous_rank})" if panel.previous_rank else ""
    title = (
        f"{panel.display_name}: da #{panel.previous_rank} a #{panel.current_rank}"
        if panel.previous_rank
        else f"{panel.display_name}: rank #{panel.current_rank}"
    )

    return (
        f"<g>"
        f'<text x="{x + 8}" y="{y + 20}" fill="{ON_SURFACE}" font-size="12" '
        f'font-family="monospace" font-weight="bold">{title}</text>'
        f'<text x="{x + w - 8}" y="{y + 20}" text-anchor="end" '
        f'fill="{PRIMARY_GREEN}" font-size="18" font-family="monospace" font-weight="bold">'
        f"{rank_now}</text>"
        f'<text x="{x + w - 8}" y="{y + 34}" text-anchor="end" '
        f'fill="{OUTLINE_GREY}" font-size="10" font-family="monospace">{rank_old}</text>'
        f'<polyline points="{poly}" fill="none" stroke="{PRIMARY_GREEN}" '
        f'stroke-width="2" stroke-linejoin="round"/>'
        f"</g>"
    )


# ---------------------------------------------------------------------------
# Chart 7: Own referrers — horizontal bar chart
# ---------------------------------------------------------------------------


def render_own_referrers_chart(refs: list[AnalyticsReferrer]) -> str:
    """Chart 7: single horizontal bar chart of own-site referrer share."""
    if not refs:
        return _empty_svg("Nessun dato — referrer OsservatorioSEO")

    width = 700
    bar_h = 26
    row_gap = 8
    margin_x, margin_y = 20, 20
    label_w = 110
    value_w = 70
    bar_max_w = width - margin_x * 2 - label_w - value_w

    n = len(refs)
    height = margin_y * 2 + n * (bar_h + row_gap)

    max_pct = max(r.share_pct for r in refs) or 1.0

    body = ""
    for i, ref in enumerate(refs):
        y = margin_y + i * (bar_h + row_gap)
        bw = bar_max_w * (ref.share_pct / max_pct)
        body += (
            f'<text x="{margin_x + 10}" y="{y + bar_h / 2 + 4:.1f}" '
            f'fill="{ON_SURFACE}" font-size="11" font-family="monospace">{ref.source}</text>'
            f'<rect x="{margin_x + label_w}" y="{y}" width="{bw:.1f}" height="{bar_h}" '
            f'fill="{PRIMARY_GREEN}" fill-opacity="0.75"/>'
            f'<text x="{margin_x + label_w + bw + 6:.1f}" y="{y + bar_h / 2 + 4:.1f}" '
            f'fill="{PRIMARY_GREEN}" font-size="11" font-family="monospace" font-weight="bold">'
            f"{ref.share_pct:.1f}%</text>"
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="Referrer source OsservatorioSEO, ultimi 30 giorni" '
        f'preserveAspectRatio="xMidYMid meet">'
        f'<rect width="{width}" height="{height}" fill="{BG_DARK}"/>'
        f"{body}"
        "</svg>"
    )
