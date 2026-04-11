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

const CATEGORY_ICONS = {
  google_updates: "history",
  google_docs_change: "warning",
  ai_models: "smart_toy",
  ai_overviews_llm_seo: "auto_awesome",
  technical_seo: "build",
  content_eeat: "article",
  tools_platforms: "settings",
  industry_news: "public",
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
  renderSectionTitles(date);
  renderTop10(feed);
  renderCategories(feed);
  renderFailed(feed);
  setupSearch(feed);
  setupCardCollapse();

  const tag = params.get("tag");
  if (tag) applyTagFilter(feed, tag);
})();

/**
 * Se siamo in modalità snapshot (?date=YYYY-MM-DD) appende la data
 * formattata "DD MM YYYY" ai titoli delle sezioni TOP 10 e CATEGORIE.
 * In modalità normale non tocca nulla.
 */
function renderSectionTitles(archiveDate) {
  if (!archiveDate) return;
  const m = String(archiveDate).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return;
  const suffix = `${m[3]} ${m[2]} ${m[1]}`;
  const top = document.getElementById("top10-title");
  const cat = document.getElementById("categories-title");
  if (top) top.textContent = `> TOP 10 DEL GIORNO ${suffix}`;
  if (cat) cat.textContent = `> TUTTE PER CATEGORIA ${suffix}`;
}

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
  const status = archiveDate
    ? `SNAPSHOT ${archiveDate} // ${dateStr}, ${timeStr}`
    : `SYSTEM STATUS: OPTIMAL // LAST REFRESH ${dateStr}, ${timeStr}`;
  const statline = `${s.sources_checked} SOURCES // ${s.items_after_dedup} LOGS // ${s.doc_changes_detected} DOC CHANGES // €${s.ai_cost_eur.toFixed(3)} AI COST`;
  metaEl.innerHTML = archiveDate
    ? `${escape(status)} &nbsp;//&nbsp; ${escape(statline)} &nbsp;//&nbsp; <a class="text-primary-container hover:underline" href="./">RETURN_TO_TODAY</a>`
    : `${escape(status)} &nbsp;//&nbsp; ${escape(statline)}`;
}

/**
 * Card in stile Top-10: include numero d'ordine 01..NN e bottone READ_LOG.
 * Su mobile solo la sezione "head" (titolo + source line) è visibile; il body
 * (summary + tags + READ_LOG) appare cliccando la card. Su desktop è sempre
 * espanso.
 */
function renderTop10Card(item, order) {
  const stars = "★".repeat(item.importance) + "☆".repeat(5 - item.importance);
  const date = formatPublishedAt(item.published_at);
  const searchBlob = buildSearchBlob(item);
  const idSuffix = shortId(item);
  const num = String(order).padStart(2, "0");
  const doc = item.is_doc_change ? "doc-change" : "";
  return `
    <article class="card ${doc} bg-surface p-4 sm:p-6 flex flex-col md:flex-row md:items-start md:justify-between group hover:bg-surface-container transition-colors"
      data-item-id="${escape(item.id)}" data-tags="${(item.tags || []).join(",")}" data-search-blob="${escape(searchBlob)}">
      <div class="flex items-start gap-4 flex-grow min-w-0">
        <span class="text-primary-container font-bold text-lg shrink-0">${num}.</span>
        <div class="max-w-3xl min-w-0 flex-1">
          <h3 class="text-base sm:text-xl font-medium group-hover:text-primary-container transition-colors">${escape(item.title_it)}</h3>
          <p class="text-[10px] sm:text-[11px] text-outline mt-1 mb-2 uppercase font-mono break-words">
            ${escape(item.source.name)} · <span class="text-[#f5a623] whitespace-nowrap">${stars}</span> · <time class="whitespace-nowrap" datetime="${escape(item.published_at)}" title="${escape(date.absolute)}">${escape(date.relative)}</time> <span class="whitespace-nowrap">// ID: ${escape(idSuffix)}</span>
          </p>
          <div class="card-body">
            <p class="text-sm text-on-surface-variant font-mono leading-relaxed">${escape(item.summary_it)}</p>
            ${renderTagsHtml(item.tags)}
          </div>
        </div>
      </div>
      <div class="card-body mt-4 md:mt-0 md:ml-6 shrink-0">
        <a class="inline-block text-xs border border-outline px-3 py-1 hover:border-primary-container hover:text-primary-container transition-all uppercase tracking-wider"
           href="${escape(item.url)}" target="_blank" rel="noopener">READ_LOG</a>
      </div>
    </article>
  `;
}

/**
 * Card compatta per la sezione categorie. Bordo sinistro verde per items con
 * importance=5, grigio per il resto. Stesso comportamento mobile collapsible.
 */
