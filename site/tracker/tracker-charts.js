/* tracker-charts.js — vanilla JS chart engine for OsservatorioSEO Tracker v3 */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", init);

  function init() {
    var DATA = window.__TRACKER_DATA__;
    if (!DATA) return;

    /* ── Constants ── */
    var PALETTE = [
      "#00f63e","#f5a623","#e24c4c","#4ca6e2","#e24ce2",
      "#4ce2c4","#e2e24c","#a64cf5","#f54c8a","#8af54c"
    ];
    var GREEN = "#00f63e";
    var GREY = "#919191";
    var DARK_GREY = "#333";
    var NS = "http://www.w3.org/2000/svg";
    var PURPOSE_COLORS = {
      "User Action": GREEN,
      "Training": "#e24c4c",
      "Mixed Purpose": "#f5a623",
      "Search": "#4ca6e2",
      "Undeclared": GREY
    };
    var TRAINING_BOTS = ["GPTBot","ClaudeBot","Meta-ExternalAgent","Bytespider"];

    /* ── Shared utilities ── */

    function svgEl(tag, attrs) {
      var el = document.createElementNS(NS, tag);
      if (attrs) {
        var keys = Object.keys(attrs);
        for (var i = 0; i < keys.length; i++) {
          el.setAttribute(keys[i], attrs[keys[i]]);
        }
      }
      return el;
    }

    function clearAndGet(id) {
      var el = document.getElementById(id);
      if (el) el.innerHTML = "";
      return el || null;
    }

    function formatBucket(rank, bucket) {
      if (typeof rank === "number" && rank !== null) return "#" + rank;
      if (!bucket) return "—";
      if (bucket.charAt(0) === ">") {
        return "oltre " + bucket.slice(1).replace(/(\d)(?=(\d{3})+$)/g, "$1.");
      }
      return "tra i primi " + Number(bucket).toLocaleString("it-IT");
    }

    function fmtDate(isoStr) {
      if (!isoStr || isoStr.length < 10) return "";
      return isoStr.slice(8, 10) + "/" + isoStr.slice(5, 7);
    }

    function fmtPct(n) {
      return n.toFixed(1) + "%";
    }

    function noData(el) {
      if (el) el.innerHTML = '<p class="text-outline text-sm">Dati non disponibili</p>';
    }

    function escHtml(s) {
      var d = document.createElement("div");
      d.textContent = s;
      return d.innerHTML;
    }

    function makeSvg(w, h) {
      var svg = svgEl("svg", {
        viewBox: "0 0 " + w + " " + h,
        preserveAspectRatio: "xMidYMid meet"
      });
      svg.classList.add("w-full");
      return svg;
    }

    function last(arr) {
      return arr && arr.length > 0 ? arr[arr.length - 1] : null;
    }

    function bucketNum(b) {
      if (!b) return Infinity;
      if (b.charAt(0) === ">") return Number(b.slice(1));
      return Number(b);
    }

    /* ── Reusable chart: Line chart ── */

    function renderLineChart(containerId, series, opts) {
      opts = opts || {};
      var W = opts.width || 700;
      var H = opts.height || 300;
      var yInv = opts.yInverted || false;
      var pad = { t: 20, r: 20, b: 40, l: 50 };
      var x0 = pad.l, x1 = W - pad.r, y0 = pad.t, y1 = H - pad.b;

      /* Determine X range from all series */
      var allDates = [];
      for (var si = 0; si < series.length; si++) {
        for (var di = 0; di < series[si].data.length; di++) {
          var dx = series[si].data[di].x;
          if (allDates.indexOf(dx) === -1) allDates.push(dx);
        }
      }
      allDates.sort();
      var n = allDates.length || 1;

      /* Determine Y range */
      var yMin = Infinity, yMax = -Infinity;
      for (si = 0; si < series.length; si++) {
        for (di = 0; di < series[si].data.length; di++) {
          var v = series[si].data[di].y;
          if (v < yMin) yMin = v;
          if (v > yMax) yMax = v;
        }
      }
      if (yMin === Infinity) { yMin = 0; yMax = 100; }
      if (yMin === yMax) { yMin -= 1; yMax += 1; }
      /* Add a bit of padding */
      var yRange = yMax - yMin;
      yMin = Math.max(0, yMin - yRange * 0.05);
      yMax = yMax + yRange * 0.05;
      if (yInv && yMin > 1) yMin = 1;

      var svg = makeSvg(W, H);

      /* Grid lines */
      var gridLines = 3;
      for (var gi = 0; gi <= gridLines; gi++) {
        var gy = y0 + (y1 - y0) * gi / gridLines;
        svg.appendChild(svgEl("line", {
          x1: x0, y1: gy, x2: x1, y2: gy, stroke: DARK_GREY, "stroke-width": "0.5"
        }));
        var labelVal;
        if (yInv) {
          labelVal = Math.round(yMin + (yMax - yMin) * gi / gridLines);
        } else {
          labelVal = Math.round(yMax - (yMax - yMin) * gi / gridLines);
        }
        var lbl = svgEl("text", {
          x: x0 - 6, y: gy + 3, fill: GREY, "font-size": "10",
          "text-anchor": "end", "font-family": "monospace"
        });
        lbl.textContent = opts.yLabel === "%" ? fmtPct(labelVal) : labelVal;
        svg.appendChild(lbl);
      }

      /* X labels: first and last */
      if (opts.xLabels !== false && allDates.length > 0) {
        var xFirst = svgEl("text", {
          x: x0, y: y1 + 20, fill: GREY, "font-size": "10",
          "text-anchor": "start", "font-family": "monospace"
        });
        xFirst.textContent = fmtDate(allDates[0]);
        svg.appendChild(xFirst);

        if (allDates.length > 1) {
          var xLast = svgEl("text", {
            x: x1, y: y1 + 20, fill: GREY, "font-size": "10",
            "text-anchor": "end", "font-family": "monospace"
          });
          xLast.textContent = fmtDate(allDates[allDates.length - 1]);
          svg.appendChild(xLast);
        }
      }

      /* Draw lines */
      var lineEls = [];
      for (si = 0; si < series.length; si++) {
        var s = series[si];
        var pts = "";
        for (di = 0; di < s.data.length; di++) {
          var xIdx = allDates.indexOf(s.data[di].x);
          var px = x0 + (x1 - x0) * xIdx / (n - 1 || 1);
          var val = s.data[di].y;
          var py;
          if (yInv) {
            py = y0 + (y1 - y0) * (val - yMin) / (yMax - yMin || 1);
          } else {
            py = y0 + (y1 - y0) * (1 - (val - yMin) / (yMax - yMin || 1));
          }
          pts += (di === 0 ? "M" : "L") + px.toFixed(1) + "," + py.toFixed(1);
        }
        var path = svgEl("path", {
          d: pts, fill: "none", stroke: s.color, "stroke-width": "2", "stroke-linejoin": "round"
        });
        svg.appendChild(path);
        lineEls.push({ label: s.label, color: s.color, visible: true, el: path });
      }

      /* Legend */
      var legendDiv = document.createElement("div");
      legendDiv.className = "flex flex-wrap gap-3 mt-3 text-sm font-mono";
      for (var li = 0; li < lineEls.length; li++) {
        (function (idx) {
          var item = lineEls[idx];
          var btn = document.createElement("button");
          btn.className = "flex items-center gap-1.5 opacity-100 transition-opacity";
          var dot = document.createElement("span");
          dot.style.cssText = "display:inline-block;width:10px;height:10px;border-radius:2px;background:" + item.color;
          btn.appendChild(dot);
          var lbl = document.createElement("span");
          lbl.style.color = item.color;
          lbl.textContent = item.label;
          btn.appendChild(lbl);
          btn.addEventListener("click", function () {
            item.visible = !item.visible;
            item.el.style.display = item.visible ? "" : "none";
            btn.style.opacity = item.visible ? "1" : "0.3";
          });
          legendDiv.appendChild(btn);
        })(li);
      }

      return { svg: svg, legendContainer: legendDiv };
    }

    /* ── Reusable chart: Stacked area ── */

    function renderStackedArea(containerId, data, opts) {
      opts = opts || {};
      var W = opts.width || 700;
      var H = opts.height || 300;
      var pad = { t: 20, r: 20, b: 40, l: 50 };
      var x0 = pad.l, x1 = W - pad.r, y0 = pad.t, y1 = H - pad.b;

      var keys = data.keys;
      var points = data.points;
      var colors = data.colors || {};
      var n = points.length || 1;

      var svg = makeSvg(W, H);

      /* Y grid: 0%, 50%, 100% */
      var yLabels = [0, 50, 100];
      for (var yi = 0; yi < yLabels.length; yi++) {
        var gy = y0 + (y1 - y0) * (1 - yLabels[yi] / 100);
        svg.appendChild(svgEl("line", {
          x1: x0, y1: gy, x2: x1, y2: gy, stroke: DARK_GREY, "stroke-width": "0.5"
        }));
        var lbl = svgEl("text", {
          x: x0 - 6, y: gy + 3, fill: GREY, "font-size": "10",
          "text-anchor": "end", "font-family": "monospace"
        });
        lbl.textContent = yLabels[yi] + "%";
        svg.appendChild(lbl);
      }

      /* X labels: first and last */
      if (points.length > 0) {
        var xF = svgEl("text", {
          x: x0, y: y1 + 20, fill: GREY, "font-size": "10",
          "text-anchor": "start", "font-family": "monospace"
        });
        xF.textContent = fmtDate(points[0].date);
        svg.appendChild(xF);
        if (points.length > 1) {
          var xL = svgEl("text", {
            x: x1, y: y1 + 20, fill: GREY, "font-size": "10",
            "text-anchor": "end", "font-family": "monospace"
          });
          xL.textContent = fmtDate(points[points.length - 1].date);
          svg.appendChild(xL);
        }
      }

      /* Compute stacks */
      var stacks = [];
      for (var ki = 0; ki < keys.length; ki++) {
        var stack = [];
        for (var pi = 0; pi < points.length; pi++) {
          var val = (points[pi].values && points[pi].values[keys[ki]]) || 0;
          var base = ki === 0 ? 0 : stacks[ki - 1][pi].top;
          stack.push({ base: base, top: base + val });
        }
        stacks.push(stack);
      }

      /* Draw areas top to bottom (so first key renders on top) */
      for (ki = keys.length - 1; ki >= 0; ki--) {
        var color = colors[keys[ki]] || PALETTE[ki % PALETTE.length];
        var stack2 = stacks[ki];
        var d = "";
        for (pi = 0; pi < points.length; pi++) {
          var px = x0 + (x1 - x0) * pi / (n - 1 || 1);
          var py = y0 + (y1 - y0) * (1 - stack2[pi].top / 100);
          d += (pi === 0 ? "M" : "L") + px.toFixed(1) + "," + py.toFixed(1);
        }
        for (pi = points.length - 1; pi >= 0; pi--) {
          var px2 = x0 + (x1 - x0) * pi / (n - 1 || 1);
          var py2 = y0 + (y1 - y0) * (1 - stack2[pi].base / 100);
          d += "L" + px2.toFixed(1) + "," + py2.toFixed(1);
        }
        d += "Z";
        svg.appendChild(svgEl("path", {
          d: d, fill: color, "fill-opacity": "0.5", stroke: color, "stroke-width": "1"
        }));
      }

      /* Legend */
      var legendDiv = document.createElement("div");
      legendDiv.className = "flex flex-wrap gap-3 mt-3 text-sm font-mono";
      for (ki = 0; ki < keys.length; ki++) {
        var c = colors[keys[ki]] || PALETTE[ki % PALETTE.length];
        var span = document.createElement("span");
        span.className = "flex items-center gap-1.5";
        span.innerHTML = '<span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:' + c + '"></span>' +
          '<span style="color:' + c + '">' + escHtml(keys[ki]) + '</span>';
        legendDiv.appendChild(span);
      }

      return { svg: svg, legendContainer: legendDiv };
    }

    /* ── Reusable chart: Area chart (single series) ── */

    function renderAreaChart(containerId, points, opts) {
      opts = opts || {};
      var W = opts.width || 700;
      var H = opts.height || 280;
      var color = opts.color || GREEN;
      var yMaxOpt = opts.yMax;
      var pad = { t: 20, r: 20, b: 40, l: 50 };
      var x0 = pad.l, x1 = W - pad.r, y0 = pad.t, y1 = H - pad.b;
      var n = points.length || 1;

      var maxVal = 0;
      for (var i = 0; i < points.length; i++) {
        if (points[i].value > maxVal) maxVal = points[i].value;
      }
      var yMax = yMaxOpt || Math.ceil(maxVal / 10) * 10 || 100;

      var svg = makeSvg(W, H);

      /* Grid */
      var gridN = 3;
      for (var gi = 0; gi <= gridN; gi++) {
        var gy = y0 + (y1 - y0) * gi / gridN;
        svg.appendChild(svgEl("line", {
          x1: x0, y1: gy, x2: x1, y2: gy, stroke: DARK_GREY, "stroke-width": "0.5"
        }));
        var lv = Math.round(yMax - yMax * gi / gridN);
        var lbl = svgEl("text", {
          x: x0 - 6, y: gy + 3, fill: GREY, "font-size": "10",
          "text-anchor": "end", "font-family": "monospace"
        });
        lbl.textContent = fmtPct(lv);
        svg.appendChild(lbl);
      }

      /* X labels */
      if (points.length > 0) {
        var xF = svgEl("text", {
          x: x0, y: y1 + 20, fill: GREY, "font-size": "10",
          "text-anchor": "start", "font-family": "monospace"
        });
        xF.textContent = fmtDate(points[0].date);
        svg.appendChild(xF);
        if (points.length > 1) {
          var xL = svgEl("text", {
            x: x1, y: y1 + 20, fill: GREY, "font-size": "10",
            "text-anchor": "end", "font-family": "monospace"
          });
          xL.textContent = fmtDate(points[points.length - 1].date);
          svg.appendChild(xL);
        }
      }

      /* Area + line */
      var linePath = "";
      var areaPath = "";
      for (i = 0; i < points.length; i++) {
        var px = x0 + (x1 - x0) * i / (n - 1 || 1);
        var py = y0 + (y1 - y0) * (1 - points[i].value / yMax);
        linePath += (i === 0 ? "M" : "L") + px.toFixed(1) + "," + py.toFixed(1);
        areaPath += (i === 0 ? "M" : "L") + px.toFixed(1) + "," + py.toFixed(1);
      }
      areaPath += "L" + x1.toFixed(1) + "," + y1 + "L" + x0.toFixed(1) + "," + y1 + "Z";

      svg.appendChild(svgEl("path", {
        d: areaPath, fill: color, "fill-opacity": "0.25", stroke: "none"
      }));
      svg.appendChild(svgEl("path", {
        d: linePath, fill: "none", stroke: color, "stroke-width": "2"
      }));

      /* Annotate last value */
      if (points.length > 0) {
        var lastPt = points[points.length - 1];
        var labelY = y0 + (y1 - y0) * (1 - lastPt.value / yMax);
        var ann = svgEl("text", {
          x: x1 - 4, y: labelY - 8, fill: color, "font-size": "11",
          "text-anchor": "end", "font-family": "monospace"
        });
        ann.textContent = (opts.label ? opts.label + " " : "") + fmtPct(lastPt.value);
        svg.appendChild(ann);
      }

      return { svg: svg };
    }

    /* ── Reusable chart: Horizontal bars ── */

    function renderHBars(containerId, data) {
      if (!data || data.length === 0) return null;

      /* Sort by IT value desc */
      data = data.slice().sort(function (a, b) { return b.valueIT - a.valueIT; });

      var barH = 24, gap = 6, labelW = 160, barMaxW = 340, rightLabelW = 80;
      var W = labelW + barMaxW + rightLabelW + 20;
      var H = data.length * (barH + gap) * 2 + gap * data.length + 20;

      /* Determine max */
      var maxVal = 1;
      for (var i = 0; i < data.length; i++) {
        if (data[i].valueIT > maxVal) maxVal = data[i].valueIT;
        if (data[i].valueGlobal > maxVal) maxVal = data[i].valueGlobal;
      }

      var svg = makeSvg(W, H);
      var yOff = 10;

      for (i = 0; i < data.length; i++) {
        var d = data[i];

        /* Label */
        var txt = svgEl("text", {
          x: labelW - 8, y: yOff + barH / 2 + 4, fill: GREY, "font-size": "11",
          "text-anchor": "end", "font-family": "monospace"
        });
        txt.textContent = d.label;
        svg.appendChild(txt);

        /* IT bar (green) */
        var bwIT = Math.max(2, (d.valueIT / maxVal) * barMaxW);
        svg.appendChild(svgEl("rect", {
          x: labelW, y: yOff, width: bwIT.toFixed(1), height: barH,
          fill: GREEN, "fill-opacity": "0.7", rx: "2"
        }));
        var vIT = svgEl("text", {
          x: labelW + bwIT + 6, y: yOff + barH / 2 + 4, fill: GREEN, "font-size": "10",
          "text-anchor": "start", "font-family": "monospace"
        });
        vIT.textContent = typeof d.valueIT === "number" ? fmtPct(d.valueIT) : d.valueIT;
        svg.appendChild(vIT);

        yOff += barH + 2;

        /* Global bar (grey) */
        var bwGL = Math.max(2, (d.valueGlobal / maxVal) * barMaxW);
        svg.appendChild(svgEl("rect", {
          x: labelW, y: yOff, width: bwGL.toFixed(1), height: barH,
          fill: GREY, "fill-opacity": "0.5", rx: "2"
        }));
        var vGL = svgEl("text", {
          x: labelW + bwGL + 6, y: yOff + barH / 2 + 4, fill: GREY, "font-size": "10",
          "text-anchor": "start", "font-family": "monospace"
        });
        vGL.textContent = typeof d.valueGlobal === "number" ? fmtPct(d.valueGlobal) : d.valueGlobal;
        svg.appendChild(vGL);

        yOff += barH + gap + 8;
      }

      /* Adjust SVG height */
      svg.setAttribute("viewBox", "0 0 " + W + " " + yOff);

      /* Small legend */
      var legendDiv = document.createElement("div");
      legendDiv.className = "flex gap-4 mt-3 text-xs font-mono";
      legendDiv.innerHTML =
        '<span class="flex items-center gap-1"><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:' + GREEN + '"></span><span style="color:' + GREEN + '">Italia</span></span>' +
        '<span class="flex items-center gap-1"><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:' + GREY + '"></span><span style="color:' + GREY + '">Mondo</span></span>';

      return { svg: svg, legendContainer: legendDiv };
    }

    /* ══════════════════════════════════════════
       Hero section
       ══════════════════════════════════════════ */

    function renderHero() {
      var el = clearAndGet("hero");
      if (!el) return;

      var platforms = DATA.ai_platforms_it;
      if (!platforms || platforms.length === 0) { noData(el); return; }

      /* Find best rank (lowest non-null) */
      var best = null;
      for (var i = 0; i < platforms.length; i++) {
        if (typeof platforms[i].rank === "number") {
          if (!best || platforms[i].rank < best.rank) best = platforms[i];
        }
      }

      var domain, rankText;
      if (best && best.rank <= 100) {
        domain = best.domain;
        rankText = "primi " + best.rank + " siti";
      } else {
        /* Find best bucket */
        var bestBucket = null;
        for (i = 0; i < platforms.length; i++) {
          var bn = bucketNum(platforms[i].bucket);
          if (!bestBucket || bn < bucketNum(bestBucket.bucket)) bestBucket = platforms[i];
        }
        if (bestBucket) {
          domain = bestBucket.domain;
          rankText = formatBucket(null, bestBucket.bucket) + " siti";
        } else {
          noData(el);
          return;
        }
      }

      el.innerHTML =
        '<p class="text-3xl sm:text-5xl font-bold text-primary-container mb-2">' + escHtml(domain) + '</p>' +
        '<p class="text-lg text-on-surface-variant">è tra i <span class="text-white font-bold">' + escHtml(rankText) + '</span> più popolari in Italia</p>';
    }

    /* ══════════════════════════════════════════
       KPI Cards
       ══════════════════════════════════════════ */

    function renderKPICards() {
      var el = clearAndGet("kpi-cards");
      if (!el) return;

      var cards = [];
      var trendsAvg = (DATA.trends_it || {}).averages || {};
      var trendsKw = (DATA.trends_it || {}).keywords || [];

      /* Cards 1-3: Top 3 AI by Google Trends average (IT) */
      var ranked = trendsKw.slice().sort(function (a, b) {
        return (trendsAvg[b] || 0) - (trendsAvg[a] || 0);
      });
      for (var i = 0; i < Math.min(3, ranked.length); i++) {
        var kw = ranked[i];
        cards.push({ value: String(trendsAvg[kw] || 0), label: kw, sub: "#" + (i + 1) + " in Italia" });
      }

      /* Card 4: Bot % IT */
      var bh = DATA.bot_human_it;
      if (bh && bh.points && bh.points.length > 0) {
        var lastBH = bh.points[bh.points.length - 1];
        cards.push({ value: fmtPct(lastBH.bot_pct), label: "Traffico bot", sub: "Italia" });
      } else {
        cards.push({ value: "—", label: "Traffico bot", sub: "Italia" });
      }

      var html = "";
      for (i = 0; i < cards.length; i++) {
        html += '<div class="bg-surface-container-lowest border border-outline-variant p-4 text-center">' +
          '<p class="text-2xl font-bold text-primary-container font-mono">' + escHtml(cards[i].value) + '</p>' +
          '<p class="text-xs text-white mt-1">' + escHtml(cards[i].label) + '</p>' +
          '<p class="text-[10px] text-outline uppercase tracking-wider mt-0.5">' + escHtml(cards[i].sub) + '</p>' +
          '</div>';
      }
      el.innerHTML = html;
    }

    /* ══════════════════════════════════════════
       S1 — AI Platform Rankings
       ══════════════════════════════════════════ */

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

      /* Table: current snapshot — IT vs Global from Trends */
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
          thtml += '<p class="text-[10px] text-outline mt-2">Valori = interesse di ricerca relativo su Google (0-100). 100 = picco massimo nel periodo. Fonte: Google Trends via DataForSEO.</p>';
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

    /* ══════════════════════════════════════════
       S2 — Crawl Purpose stacked area
       ══════════════════════════════════════════ */

    function renderSection2() {
      renderPurposeCards("chart-s2-it", DATA.crawl_purpose_it, "Italia");
      renderPurposeCards("chart-s2-global", DATA.crawl_purpose_global, "Mondo");

      var textEl = clearAndGet("text-s2");
      if (textEl) {
        var parts = [];
        var itRaw = DATA.crawl_purpose_it;
        var glRaw = DATA.crawl_purpose_global;
        if (itRaw && itRaw.points && itRaw.points.length > 0) {
          var lp = itRaw.points[itRaw.points.length - 1];
          var ua = (lp.values && lp.values["User Action"]) || 0;
          var tr = (lp.values && lp.values["Training"]) || 0;
          parts.push("In Italia, secondo le dichiarazioni degli operatori dei bot, il " + fmtPct(ua) + " del crawling AI è classificato come 'per gli utenti' e il " + fmtPct(tr) + " come 'addestramento modelli'.");
        }
        if (glRaw && glRaw.points && glRaw.points.length > 0) {
          var lp2 = glRaw.points[glRaw.points.length - 1];
          var ua2 = (lp2.values && lp2.values["User Action"]) || 0;
          var tr2 = (lp2.values && lp2.values["Training"]) || 0;
          parts.push("A livello globale: " + fmtPct(ua2) + " per gli utenti, " + fmtPct(tr2) + " per l'addestramento.");
        }
        parts.push("Nota: i dati di Cloudflare mostrano un forte 'crawl-to-click gap' — per ogni visita che l'AI rimanda a un sito, vengono scansionate centinaia o migliaia di pagine.");
        textEl.innerHTML = '<p class="text-sm text-on-surface-variant leading-relaxed">' + parts.join(" ") + '</p>';
      }
    }

    function renderPurposeCards(containerId, raw, label) {
      var el = clearAndGet(containerId);
      if (!el || !raw || !raw.points || raw.points.length === 0) {
        if (el) noData(el);
        return;
      }
      var lp = raw.points[raw.points.length - 1];
      var purposes = [
        { key: "User Action", label: "Per gli utenti", color: GREEN, desc: "L'AI recupera pagine per rispondere a domande degli utenti" },
        { key: "Training", label: "Addestramento", color: "#e24c4c", desc: "Raccolta contenuti per addestrare modelli AI" },
        { key: "Mixed Purpose", label: "Scopo misto", color: "#f5a623", desc: "Sia utenti che addestramento" },
        { key: "Search", label: "Ricerca", color: "#4ca6e2", desc: "Indicizzazione per la search dell'AI" },
        { key: "Undeclared", label: "Non dichiarato", color: GREY, desc: "Scopo non comunicato dall'operatore" }
      ];

      var grid = document.createElement("div");
      grid.className = "grid grid-cols-2 sm:grid-cols-3 gap-3";

      for (var i = 0; i < purposes.length; i++) {
        var p = purposes[i];
        var val = (lp.values && lp.values[p.key]) || 0;
        if (val < 0.1) continue;

        var card = document.createElement("div");
        card.className = "bg-surface-container-lowest border border-outline-variant/50 p-3 rounded";
        card.innerHTML =
          '<div class="text-2xl font-bold font-mono" style="color:' + p.color + '">' + fmtPct(val) + '</div>' +
          '<div class="text-xs text-white font-bold mt-1">' + p.label + '</div>' +
          '<div class="text-[10px] text-outline mt-0.5">' + p.desc + '</div>';
        grid.appendChild(card);
      }

      el.appendChild(grid);

      // Add trend sparkline if enough data points
      if (raw.points.length >= 4) {
        var sparkDiv = document.createElement("div");
        sparkDiv.className = "mt-3";
        var W = 340, H = 60, PAD = { l: 5, r: 5, t: 5, b: 5 };
        var svg = svgEl("svg", { viewBox: "0 0 " + W + " " + H, class: "w-full" });
        var n = raw.points.length;
        var xScale = function(idx) { return PAD.l + (idx / Math.max(n - 1, 1)) * (W - PAD.l - PAD.r); };
        var yScale = function(v) { return PAD.t + ((100 - v) / 100) * (H - PAD.t - PAD.b); };

        // Draw lines for top 2 purposes
        var topKeys = ["User Action", "Training"];
        var topColors = [GREEN, "#e24c4c"];
        for (var k = 0; k < topKeys.length; k++) {
          var pts = [];
          for (var j = 0; j < raw.points.length; j++) {
            var v = (raw.points[j].values && raw.points[j].values[topKeys[k]]) || 0;
            pts.push(xScale(j) + "," + yScale(v));
          }
          if (pts.length >= 2) {
            svg.appendChild(svgEl("polyline", {
              points: pts.join(" "),
              fill: "none",
              stroke: topColors[k],
              "stroke-width": "1.5",
              "stroke-opacity": "0.7"
            }));
          }
        }
        sparkDiv.appendChild(svg);

        var sparkLabel = document.createElement("div");
        sparkLabel.className = "flex gap-4 text-[10px] text-outline mt-1";
        sparkLabel.innerHTML =
          '<span><span style="color:' + GREEN + '">—</span> Per gli utenti</span>' +
          '<span><span style="color:#e24c4c">—</span> Addestramento</span>' +
          '<span class="text-outline/50">Trend ultime ' + n + ' settimane</span>';
        sparkDiv.appendChild(sparkLabel);

        el.appendChild(sparkDiv);
      }
    }

    function renderStackedAreaPair(idIT, rawIT, idGL, rawGL, colorMap) {
      var elIT = clearAndGet(idIT);
      var elGL = clearAndGet(idGL);
      var smallW = 340;

      if (elIT) {
        if (!rawIT || !rawIT.points || rawIT.points.length === 0) {
          noData(elIT);
        } else {
          var chartIT = renderStackedArea(idIT, {
            keys: rawIT.purposes || rawIT.agents || [],
            points: rawIT.points,
            colors: colorMap || {}
          }, { width: smallW });
          elIT.appendChild(chartIT.svg);
          elIT.appendChild(chartIT.legendContainer);
        }
      }

      if (elGL) {
        if (!rawGL || !rawGL.points || rawGL.points.length === 0) {
          noData(elGL);
        } else {
          var chartGL = renderStackedArea(idGL, {
            keys: rawGL.purposes || rawGL.agents || [],
            points: rawGL.points,
            colors: colorMap || {}
          }, { width: smallW });
          elGL.appendChild(chartGL.svg);
          elGL.appendChild(chartGL.legendContainer);
        }
      }
    }

    /* ══════════════════════════════════════════
       S3 — AI Bots multi-line
       ══════════════════════════════════════════ */

    function renderSection3() {
      renderBotsLineChartPair(
        "chart-s3-it", DATA.ai_bots_ua_it,
        "chart-s3-global", DATA.ai_bots_ua_global,
        null /* all agents */
      );

      var textEl = clearAndGet("text-s3");
      if (textEl) {
        var parts = [];
        var topIT = getTopAgent(DATA.ai_bots_ua_it);
        var topGL = getTopAgent(DATA.ai_bots_ua_global);
        if (topIT) parts.push("Il bot AI più attivo in Italia è " + topIT.agent + " (" + fmtPct(topIT.pct) + ").");
        if (topGL) parts.push("A livello globale è " + topGL.agent + " (" + fmtPct(topGL.pct) + ").");
        if (parts.length > 0) {
          textEl.innerHTML = '<p class="text-sm text-on-surface-variant leading-relaxed">' + parts.join(" ") + '</p>';
        }
      }
    }

    function getTopAgent(raw) {
      if (!raw || !raw.points || raw.points.length === 0 || !raw.agents) return null;
      var lp = raw.points[raw.points.length - 1];
      var topA = "", topV = -1;
      for (var i = 0; i < raw.agents.length; i++) {
        var v = (lp.values && lp.values[raw.agents[i]]) || 0;
        if (v > topV) { topV = v; topA = raw.agents[i]; }
      }
      return { agent: topA, pct: topV };
    }

    function renderBotsLineChartPair(idIT, rawIT, idGL, rawGL, filterAgents) {
      var smallW = 340;

      function buildSeries(raw) {
        if (!raw || !raw.points || raw.points.length === 0 || !raw.agents) return null;
        var agents = filterAgents || raw.agents;
        var series = [];
        for (var ai = 0; ai < agents.length; ai++) {
          var agent = agents[ai];
          /* Check agent exists in data */
          if (raw.agents.indexOf(agent) === -1) continue;
          var dataArr = [];
          for (var pi = 0; pi < raw.points.length; pi++) {
            dataArr.push({
              x: raw.points[pi].date,
              y: (raw.points[pi].values && raw.points[pi].values[agent]) || 0
            });
          }
          series.push({
            label: agent,
            data: dataArr,
            color: PALETTE[series.length % PALETTE.length]
          });
        }
        return series.length > 0 ? series : null;
      }

      var elIT = clearAndGet(idIT);
      if (elIT) {
        var seriesIT = buildSeries(rawIT);
        if (!seriesIT) { noData(elIT); }
        else {
          var c = renderLineChart(idIT, seriesIT, { width: smallW, yLabel: "%" });
          elIT.appendChild(c.svg);
          elIT.appendChild(c.legendContainer);
        }
      }

      var elGL = clearAndGet(idGL);
      if (elGL) {
        var seriesGL = buildSeries(rawGL);
        if (!seriesGL) { noData(elGL); }
        else {
          var c2 = renderLineChart(idGL, seriesGL, { width: smallW, yLabel: "%" });
          elGL.appendChild(c2.svg);
          elGL.appendChild(c2.legendContainer);
        }
      }
    }

    /* ══════════════════════════════════════════
       S4 — IT vs World horizontal bars
       ══════════════════════════════════════════ */

    function renderSection4() {
      var el = clearAndGet("chart-s4");
      var textEl = clearAndGet("text-s4");
      if (!el) return;

      var barData = [];

      /* 1. Traffico bot */
      var bhIT = DATA.bot_human_it;
      var bhGL = DATA.bot_human_global;
      if (bhIT && bhIT.points && bhIT.points.length > 0 && bhGL && bhGL.points && bhGL.points.length > 0) {
        barData.push({
          label: "Traffico bot (% del totale)",
          valueIT: bhIT.points[bhIT.points.length - 1].bot_pct,
          valueGlobal: bhGL.points[bhGL.points.length - 1].bot_pct
        });
      }

      /* 2. Crawling per utenti */
      var cpIT = DATA.crawl_purpose_it;
      var cpGL = DATA.crawl_purpose_global;
      if (cpIT && cpIT.points && cpIT.points.length > 0 && cpGL && cpGL.points && cpGL.points.length > 0) {
        var lpIT = cpIT.points[cpIT.points.length - 1];
        var lpGL = cpGL.points[cpGL.points.length - 1];
        barData.push({
          label: "Crawling per gli utenti (% AI bot)",
          valueIT: (lpIT.values && lpIT.values["User Action"]) || 0,
          valueGlobal: (lpGL.values && lpGL.values["User Action"]) || 0
        });
      }

      /* 3. Crawling per addestramento */
      if (cpIT && cpIT.points && cpIT.points.length > 0 && cpGL && cpGL.points && cpGL.points.length > 0) {
        barData.push({
          label: "Crawling per addestramento (% AI bot)",
          valueIT: (lpIT.values && lpIT.values["Training"]) || 0,
          valueGlobal: (lpGL.values && lpGL.values["Training"]) || 0
        });
      }

      /* 4. Second most active bot */
      var sec = getSecondAgent(DATA.ai_bots_ua_it);
      var secGL = getSecondAgent(DATA.ai_bots_ua_global);
      if (sec || secGL) {
        barData.push({
          label: (sec ? sec.agent : (secGL ? secGL.agent : "Bot #2")) + " (% AI bot)",
          valueIT: sec ? sec.pct : 0,
          valueGlobal: secGL ? secGL.pct : 0
        });
      }

      if (barData.length === 0) { noData(el); return; }

      var chart = renderHBars("chart-s4", barData);
      if (chart) {
        el.appendChild(chart.svg);
        el.appendChild(chart.legendContainer);
      }

      /* Text */
      if (textEl) {
        var ahead = 0, behind = 0;
        for (var i = 0; i < barData.length; i++) {
          if (barData[i].valueIT > barData[i].valueGlobal) ahead++;
          else if (barData[i].valueIT < barData[i].valueGlobal) behind++;
        }
        var msg = "L'Italia ";
        if (ahead > behind) msg += "è in vantaggio sulla media mondiale in " + ahead + " metriche su " + barData.length + ".";
        else if (behind > ahead) msg += "è in ritardo sulla media mondiale in " + behind + " metriche su " + barData.length + ".";
        else msg += "è allineata alla media mondiale.";
        textEl.innerHTML = '<p class="text-sm text-on-surface-variant leading-relaxed">' + msg + '</p>';
      }
    }

    function getBestRank(platforms) {
      if (!platforms || platforms.length === 0) return null;
      var best = null;
      for (var i = 0; i < platforms.length; i++) {
        if (typeof platforms[i].rank === "number") {
          if (!best || platforms[i].rank < best.rank) best = platforms[i];
        }
      }
      if (best) return best;
      /* Fallback: best bucket */
      for (i = 0; i < platforms.length; i++) {
        if (platforms[i].bucket && (!best || bucketNum(platforms[i].bucket) < bucketNum(best.bucket))) {
          best = platforms[i];
        }
      }
      return best;
    }

    function getSecondAgent(raw) {
      if (!raw || !raw.points || raw.points.length === 0 || !raw.agents) return null;
      var lp = raw.points[raw.points.length - 1];
      var sorted = raw.agents.map(function (a) {
        return { agent: a, pct: (lp.values && lp.values[a]) || 0 };
      }).sort(function (a, b) { return b.pct - a.pct; });
      return sorted.length >= 2 ? sorted[1] : null;
    }

    /* ══════════════════════════════════════════
       S5 — Training bots lines
       ══════════════════════════════════════════ */

    function renderSection5() {
      renderBotsLineChartPair(
        "chart-s5-it", DATA.ai_bots_ua_it,
        "chart-s5-global", DATA.ai_bots_ua_global,
        TRAINING_BOTS
      );

      var textEl = clearAndGet("text-s5");
      if (textEl) {
        var parts = [];
        var itRaw = DATA.ai_bots_ua_it;
        var glRaw = DATA.ai_bots_ua_global;
        if (itRaw && itRaw.points && itRaw.points.length > 0) {
          var lp = itRaw.points[itRaw.points.length - 1];
          var gptIT = (lp.values && lp.values["GPTBot"]) || 0;
          parts.push("GPTBot rappresenta il " + fmtPct(gptIT) + " del traffico bot AI in Italia.");
        }
        if (glRaw && glRaw.points && glRaw.points.length > 0) {
          var lp2 = glRaw.points[glRaw.points.length - 1];
          var gptGL = (lp2.values && lp2.values["GPTBot"]) || 0;
          parts.push("A livello globale GPTBot è al " + fmtPct(gptGL) + ".");
        }
        if (parts.length > 0) {
          textEl.innerHTML = '<p class="text-sm text-on-surface-variant leading-relaxed">' + parts.join(" ") + '</p>';
        }
      }
    }

    /* ══════════════════════════════════════════
       S6 — All bots stacked area
       ══════════════════════════════════════════ */

    function renderSection6() {
      /* Reuse the same multi-line approach as Section 3 */
      renderBotsLineChartPair(
        "chart-s6-it", DATA.ai_bots_ua_it,
        "chart-s6-global", DATA.ai_bots_ua_global
      );

      var textEl = clearAndGet("text-s6");
      if (textEl && DATA.ai_bots_ua_it && DATA.ai_bots_ua_it.points && DATA.ai_bots_ua_it.points.length >= 2) {
        var pts = DATA.ai_bots_ua_it.points;
        var first = pts[0];
        var last = pts[pts.length - 1];
        var gbFirst = (first.values && first.values["Googlebot"]) || 0;
        var gbLast = (last.values && last.values["Googlebot"]) || 0;
        var delta = gbLast - gbFirst;
        var trend = delta > 1 ? "in crescita" : delta < -1 ? "in calo" : "stabile";
        textEl.innerHTML = '<p class="text-sm text-on-surface-variant leading-relaxed">' +
          'Googlebot rappresenta il ' + fmtPct(gbLast) + ' del crawling AI in Italia (' + trend +
          ' rispetto a ' + fmtPct(gbFirst) + ' di ' + (pts.length) + ' settimane fa). ' +
          'La composizione complessiva mostra come le quote relative dei diversi crawler si stiano ridistribuendo.</p>';
      }
    }

    /* ══════════════════════════════════════════
       S7 — Industry horizontal bars
       ══════════════════════════════════════════ */

    function renderSection7() {
      var el = clearAndGet("chart-s7");
      var textEl = clearAndGet("text-s7");
      if (!el) return;

      var indIT = DATA.industry_it || [];
      var indGL = DATA.industry_global || [];

      /* Filter "other" and take top 10 by IT */
      indIT = indIT.filter(function (d) { return d.industry.toLowerCase() !== "other"; });
      indIT.sort(function (a, b) { return b.pct - a.pct; });
      indIT = indIT.slice(0, 10);

      if (indIT.length === 0) { noData(el); return; }

      /* Build global lookup */
      var glMap = {};
      for (var i = 0; i < indGL.length; i++) {
        glMap[indGL[i].industry] = indGL[i].pct;
      }

      var barData = [];
      for (i = 0; i < indIT.length; i++) {
        barData.push({
          label: indIT[i].industry,
          valueIT: indIT[i].pct,
          valueGlobal: glMap[indIT[i].industry] || 0
        });
      }

      var chart = renderHBars("chart-s7", barData);
      if (chart) {
        el.appendChild(chart.svg);
        el.appendChild(chart.legendContainer);
      }

      if (textEl && barData.length > 0) {
        var topIT2 = barData[0];
        var glVal = topIT2.valueGlobal;
        textEl.innerHTML = '<p class="text-sm text-on-surface-variant leading-relaxed">' +
          'Il settore più colpito dal crawling AI in Italia è <strong class="text-white">' + escHtml(topIT2.label) + '</strong> (' + fmtPct(topIT2.valueIT) + ')' +
          (glVal > 0 ? ', contro il ' + fmtPct(glVal) + ' a livello globale.' : '.') + '</p>';
      }
    }

    /* ══════════════════════════════════════════
       S8 — Bot vs Human area
       ══════════════════════════════════════════ */

    function renderSection8() {
      var ORANGE = "#f5a623";

      function renderBH(elId, raw) {
        var el = clearAndGet(elId);
        if (!el) return;
        if (!raw || !raw.points || raw.points.length === 0) { noData(el); return; }

        var points = raw.points.map(function (p) { return { date: p.date, value: p.bot_pct }; });
        var maxY = 100;
        var chart = renderAreaChart(elId, points, { color: ORANGE, yMax: maxY, label: "Bot", width: 340 });
        el.appendChild(chart.svg);
      }

      renderBH("chart-s8-it", DATA.bot_human_it);
      renderBH("chart-s8-global", DATA.bot_human_global);

      var textEl = clearAndGet("text-s8");
      if (textEl) {
        var parts = [];
        var bhIT = DATA.bot_human_it;
        var bhGL = DATA.bot_human_global;
        if (bhIT && bhIT.points && bhIT.points.length > 0) {
          var lpIT = bhIT.points[bhIT.points.length - 1];
          parts.push("Il traffico bot in Italia è al " + fmtPct(lpIT.bot_pct) + ".");
          if (bhIT.points.length >= 2) {
            var prev = bhIT.points[bhIT.points.length - 2];
            if (lpIT.bot_pct > prev.bot_pct) parts.push("Il trend è in crescita.");
            else if (lpIT.bot_pct < prev.bot_pct) parts.push("Il trend è in calo.");
            else parts.push("Il trend è stabile.");
          }
        }
        if (bhGL && bhGL.points && bhGL.points.length > 0) {
          var lpGL = bhGL.points[bhGL.points.length - 1];
          parts.push("A livello globale è al " + fmtPct(lpGL.bot_pct) + ".");
        }
        if (parts.length > 0) {
          textEl.innerHTML = '<p class="text-sm text-on-surface-variant leading-relaxed">' + parts.join(" ") + '</p>';
        }
      }
    }

    /* ══════════════════════════════════════════
       S9 — Device type + OS
       ══════════════════════════════════════════ */

    function renderSection9() {
      function renderDevice(elId, raw) {
        var el = clearAndGet(elId);
        if (!el) return;
        if (!raw || !raw.points || raw.points.length === 0) { noData(el); return; }

        var points = raw.points.map(function (p) { return { date: p.date, value: p.mobile_pct }; });
        var chart = renderAreaChart(elId, points, { color: GREEN, yMax: 100, label: "Mobile", width: 340 });
        el.appendChild(chart.svg);
      }

      renderDevice("chart-s9-it", DATA.device_type_it);
      renderDevice("chart-s9-global", DATA.device_type_global);

      /* OS bars */
      var osEl = clearAndGet("chart-s9-os");
      if (osEl) {
        var osIT = DATA.os_it || [];
        var osGL = DATA.os_global || [];
        if (osIT.length === 0) { noData(osEl); }
        else {
          var glMap = {};
          for (var i = 0; i < osGL.length; i++) {
            glMap[osGL[i].os] = osGL[i].pct;
          }
          var barData = [];
          for (i = 0; i < osIT.length; i++) {
            barData.push({
              label: osIT[i].os,
              valueIT: osIT[i].pct,
              valueGlobal: glMap[osIT[i].os] || 0
            });
          }
          var chart = renderHBars("chart-s9-os", barData);
          if (chart) {
            osEl.appendChild(chart.svg);
            osEl.appendChild(chart.legendContainer);
          }
        }
      }

      /* Text */
      var textEl = clearAndGet("text-s9");
      if (textEl) {
        var parts = [];
        var dtIT = DATA.device_type_it;
        var dtGL = DATA.device_type_global;
        if (dtIT && dtIT.points && dtIT.points.length > 0) {
          var lpIT = dtIT.points[dtIT.points.length - 1];
          parts.push("Il mobile rappresenta il " + fmtPct(lpIT.mobile_pct) + " del traffico in Italia.");
        }
        if (dtGL && dtGL.points && dtGL.points.length > 0) {
          var lpGL = dtGL.points[dtGL.points.length - 1];
          parts.push("A livello globale è il " + fmtPct(lpGL.mobile_pct) + ".");
        }
        var osIT2 = DATA.os_it || [];
        if (osIT2.length > 0) {
          var topOS = osIT2.slice().sort(function (a, b) { return b.pct - a.pct; })[0];
          parts.push("Il sistema operativo più diffuso in Italia è " + topOS.os + " (" + fmtPct(topOS.pct) + ").");
        }
        if (parts.length > 0) {
          textEl.innerHTML = '<p class="text-sm text-on-surface-variant leading-relaxed">' + parts.join(" ") + '</p>';
        }
      }
    }

    /* ══════════════════════════════════════════
       Render all
       ══════════════════════════════════════════ */

    renderHero();
    renderKPICards();
    renderSection1();
    renderSection2();
    renderSection3();
    renderSection4();
    renderSection5();
    renderSection6();
    renderSection7();
    renderSection8();
    renderSection9();
  }
})();
