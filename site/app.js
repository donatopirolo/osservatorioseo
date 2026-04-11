const CATEGORY_LABELS = {
  google_updates: "Google Updates",
  google_docs_change: "Google Docs Change ⚠️",
  ai_models: "AI Models",
  ai_overviews_llm_seo: "AI Overviews & LLM SEO",
  technical_seo: "Technical SEO",
  content_eeat: "Content & E-E-A-T",
  tools_platforms: "Tools & Platforms",
  industry_news: "Industry News",
};

const ARCHIVE_SEARCH_DAYS = 7; // quanti giorni carichiamo nel cross-archive search

// Cache globale per gli items caricati dall'archivio (lazy, solo quando serve)
let archiveItemsCache = null;

/**
 * Costruisce il blob di ricerca per un item: titolo italiano + titolo originale
 * (inglese) + summary + tag + source name + source id + category + URL. Gli
 * underscore nei tag/id/category diventano spazi, così le query "gpt-5" e
 * "gpt 5" matchano contro il tag "gpt_5_mini". Tutto lowercase.
 */
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

(async function () {
  const params = new URLSearchParams(window.location.search);
  const date = params.get("date"); // se presente → modalità archivio singolo giorno

  const feedUrl = date ? `data/archive/${encodeURIComponent(date)}.json` : "data/feed.json";
  let feed = null;

  try {
    const resp = await fetch(feedUrl, { cache: "no-cache" });
    if (!resp.ok) throw new Error("feed fetch failed: HTTP " + resp.status);
    feed = await resp.json();
  } catch (e) {
    document.querySelector("main").innerHTML =
      '<p style="color: #cc0000;">Impossibile caricare il feed (' +
      escape(feedUrl) +
      "): " +
      escape(e.message) +
      "</p>";
    return;
  }

  renderMeta(feed, date);
  renderTop10(feed);
  renderCategories(feed);
  renderFailed(feed);
  setupSearch(feed);

  const tag = params.get("tag");
  if (tag) applyTagFilter(feed, tag);
})();

