// Hydration-only. Il markup è già pre-renderizzato server-side via Jinja2
// SSG. Qui attiviamo solo: search filter locale, toggle cross-archive, card
// collapse mobile, redirect compat ?date=YYYY-MM-DD → /archivio/YYYY/MM/DD/,
// e refresh client-side delle date relative ("2 ore fa" → "8 ore fa")
// ricalcolate dal datetime attribute al load.

const ARCHIVE_SEARCH_DAYS = 7;
let archiveItemsCache = null;

(function init() {
  redirectLegacyDateParam();
  refreshRelativeDates();
  setupSearch();
  setupCardCollapse();
  preloadSearchFromQueryParam();
})();

function redirectLegacyDateParam() {
  const params = new URLSearchParams(window.location.search);
  const date = params.get("date");
  if (!date) return;
  const m = date.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return;
  window.location.replace(`/archivio/${m[1]}/${m[2]}/${m[3]}/`);
}

function refreshRelativeDates() {
  document.querySelectorAll(".card time[datetime]").forEach((el) => {
    const iso = el.getAttribute("datetime");
    if (!iso) return;
    el.textContent = formatRelative(iso);
  });
}

function formatRelative(iso) {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const now = new Date();
  const diff = now - d;
  const min = Math.floor(diff / 60000);
  const h = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (diff < 0) return d.toLocaleDateString("it-IT", { day: "numeric", month: "short" });
  if (min < 1) return "adesso";
  if (min < 60) return `${min} min fa`;
  if (h < 24) return `${h} h fa`;
  if (days < 2) return "ieri";
  if (days < 7) return `${days} giorni fa`;
  return d.toLocaleDateString("it-IT", { day: "numeric", month: "short", year: "numeric" });
}

function setupSearch() {
  const input = document.getElementById("search");
  const toggle = document.getElementById("search-archive-toggle");
  if (!input) return;

  const runSearch = async () => {
    const raw = input.value.trim().toLowerCase();
    const q = raw.replace(/[_\-/]+/g, " ");

    document.querySelectorAll("#top10-section .card, #categories-section .card").forEach((card) => {
      const blob = card.dataset.searchBlob || "";
      card.style.display = !q || blob.includes(q) ? "" : "none";
    });

    if (toggle && toggle.checked && q) {
      await showArchiveResults(q);
    } else {
      hideArchiveResults();
    }
  };

  input.addEventListener("input", runSearch);
  if (toggle) toggle.addEventListener("change", runSearch);
}

async function showArchiveResults(query) {
  const section = document.getElementById("archive-results");
  if (!section) return;
  const meta = document.getElementById("archive-results-meta");
  const list = document.getElementById("archive-results-list");
  section.hidden = false;
  meta.textContent = "Caricamento archivio…";

  try {
    if (archiveItemsCache === null) {
      archiveItemsCache = await loadArchiveItems(ARCHIVE_SEARCH_DAYS);
    }
  } catch (e) {
    meta.textContent = "Errore caricamento archivio: " + e.message;
    list.innerHTML = "";
    return;
  }

  const matches = archiveItemsCache.filter((entry) =>
    buildSearchBlob(entry.item).includes(query),
  );
  if (matches.length === 0) {
    meta.textContent = `Nessun risultato negli ultimi ${ARCHIVE_SEARCH_DAYS} giorni.`;
    list.innerHTML = "";
    return;
  }
  meta.textContent = `${matches.length} RESULTS IN LAST ${ARCHIVE_SEARCH_DAYS} DAYS // INDEXED ${archiveItemsCache.length} LOGS`;

  const byDate = {};
  for (const { date, item } of matches) {
    (byDate[date] = byDate[date] || []).push(item);
  }
  list.innerHTML = Object.entries(byDate)
    .sort(([a], [b]) => (a < b ? 1 : -1))
    .map(([date, items]) => {
      const cards = items.map((i) => renderArchiveSearchResult(i, date)).join("");
      return `<div class="flex flex-col gap-4">
        <div class="flex items-center justify-between border-b border-outline-variant pb-2">
          <h3 class="text-outline font-bold uppercase tracking-widest text-xs">[ ARCHIVE // ${escape(date)} ]</h3>
          <span class="text-outline text-[10px] font-mono">${items.length} HITS</span>
        </div>
        <div class="flex flex-col gap-4">${cards}</div>
      </div>`;
    })
    .join("");
}

function renderArchiveSearchResult(item, date) {
  const [y, m, d] = date.split("-");
  const path = item.importance >= 4 ? `/archivio/${y}/${m}/${d}/` : item.url;
  const stars = "★".repeat(item.importance) + "☆".repeat(5 - item.importance);
  return `<a href="${escape(path)}" class="block p-4 border-l-2 border-outline-variant bg-surface-container-lowest hover:bg-surface-container transition-colors">
    <h4 class="text-sm font-bold text-white hover:text-primary-container">${escape(item.title_it)}</h4>
    <p class="text-[10px] text-outline mt-1 font-mono uppercase">${escape(item.source.name)} · <span class="text-[#f5a623]">${stars}</span></p>
  </a>`;
}

function hideArchiveResults() {
  const section = document.getElementById("archive-results");
  if (!section) return;
  section.hidden = true;
  const list = document.getElementById("archive-results-list");
  if (list) list.innerHTML = "";
}

async function loadArchiveItems(days) {
  const idxResp = await fetch("/data/archive/index.json", { cache: "no-cache" });
  if (!idxResp.ok) throw new Error("index.json HTTP " + idxResp.status);
  const entries = await idxResp.json();
  const slice = entries.slice(0, days);

  const feeds = await Promise.all(
    slice.map(async (e) => {
      try {
        const r = await fetch(`/data/archive/${encodeURIComponent(e.file)}`, {
          cache: "no-cache",
        });
        if (!r.ok) return null;
        return { date: e.date, feed: await r.json() };
      } catch {
        return null;
      }
    }),
  );

  const items = [];
  for (const f of feeds) {
    if (!f || !f.feed || !Array.isArray(f.feed.items)) continue;
    for (const item of f.feed.items) {
      items.push({ date: f.date, item });
    }
  }
  return items;
}

function buildSearchBlob(item) {
  const parts = [
    item.title_it || "",
    item.title_original || "",
    item.summary_it || "",
    (item.tags || []).join(" "),
    item.source?.name || "",
    item.source?.id || "",
    item.category || "",
    item.url || "",
  ];
  return parts.join(" ").replace(/[_\-/]+/g, " ").toLowerCase();
}

function setupCardCollapse() {
  const mobileMql = window.matchMedia("(max-width: 767px)");
  document.addEventListener("click", (e) => {
    if (!mobileMql.matches) return;
    if (e.target.closest("a")) return;
    const card = e.target.closest(".card");
    if (!card) return;
    card.classList.toggle("expanded");
  });
}

function preloadSearchFromQueryParam() {
  const params = new URLSearchParams(window.location.search);
  const q = params.get("q");
  const cross = params.get("cross");
  if (!q) return;
  const input = document.getElementById("search");
  if (!input) return;
  input.value = q;
  if (cross) {
    const toggle = document.getElementById("search-archive-toggle");
    if (toggle) toggle.checked = true;
  }
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.focus();
}

function escape(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
