const TYPE_LABELS = {
  official: "UFFICIALE",
  media: "MEDIA",
  independent: "INDIPENDENTE",
  tool_vendor: "TOOL VENDOR",
  social: "SOCIAL",
  doc_change: "DOC CHANGE",
};

(async function () {
  const sourcesMeta = document.getElementById("sources-meta");
  const sourcesList = document.getElementById("sources-list");
  const dwMeta = document.getElementById("docwatcher-meta");
  const dwList = document.getElementById("docwatcher-list");

  try {
    const resp = await fetch("data/config_snapshot.json", { cache: "no-cache" });
    if (!resp.ok) throw new Error("config_snapshot.json HTTP " + resp.status);
    const config = await resp.json();

    renderSources(config.sources || [], sourcesMeta, sourcesList);
    renderDocWatcher(config.doc_watcher_pages || [], dwMeta, dwList);
  } catch (err) {
    sourcesMeta.textContent = "ERROR: " + err.message;
    dwMeta.textContent = "ERROR: " + err.message;
  }
})();

function renderSources(sources, metaEl, listEl) {
  // Il backend (load_sources) già filtra le fonti disabled, quindi qui
  // riceviamo solo quelle attivamente fetchate.
  const enabled = sources;
  const disabled = [];
  metaEl.textContent = `${enabled.length} FONTI ATTIVE`;

  // Raggruppa per type
  const byType = {};
  for (const s of enabled) {
    (byType[s.type] = byType[s.type] || []).push(s);
  }
  const typeOrder = ["official", "media", "independent", "tool_vendor", "social"];

  const sections = typeOrder
    .filter((t) => byType[t])
    .map((t) => {
      const label = TYPE_LABELS[t] || t.toUpperCase();
      const rows = byType[t]
        .sort((a, b) => b.authority - a.authority)
        .map((s) => renderSourceRow(s))
        .join("");
      return `
        <div class="mb-6">
          <h3 class="text-primary-container font-bold uppercase tracking-widest text-xs mb-3 pb-1 border-b border-outline-variant">
            [ ${escape(label)} // ${byType[t].length} ]
          </h3>
          <div class="flex flex-col gap-1">${rows}</div>
        </div>
      `;
    })
    .join("");

  let disabledHtml = "";
  if (disabled.length > 0) {
    const rows = disabled.map((s) => renderSourceRow(s, true)).join("");
    disabledHtml = `
      <div class="mb-6 opacity-60">
        <h3 class="text-outline font-bold uppercase tracking-widest text-xs mb-3 pb-1 border-b border-outline-variant">
          [ DISABILITATE // ${disabled.length} ]
        </h3>
        <div class="flex flex-col gap-1">${rows}</div>
      </div>
    `;
  }

  listEl.innerHTML = sections + disabledHtml;
}

function renderSourceRow(s, isDisabled = false) {
  const stars = "★".repeat(s.authority);
  const hostname = s.url ? safeHostname(s.url) : "";
  const fetcherClass =
    s.fetcher === "playwright"
      ? "text-primary-container"
      : s.fetcher === "scraper"
        ? "text-white"
        : "text-outline";
  const strike = isDisabled ? "line-through" : "";
  return `
    <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-2 px-4 py-2 border border-outline-variant bg-surface-container-lowest font-mono text-xs ${strike}">
      <div class="flex items-center gap-3 flex-wrap">
        <span class="text-[#f5a623]">${stars}</span>
        <span class="text-white">${escape(s.name)}</span>
        <span class="text-outline text-[10px] uppercase">${escape(s.id)}</span>
      </div>
      <div class="flex items-center gap-3 text-[10px] uppercase">
        <span class="${fetcherClass}">${escape(s.fetcher)}</span>
        ${hostname ? `<a href="${escape(s.url)}" target="_blank" rel="noopener" class="text-outline hover:text-primary-container">${escape(hostname)} →</a>` : ""}
      </div>
    </div>
  `;
}

function renderDocWatcher(pages, metaEl, listEl) {
  metaEl.textContent = `${pages.length} PAGINE SORVEGLIATE`;
  listEl.innerHTML = pages
    .sort((a, b) => b.importance - a.importance)
    .map((p) => {
      const stars = "★".repeat(p.importance);
      return `
        <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-2 px-4 py-2 border border-outline-variant bg-surface-container-lowest font-mono text-xs">
          <div class="flex items-center gap-3 flex-wrap">
            <span class="text-[#f5a623]">${stars}</span>
            <span class="text-white">${escape(p.name)}</span>
            <span class="text-outline text-[10px] uppercase">[${escape(p.type)}]</span>
          </div>
          <a href="${escape(p.url)}" target="_blank" rel="noopener" class="text-outline hover:text-primary-container text-[10px] uppercase">
            ${escape(safeHostname(p.url))} →
          </a>
        </div>
      `;
    })
    .join("");
}

function safeHostname(url) {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

function escape(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