function renderCategoryCard(item, extraClass = "") {
  const stars = "★".repeat(item.importance) + "☆".repeat(5 - item.importance);
  const date = formatPublishedAt(item.published_at);
  const searchBlob = buildSearchBlob(item);
  const idSuffix = shortId(item);
  const borderClass =
    item.importance >= 5 || item.is_doc_change
      ? "border-l-2 border-primary-container bg-surface-container-low"
      : "border-l-2 border-outline-variant bg-surface-container-lowest";
  const doc = item.is_doc_change ? "doc-change" : "";
  return `
    <article class="card ${doc} ${extraClass} ${borderClass} p-4 sm:p-6 flex flex-col md:flex-row md:justify-between md:items-start group hover:bg-surface-container transition-colors"
      data-item-id="${escape(item.id)}" data-tags="${(item.tags || []).join(",")}" data-search-blob="${escape(searchBlob)}">
      <div class="max-w-4xl min-w-0 flex-1">
        <h4 class="text-base sm:text-lg font-bold mb-1 group-hover:text-primary-container transition-colors">${escape(item.title_it)}</h4>
        <p class="text-[10px] sm:text-[11px] text-outline mb-2 font-mono uppercase break-words">
          ${escape(item.source.name)} · <span class="text-[#f5a623] whitespace-nowrap">${stars}</span> · <time class="whitespace-nowrap" datetime="${escape(item.published_at)}" title="${escape(date.absolute)}">${escape(date.relative)}</time> <span class="whitespace-nowrap">// ID: ${escape(idSuffix)}</span>
        </p>
        <div class="card-body">
          <p class="text-sm text-on-surface-variant font-mono">${escape(item.summary_it)}</p>
          ${renderTagsHtml(item.tags)}
        </div>
      </div>
      <a class="card-body text-outline text-xs font-mono mt-4 md:mt-0 md:ml-6 shrink-0 hover:text-primary-container transition-colors uppercase tracking-wider"
         href="${escape(item.url)}" target="_blank" rel="noopener">LOG_OPEN →</a>
    </article>
  `;
}

function renderTagsHtml(tags) {
  if (!tags || tags.length === 0) return "";
  const chips = tags
    .map(
      (t) =>
        `<span class="inline-block text-[10px] uppercase tracking-wider px-2 py-0.5 mr-1 mt-2 border border-outline-variant text-outline font-mono">${escape(t)}</span>`,
    )
    .join("");
  return `<div class="mt-2">${chips}</div>`;
}

function shortId(item) {
  // Prendiamo gli ultimi 4 char del raw_hash (o item.id) in maiuscolo
  const src = item.raw_hash || item.id || "";
  const m = String(src).replace(/[^a-zA-Z0-9]/g, "");
  return (m.slice(-4) || "0000").toUpperCase();
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
  const cards = [];
  feed.top10.forEach((id, idx) => {
    const item = byId[id];
    if (item) cards.push(renderTop10Card(item, idx + 1));
  });
  container.innerHTML = cards.join("");
}

function renderCategories(feed) {
  const container = document.getElementById("categories");
  const byId = Object.fromEntries(feed.items.map((i) => [i.id, i]));
  const sections = Object.entries(feed.categories)
    .filter(([, ids]) => ids.length > 0)
    .map(([catId, ids]) => {
      const label = CATEGORY_LABELS[catId] || catId;
      const icon = CATEGORY_ICONS[catId] || "folder";
      const cards = ids
        .map((id) => (byId[id] ? renderCategoryCard(byId[id]) : null))
        .filter(Boolean)
        .join("");
      return `
        <section class="flex flex-col gap-6">
          <div class="flex items-center justify-between border-b border-primary-container pb-2">
            <h3 class="text-primary-container font-bold uppercase tracking-widest text-sm">[ ${escape(label)} ]</h3>
            <span class="material-symbols-outlined text-primary-container text-sm">${escape(icon)}</span>
          </div>
          <div class="flex flex-col gap-4">${cards}</div>
        </section>
      `;
    });
  container.innerHTML = sections.join("");
}

function renderFailed(feed) {
  if (!feed.failed_sources || feed.failed_sources.length === 0) return;
  const section = document.getElementById("failed");
  section.hidden = false;
  const list = document.getElementById("failed-list");
  list.innerHTML = feed.failed_sources
    .map(
      (f) =>
        `<li class="border-l-2 border-error px-3 py-2 bg-surface-container-lowest">
          <span class="text-error uppercase">[ERR]</span>
          <code class="text-white">${escape(f.id)}</code>:
          <span class="text-on-surface-variant">${escape(f.error)}</span>
        </li>`,
    )
    .join("");
}

/**
 * Su mobile (< md breakpoint), le card hanno il body nascosto via CSS. Un
 * click sulla card lo espande. Click sui link interni non intercettati.
 * Su desktop il CSS forza il body visibile, quindi questo handler diventa
 * no-op.
 */
function setupCardCollapse() {
  const mobileMql = window.matchMedia("(max-width: 767px)");
  document.addEventListener("click", (e) => {
    if (!mobileMql.matches) return;
    const link = e.target.closest("a");
    if (link) return; // lascia andare i click sui link
    const card = e.target.closest(".card");
    if (!card) return;
    card.classList.toggle("expanded");
  });
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

  meta.textContent = `${matches.length} RESULTS IN LAST ${ARCHIVE_SEARCH_DAYS} DAYS // INDEXED ${archiveItemsCache.length} LOGS`;
  // Raggruppa per data
  const byDate = {};
  for (const { date, item } of matches) {
    (byDate[date] = byDate[date] || []).push(item);
  }
  list.innerHTML = Object.entries(byDate)
    .sort(([a], [b]) => (a < b ? 1 : -1))
    .map(([date, items]) => {
      const cards = items.map((i) => renderCategoryCard(i, "from-archive")).join("");
      return `
        <div class="flex flex-col gap-4">
          <div class="flex items-center justify-between border-b border-outline-variant pb-2">
            <h3 class="text-outline font-bold uppercase tracking-widest text-xs">[ ARCHIVE // ${escape(date)} ]</h3>
            <span class="text-outline text-[10px] font-mono">${items.length} HITS</span>
          </div>
          <div class="flex flex-col gap-4">${cards}</div>
        </div>
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