function renderMeta(feed, archiveDate) {
  const local = new Date(feed.generated_at_local);
  const dateStr = local.toLocaleDateString("it-IT", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  const timeStr = local.toLocaleTimeString("it-IT", {
    hour: "2-digit",
    minute: "2-digit",
  });
  const s = feed.stats;
  const metaEl = document.getElementById("meta");
  const base = `${dateStr}, ${timeStr} · ${s.sources_checked} fonti · ${s.items_after_dedup} notizie · €${s.ai_cost_eur.toFixed(3)} costo AI`;
  if (archiveDate) {
    metaEl.innerHTML =
      `<strong>📜 Stai vedendo lo snapshot del ${escape(archiveDate)}.</strong> ` +
      escape(base) +
      ` · <a href="./">Torna a oggi</a>`;
  } else {
    metaEl.textContent = base;
  }
}

function renderCard(item, extraClass = "") {
  const stars = "★".repeat(item.importance) + "☆".repeat(5 - item.importance);
  const typeClass = item.is_doc_change ? "doc-change" : "";
  const tags = (item.tags || []).map((t) => `<span class="tag">${escape(t)}</span>`).join("");
  const date = formatPublishedAt(item.published_at);
  const classes = ["card", typeClass, extraClass].filter(Boolean).join(" ");
  const searchBlob = buildSearchBlob(item);
  return `
    <div class="${classes}" data-item-id="${escape(item.id)}" data-tags="${(item.tags || []).join(",")}" data-search-blob="${escape(searchBlob)}">
      <h3>${escape(item.title_it)}</h3>
      <p class="source-line">
        ${escape(item.source.name)} · <span class="stars">${stars}</span> ·
        <time datetime="${escape(item.published_at)}" title="${escape(date.absolute)}">${escape(date.relative)}</time>
      </p>
      <p class="summary">${escape(item.summary_it)}</p>
      <p>${tags}</p>
      <a class="readmore" href="${escape(item.url)}" target="_blank" rel="noopener">→ ${hostname(item.url)}</a>
    </div>
  `;
}

function formatPublishedAt(iso) {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return { relative: "", absolute: "" };
  const now = new Date();
  const diffMs = now - d;
  const diffMin = Math.floor(diffMs / 60000);
  const diffH = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  let relative;
  if (diffMs < 0) relative = d.toLocaleDateString("it-IT", { day: "numeric", month: "short" });
  else if (diffMin < 1) relative = "adesso";
  else if (diffMin < 60) relative = `${diffMin} min fa`;
  else if (diffH < 24) relative = `${diffH} h fa`;
  else if (diffDays < 2) relative = "ieri";
  else if (diffDays < 7) relative = `${diffDays} giorni fa`;
  else relative = d.toLocaleDateString("it-IT", { day: "numeric", month: "short", year: "numeric" });

  const absolute = d.toLocaleString("it-IT", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return { relative, absolute };
}

function renderTop10(feed) {
  const container = document.getElementById("top10");
  const byId = Object.fromEntries(feed.items.map((i) => [i.id, i]));
  container.innerHTML = feed.top10
    .map((id) => renderCard(byId[id]))
    .filter(Boolean)
    .join("");
}

function renderCategories(feed) {
  const container = document.getElementById("categories");
  const byId = Object.fromEntries(feed.items.map((i) => [i.id, i]));
  const catContainers = Object.entries(feed.categories).map(([catId, ids]) => {
    const label = CATEGORY_LABELS[catId] || catId;
    const cards = ids
      .map((id) => renderCard(byId[id]))
      .filter(Boolean)
      .join("");
    return `
      <details open>
        <summary>${label} (${ids.length})</summary>
        ${cards}
      </details>
    `;
  });
  container.innerHTML = catContainers.join("");
}

function renderFailed(feed) {
  if (!feed.failed_sources || feed.failed_sources.length === 0) return;
  const section = document.getElementById("failed");
  section.hidden = false;
  const list = document.getElementById("failed-list");
  list.innerHTML = feed.failed_sources
    .map((f) => `<li><code>${escape(f.id)}</code>: ${escape(f.error)}</li>`)
    .join("");
}

function setupSearch(feed) {
  const input = document.getElementById("search");
  const toggle = document.getElementById("search-archive-toggle");

  const runSearch = async () => {
    const rawQ = input.value.trim().toLowerCase();
    // Normalizza la query allo stesso modo del blob: trattini/underscore → spazi
    const q = rawQ.replace(/[_\-/]+/g, " ");

    // Filtra le card del feed corrente (top10 + categorie) usando data-search-blob
    document.querySelectorAll("#top10-section .card, #categories-section .card").forEach((card) => {
      const blob = card.dataset.searchBlob || "";
      card.style.display = !q || blob.includes(q) ? "" : "none";
    });

    // Se il toggle archive è attivo e c'è una query non vuota, mostra risultati archivio
    if (toggle && toggle.checked && q) {
      await showArchiveResults(q);
    } else {
      hideArchiveResults();
    }
  };

  input.addEventListener("input", runSearch);
  if (toggle) {
    toggle.addEventListener("change", runSearch);
  }
}

async function showArchiveResults(query) {
  const section = document.getElementById("archive-results");
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

  const matches = archiveItemsCache.filter((entry) => {
    return buildSearchBlob(entry.item).includes(query);
  });

  if (matches.length === 0) {
    meta.textContent = `Nessun risultato negli ultimi ${ARCHIVE_SEARCH_DAYS} giorni di archivio (${archiveItemsCache.length} items indicizzati).`;
    list.innerHTML = "";
    return;
  }

  meta.textContent = `${matches.length} risultati negli ultimi ${ARCHIVE_SEARCH_DAYS} giorni (su ${archiveItemsCache.length} items indicizzati).`;
  // Raggruppa per data
  const byDate = {};
  for (const { date, item } of matches) {
    (byDate[date] = byDate[date] || []).push(item);
  }
  list.innerHTML = Object.entries(byDate)
    .sort(([a], [b]) => (a < b ? 1 : -1))
    .map(([date, items]) => {
      const cards = items.map((i) => renderCard(i, "from-archive")).join("");
      return `
        <details open>
          <summary>📅 ${escape(date)} (${items.length})</summary>
          ${cards}
        </details>
      `;
    })
    .join("");
}

function hideArchiveResults() {
  const section = document.getElementById("archive-results");
  section.hidden = true;
  const list = document.getElementById("archive-results-list");
  list.innerHTML = "";
}

async function loadArchiveItems(days) {
  // Carica l'indice, prendi le ultime `days` date, fetch in parallelo, estrai tutti gli items
  const idxResp = await fetch("data/archive/index.json", { cache: "no-cache" });
  if (!idxResp.ok) throw new Error("index.json HTTP " + idxResp.status);
  const entries = await idxResp.json();
  const slice = entries.slice(0, days);

  const feeds = await Promise.all(
    slice.map(async (e) => {
      try {
        const r = await fetch(`data/archive/${encodeURIComponent(e.file)}`, { cache: "no-cache" });
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

function applyTagFilter(feed, tag) {
  document.querySelectorAll(".card").forEach((card) => {
    const tags = (card.dataset.tags || "").split(",");
    card.style.display = tags.includes(tag) ? "" : "none";
  });
}

function escape(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function hostname(url) {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}
