(async function () {
  const meta = document.getElementById("archive-meta");
  const list = document.getElementById("archive-list");
  try {
    const resp = await fetch("data/archive/index.json", { cache: "no-cache" });
    if (!resp.ok) throw new Error("index.json HTTP " + resp.status);
    const entries = await resp.json();
    if (!Array.isArray(entries) || entries.length === 0) {
      meta.textContent = "NO ARCHIVED LOGS";
      return;
    }
    meta.textContent = `${entries.length} LOG FILES AVAILABLE // ORDER: MOST RECENT FIRST`;
    list.innerHTML = entries
      .map((e, idx) => {
        const d = new Date(e.date + "T00:00:00Z");
        const label = d.toLocaleDateString("it-IT", {
          weekday: "long",
          year: "numeric",
          month: "long",
          day: "numeric",
        });
        const num = String(idx + 1).padStart(3, "0");
        return `
          <li>
            <a class="group flex items-center justify-between px-4 py-3 border border-outline-variant bg-surface-container-low hover:border-primary-container hover:bg-surface-container transition-colors"
               href="./?date=${encodeURIComponent(e.date)}">
              <div class="flex items-center gap-4">
                <span class="text-primary-container font-bold font-mono text-sm">${num}.</span>
                <span class="font-mono text-sm text-white">${escape(e.date)}</span>
                <span class="text-xs text-outline uppercase tracking-widest hidden md:inline">${escape(label)}</span>
              </div>
              <span class="text-xs text-outline uppercase tracking-widest group-hover:text-primary-container transition-colors">OPEN_LOG →</span>
            </a>
          </li>
        `;
      })
      .join("");
  } catch (err) {
    meta.textContent = "ERROR LOADING INDEX: " + err.message;
  }
})();

function escape(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
