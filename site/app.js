(async function () {
  const FEED_URL = "data/feed.json";

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

  let feed = null;

  try {
    const resp = await fetch(FEED_URL, { cache: "no-cache" });
    if (!resp.ok) throw new Error("feed fetch failed: " + resp.status);
    feed = await resp.json();
  } catch (e) {
    document.querySelector("main").innerHTML =
      '<p style="color: #cc0000;">Impossibile caricare il feed: ' + e.message + "</p>";
    return;
  }

  renderMeta(feed);
  renderTop10(feed);
  renderCategories(feed);
  renderFailed(feed);
  setupSearch(feed);

  const params = new URLSearchParams(window.location.search);
  const tag = params.get("tag");
  if (tag) applyTagFilter(feed, tag);
})();

function renderMeta(feed) {
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
  document.getElementById("meta").textContent =
    `${dateStr}, ${timeStr} · ${s.sources_checked} fonti · ${s.items_after_dedup} notizie · €${s.ai_cost_eur.toFixed(3)} costo AI`;
}

function renderCard(item) {
  const stars = "★".repeat(item.importance) + "☆".repeat(5 - item.importance);
  const srcType = item.is_doc_change ? "doc-change" : "";
  const tags = (item.tags || []).map((t) => `<span class="tag">${escape(t)}</span>`).join("");
  const date = formatPublishedAt(item.published_at);
  return `
    <div class="card ${srcType}" data-item-id="${escape(item.id)}" data-tags="${(item.tags || []).join(",")}">
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
  container.innerHTML = feed.top10.map((id) => renderCard(byId[id])).filter(Boolean).join("");
}

function renderCategories(feed) {
  const container = document.getElementById("categories");
  const byId = Object.fromEntries(feed.items.map((i) => [i.id, i]));
  const catContainers = Object.entries(feed.categories).map(([catId, ids]) => {
    const label = CATEGORY_LABELS[catId] || catId;
    const cards = ids.map((id) => renderCard(byId[id])).filter(Boolean).join("");
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
  input.addEventListener("input", () => {
    const q = input.value.toLowerCase().trim();
    document.querySelectorAll(".card").forEach((card) => {
      const text = card.textContent.toLowerCase();
      card.style.display = !q || text.includes(q) ? "" : "none";
    });
  });
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
