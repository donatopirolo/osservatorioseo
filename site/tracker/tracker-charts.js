/* tracker-charts.js — vanilla JS chart engine for OsservatorioSEO Tracker v2 */
(function () {
  "use strict";

  const DATA = window.__TRACKER_DATA__;
  if (!DATA) return;

  const COLORS = [
    "#00f63e", "#f5a623", "#e24c4c", "#4ca6e2", "#e24ce2",
    "#4ce2c4", "#e2e24c", "#a64cf5", "#f54c8a", "#8af54c"
  ];
  const PURPOSE_COLORS = {
    "User Action": "#00f63e",
    "Training": "#e24c4c",
    "Mixed": "#f5a623",
    "Search": "#4ca6e2",
    "Undeclared": "#919191"
  };
  const GRID_COLOR = "#333";
  const LABEL_COLOR = "#919191";
  const NS = "http://www.w3.org/2000/svg";

  /* ── State ── */
  let view = localStorage.getItem("tracker_view") || "it";

  function suffix() { return view === "it" ? "_it" : "_global"; }
  function otherSuffix() { return view === "it" ? "_global" : "_it"; }

  /* ── SVG helpers ── */
  function svgEl(tag, attrs) {
    const el = document.createElementNS(NS, tag);
    if (attrs) Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
    return el;
  }

  function makeSvg(w, h) {
    const svg = svgEl("svg", {
      viewBox: "0 0 " + w + " " + h,
      preserveAspectRatio: "xMidYMid meet"
    });
    svg.classList.add("w-full");
    return svg;
  }

  function drawGrid(svg, x0, y0, x1, y1, hLines, labels, invert) {
    const g = svgEl("g");
    for (let i = 0; i <= hLines; i++) {
      const y = y0 + (y1 - y0) * i / hLines;
      g.appendChild(svgEl("line", {
        x1: x0, y1: y, x2: x1, y2: y, stroke: GRID_COLOR, "stroke-width": "0.5"
      }));
      if (labels) {
        const val = invert
          ? Math.round(labels.min + (labels.max - labels.min) * i / hLines)
          : Math.round(labels.max - (labels.max - labels.min) * i / hLines);
        const txt = svgEl("text", {
          x: x0 - 6, y: y + 3, fill: LABEL_COLOR, "font-size": "10",
          "text-anchor": "end", "font-family": "monospace"
        });
        txt.textContent = val;
        g.appendChild(txt);
      }
    }
    return g;
  }

  function drawXLabels(svg, x0, x1, y, dates, maxLabels) {
    const g = svgEl("g");
    const n = dates.length;
    if (n === 0) return g;
    const step = Math.max(1, Math.floor(n / (maxLabels || 6)));
    for (let i = 0; i < n; i += step) {
      const x = x0 + (x1 - x0) * i / (n - 1 || 1);
      const txt = svgEl("text", {
        x: x, y: y, fill: LABEL_COLOR, "font-size": "10",
        "text-anchor": "middle", "font-family": "monospace"
      });
      const d = dates[i];
      txt.textContent = d ? d.slice(5, 10) : "";
      g.appendChild(txt);
    }
    return g;
  }

  function buildLegend(items, toggleCb) {
    const div = document.createElement("div");
    div.className = "flex flex-wrap gap-3 mt-3 text-sm font-mono";
    items.forEach((item, idx) => {
      const btn = document.createElement("button");
      btn.className = "flex items-center gap-1.5 opacity-100 transition-opacity";
      btn.dataset.idx = idx;
      const dot = document.createElement("span");
      dot.style.cssText = "display:inline-block;width:10px;height:10px;border-radius:2px;background:" + item.color;
      btn.appendChild(dot);
      const label = document.createElement("span");
      label.style.color = item.color;
      label.textContent = item.label;
      btn.appendChild(label);
      btn.addEventListener("click", function () {
        item.visible = !item.visible;
        btn.style.opacity = item.visible ? "1" : "0.3";
        toggleCb(idx, item.visible);
      });
      div.appendChild(btn);
    });
    return div;
  }

  /* ── Toggle buttons ── */
  function initToggle() {
    const btns = document.querySelectorAll("[data-view-toggle]");
    btns.forEach(function (btn) {
      const v = btn.dataset.viewToggle;
      if (v === view) {
        btn.classList.add("active");
        btn.classList.remove("border-outline-variant", "text-outline");
        btn.classList.add("border-primary-container", "text-primary-container");
      } else {
        btn.classList.remove("active", "border-primary-container", "text-primary-container");
        btn.classList.add("border-outline-variant", "text-outline");
      }
      btn.addEventListener("click", function () {
        if (v === view) return;
        view = v;
        localStorage.setItem("tracker_view", view);
        initToggle();
        renderAll();
      });
    });
  }

  /* ══════════════════════════════════════════
     Section 1: Top 10 line chart + table
     ══════════════════════════════════════════ */
  function renderTop10() {
    const container = document.getElementById("chart-top10");
    const tableContainer = document.getElementById("table-top10");
    if (!container) return;

    const data = DATA["top10" + suffix()];
    if (!data || data.length === 0) {
      container.innerHTML = '<p class="text-outline font-mono text-sm">Dati non disponibili.</p>';
      if (tableContainer) tableContainer.innerHTML = "";
      return;
    }

    container.innerHTML = "";
    if (tableContainer) tableContainer.innerHTML = "";

    const W = 700, H = 320, pad = { t: 20, r: 20, b: 40, l: 50 };
    const x0 = pad.l, x1 = W - pad.r, y0 = pad.t, y1 = H - pad.b;

    /* Determine date axis from first domain with timeseries */
    let dates = [];
    for (const d of data) {
      if (d.timeseries && d.timeseries.length > 0) {
        dates = d.timeseries.map(function (p) { return p.date; });
        break;
      }
    }
    const n = dates.length || 1;

    /* Y range: rank 1 at top, max at bottom */
    let maxRank = 10;
    data.forEach(function (d) {
      if (d.timeseries) d.timeseries.forEach(function (p) {
        if (p.value > maxRank) maxRank = Math.ceil(p.value);
      });
    });

    const svg = makeSvg(W, H);
    svg.appendChild(drawGrid(svg, x0, y0, x1, y1, 5, { min: 1, max: maxRank }, true));
    svg.appendChild(drawXLabels(svg, x0, x1, y1 + 20, dates, 6));

    /* Lines */
    const lines = [];
    data.forEach(function (d, idx) {
      if (!d.timeseries || d.timeseries.length === 0) return;
      const color = COLORS[idx % COLORS.length];
      let pts = "";
      d.timeseries.forEach(function (p, i) {
        const px = x0 + (x1 - x0) * i / (n - 1 || 1);
        const py = y0 + (y1 - y0) * (p.value - 1) / (maxRank - 1 || 1);
        pts += (i === 0 ? "M" : "L") + px.toFixed(1) + "," + py.toFixed(1);
      });
      const path = svgEl("path", {
        d: pts, fill: "none", stroke: color, "stroke-width": "2", "stroke-linejoin": "round"
      });
      path.dataset.idx = idx;
      svg.appendChild(path);
      lines.push({ label: d.domain, color: color, visible: true, el: path });
    });

    container.appendChild(svg);

    /* Legend */
    const legend = buildLegend(lines, function (idx, vis) {
      lines[idx].el.style.display = vis ? "" : "none";
    });
    container.appendChild(legend);

    /* Table */
    if (tableContainer) {
      const table = document.createElement("table");
      table.className = "w-full text-sm font-mono";
      const thead = document.createElement("thead");
      thead.innerHTML = '<tr class="text-outline text-[10px] uppercase tracking-widest">' +
        '<th class="text-left py-1 pr-4">#</th>' +
        '<th class="text-left py-1 pr-4">Dominio</th>' +
        '<th class="text-left py-1">Categorie</th></tr>';
      table.appendChild(thead);
      const tbody = document.createElement("tbody");
      data.forEach(function (d) {
        const tr = document.createElement("tr");
        tr.className = "border-t border-outline-variant";
        tr.innerHTML =
          '<td class="py-1.5 pr-4 text-primary-container">' + d.rank + '</td>' +
          '<td class="py-1.5 pr-4 text-white">' + escHtml(d.domain) + '</td>' +
          '<td class="py-1.5 text-outline">' + escHtml((d.categories || []).join(", ")) + '</td>';
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      tableContainer.appendChild(table);
    }
  }

  /* ══════════════════════════════════════════
     Section 2: AI Platforms table
     ══════════════════════════════════════════ */
  function renderPlatforms() {
    const container = document.getElementById("chart-platforms");
    if (!container) return;

    const data = DATA["ai_platforms" + suffix()];
    const other = DATA["ai_platforms" + otherSuffix()];
    if (!data || data.length === 0) {
      container.innerHTML = '<p class="text-outline font-mono text-sm">Dati non disponibili.</p>';
      return;
    }

    container.innerHTML = "";

    /* Build lookup for other view */
    const otherMap = {};
    if (other) other.forEach(function (p) { otherMap[p.domain] = p; });

    const otherLabel = view === "it" ? "Mondo" : "Italia";

    const table = document.createElement("table");
    table.className = "w-full text-sm font-mono";
    const thead = document.createElement("thead");
    thead.innerHTML = '<tr class="text-outline text-[10px] uppercase tracking-widest">' +
      '<th class="text-left py-1 pr-4">Piattaforma</th>' +
      '<th class="text-left py-1 pr-4">Tipo</th>' +
      '<th class="text-right py-1 pr-4">Rank</th>' +
      '<th class="text-right py-1 pr-4">Bucket</th>' +
      '<th class="text-right py-1">Bucket ' + escHtml(otherLabel) + '</th></tr>';
    table.appendChild(thead);
    const tbody = document.createElement("tbody");
    data.forEach(function (p) {
      const o = otherMap[p.domain];
      const tr = document.createElement("tr");
      tr.className = "border-t border-outline-variant";
      tr.innerHTML =
        '<td class="py-1.5 pr-4 text-white">' + escHtml(p.label || p.domain) + '</td>' +
        '<td class="py-1.5 pr-4 text-outline">' + escHtml(p.type || "") + '</td>' +
        '<td class="py-1.5 pr-4 text-right text-primary-container">' + (p.rank != null ? p.rank : "—") + '</td>' +
        '<td class="py-1.5 pr-4 text-right text-outline">' + escHtml(p.bucket || "—") + '</td>' +
        '<td class="py-1.5 text-right text-outline-variant">' + escHtml(o ? (o.bucket || "—") : "—") + '</td>';
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    container.appendChild(table);
  }

  /* ══════════════════════════════════════════
     Section 3: Bot vs Human area chart
     ══════════════════════════════════════════ */
  function renderBotHuman() {
    const container = document.getElementById("chart-bot-human");
    if (!container) return;

    const raw = DATA["bot_human" + suffix()];
    if (!raw || !raw.points || raw.points.length === 0) {
      container.innerHTML = '<p class="text-outline font-mono text-sm">Dati non disponibili.</p>';
      return;
    }

    container.innerHTML = "";

    const points = raw.points;
    const W = 700, H = 280, pad = { t: 20, r: 20, b: 40, l: 50 };
    const x0 = pad.l, x1 = W - pad.r, y0 = pad.t, y1 = H - pad.b;
    const n = points.length;

    const svg = makeSvg(W, H);
    svg.appendChild(drawGrid(svg, x0, y0, x1, y1, 5, { min: 0, max: 100 }, false));
    svg.appendChild(drawXLabels(svg, x0, x1, y1 + 20, points.map(function (p) { return p.date; }), 6));

    /* Bot area (orange) */
    let areaPath = "";
    let linePath = "";
    points.forEach(function (p, i) {
      const px = x0 + (x1 - x0) * i / (n - 1 || 1);
      const py = y0 + (y1 - y0) * (1 - p.bot_pct / 100);
      linePath += (i === 0 ? "M" : "L") + px.toFixed(1) + "," + py.toFixed(1);
      areaPath += (i === 0 ? "M" : "L") + px.toFixed(1) + "," + py.toFixed(1);
    });
    /* Close area down to baseline */
    areaPath += "L" + x1.toFixed(1) + "," + y1 + "L" + x0.toFixed(1) + "," + y1 + "Z";

    svg.appendChild(svgEl("path", {
      d: areaPath, fill: "#f5a623", "fill-opacity": "0.25", stroke: "none"
    }));
    svg.appendChild(svgEl("path", {
      d: linePath, fill: "none", stroke: "#f5a623", "stroke-width": "2"
    }));

    /* Label */
    const lastPt = points[n - 1];
    const labelY = y0 + (y1 - y0) * (1 - lastPt.bot_pct / 100);
    const lbl = svgEl("text", {
      x: x1 - 4, y: labelY - 8, fill: "#f5a623", "font-size": "11",
      "text-anchor": "end", "font-family": "monospace"
    });
    lbl.textContent = "Bot " + lastPt.bot_pct.toFixed(1) + "%";
    svg.appendChild(lbl);

    container.appendChild(svg);
  }

  /* ══════════════════════════════════════════
     Section 4a: AI Bots by user-agent
     ══════════════════════════════════════════ */
  function renderAiBots() {
    const container = document.getElementById("chart-ai-bots");
    if (!container) return;

    const raw = DATA["ai_bots_ua" + suffix()];
    if (!raw || !raw.points || raw.points.length === 0) {
      container.innerHTML = '<p class="text-outline font-mono text-sm">Dati non disponibili.</p>';
      return;
    }

    container.innerHTML = "";

    const agents = raw.agents || [];
    const points = raw.points;
    const W = 450, H = 280, pad = { t: 20, r: 20, b: 40, l: 50 };
    const x0 = pad.l, x1 = W - pad.r, y0 = pad.t, y1 = H - pad.b;
    const n = points.length;

    /* Determine max Y */
    let maxY = 1;
    points.forEach(function (p) {
      agents.forEach(function (a) {
        const v = (p.values && p.values[a]) || 0;
        if (v > maxY) maxY = v;
      });
    });
    maxY = Math.ceil(maxY / 10) * 10 || 10;

    const svg = makeSvg(W, H);
    svg.appendChild(drawGrid(svg, x0, y0, x1, y1, 5, { min: 0, max: maxY }, false));
    svg.appendChild(drawXLabels(svg, x0, x1, y1 + 20, points.map(function (p) { return p.date; }), 4));

    const lineEls = [];
    agents.forEach(function (agent, idx) {
      const color = COLORS[idx % COLORS.length];
      let pts = "";
      points.forEach(function (p, i) {
        const v = (p.values && p.values[agent]) || 0;
        const px = x0 + (x1 - x0) * i / (n - 1 || 1);
        const py = y0 + (y1 - y0) * (1 - v / maxY);
        pts += (i === 0 ? "M" : "L") + px.toFixed(1) + "," + py.toFixed(1);
      });
      const path = svgEl("path", {
        d: pts, fill: "none", stroke: color, "stroke-width": "2", "stroke-linejoin": "round"
      });
      svg.appendChild(path);
      lineEls.push({ label: agent, color: color, visible: true, el: path });
    });

    container.appendChild(svg);
    container.appendChild(buildLegend(lineEls, function (idx, vis) {
      lineEls[idx].el.style.display = vis ? "" : "none";
    }));
  }

  /* ══════════════════════════════════════════
     Section 4b: Crawl purpose stacked area
     ══════════════════════════════════════════ */
  function renderCrawlPurpose() {
    const container = document.getElementById("chart-crawl-purpose");
    if (!container) return;

    const raw = DATA["crawl_purpose" + suffix()];
    if (!raw || !raw.points || raw.points.length === 0) {
      container.innerHTML = '<p class="text-outline font-mono text-sm">Dati non disponibili.</p>';
      return;
    }

    container.innerHTML = "";

    const purposes = raw.purposes || [];
    const points = raw.points;
    const W = 450, H = 280, pad = { t: 20, r: 20, b: 40, l: 50 };
    const x0 = pad.l, x1 = W - pad.r, y0 = pad.t, y1 = H - pad.b;
    const n = points.length;

    const svg = makeSvg(W, H);
    svg.appendChild(drawGrid(svg, x0, y0, x1, y1, 5, { min: 0, max: 100 }, false));
    svg.appendChild(drawXLabels(svg, x0, x1, y1 + 20, points.map(function (p) { return p.date; }), 4));

    /* Compute cumulative stacks */
    const stacks = []; // stacks[purposeIdx][pointIdx] = {base, top}
    purposes.forEach(function (purpose, pIdx) {
      const stack = [];
      points.forEach(function (pt, i) {
        const v = (pt.values && pt.values[purpose]) || 0;
        const base = pIdx === 0 ? 0 : stacks[pIdx - 1][i].top;
        stack.push({ base: base, top: base + v });
      });
      stacks.push(stack);
    });

    /* Draw areas bottom-to-top, render in reverse so first purpose is on top visually */
    for (let pIdx = purposes.length - 1; pIdx >= 0; pIdx--) {
      const purpose = purposes[pIdx];
      const color = PURPOSE_COLORS[purpose] || COLORS[pIdx % COLORS.length];
      const stack = stacks[pIdx];

      let d = "";
      /* Top edge left to right */
      stack.forEach(function (s, i) {
        const px = x0 + (x1 - x0) * i / (n - 1 || 1);
        const py = y0 + (y1 - y0) * (1 - s.top / 100);
        d += (i === 0 ? "M" : "L") + px.toFixed(1) + "," + py.toFixed(1);
      });
      /* Bottom edge right to left */
      for (let i = n - 1; i >= 0; i--) {
        const px = x0 + (x1 - x0) * i / (n - 1 || 1);
        const py = y0 + (y1 - y0) * (1 - stack[i].base / 100);
        d += "L" + px.toFixed(1) + "," + py.toFixed(1);
      }
      d += "Z";

      svg.appendChild(svgEl("path", {
        d: d, fill: color, "fill-opacity": "0.5", stroke: color, "stroke-width": "1"
      }));
    }

    container.appendChild(svg);

    /* Legend (non-interactive for stacked area) */
    const legendDiv = document.createElement("div");
    legendDiv.className = "flex flex-wrap gap-3 mt-3 text-sm font-mono";
    purposes.forEach(function (p, idx) {
      const color = PURPOSE_COLORS[p] || COLORS[idx % COLORS.length];
      const span = document.createElement("span");
      span.className = "flex items-center gap-1.5";
      span.innerHTML = '<span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:' + color + '"></span>' +
        '<span style="color:' + color + '">' + escHtml(p) + '</span>';
      legendDiv.appendChild(span);
    });
    container.appendChild(legendDiv);
  }

  /* ══════════════════════════════════════════
     Section 5: Industry horizontal bars
     ══════════════════════════════════════════ */
  function renderIndustry() {
    const container = document.getElementById("chart-industry");
    if (!container) return;

    let data = DATA["industry" + suffix()];
    if (!data || data.length === 0) {
      container.innerHTML = '<p class="text-outline font-mono text-sm">Dati non disponibili.</p>';
      return;
    }

    container.innerHTML = "";

    /* Filter out "other"/"Other" and take top 10 */
    data = data.filter(function (d) {
      return d.industry.toLowerCase() !== "other";
    }).slice(0, 10);

    const maxPct = Math.max.apply(null, data.map(function (d) { return d.pct; })) || 1;

    const barH = 28, gap = 6, labelW = 140, barMaxW = 420;
    const W = labelW + barMaxW + 80;
    const H = data.length * (barH + gap) + 10;

    const svg = makeSvg(W, H);

    data.forEach(function (d, i) {
      const y = i * (barH + gap) + 5;
      const bw = (d.pct / maxPct) * barMaxW;
      const color = COLORS[i % COLORS.length];

      /* Label */
      const txt = svgEl("text", {
        x: labelW - 8, y: y + barH / 2 + 4, fill: LABEL_COLOR, "font-size": "11",
        "text-anchor": "end", "font-family": "monospace"
      });
      txt.textContent = d.industry;
      svg.appendChild(txt);

      /* Bar */
      svg.appendChild(svgEl("rect", {
        x: labelW, y: y, width: Math.max(2, bw).toFixed(1), height: barH,
        fill: color, "fill-opacity": "0.7", rx: "2"
      }));

      /* Value */
      const val = svgEl("text", {
        x: labelW + bw + 6, y: y + barH / 2 + 4, fill: color, "font-size": "11",
        "text-anchor": "start", "font-family": "monospace"
      });
      val.textContent = d.pct.toFixed(1) + "%";
      svg.appendChild(val);
    });

    container.appendChild(svg);
  }

  /* ── Utilities ── */
  function escHtml(s) {
    var d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  /* ── Render all ── */
  function renderAll() {
    renderTop10();
    renderPlatforms();
    renderBotHuman();
    renderAiBots();
    renderCrawlPurpose();
    renderIndustry();
  }

  /* ── Init ── */
  initToggle();
  renderAll();
})();
