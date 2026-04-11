(async function () {
  const meta = document.getElementById("archive-meta");
  const list = document.getElementById("archive-list");
  try {
    const resp = await fetch("data/archive/index.json", { cache: "no-cache" });
    if (!resp.ok) throw new Error("index.json HTTP " + resp.status);
    const entries = await resp.json();
    if (!Array.isArray(entries) || entries.length === 0) {
      meta.textContent = "Nessun file archivio disponibile.";
      return;
    }
    meta.textContent = `${entries.length} giornate disponibili (ordine dal più recente)`;
    list.innerHTML = entries
      .map((e) => {
        const d = new Date(e.date + "T00:00:00Z");
        const label = d.toLocaleDateString("it-IT", {
          weekday: "long",
          year: "numeric",
          month: "long",
          day: "numeric",
        });
        return `
          <li class="archive-entry">
            <a href="./?date=${encodeURIComponent(e.date)}">
              <span class="archive-date">${escape(e.date)}</span>
              <span class="archive-label">${escape(label)}</span>
            </a>
          </li>
        `;
      })
      .join("");
  } catch (err) {
    meta.textContent = "Impossibile caricare l'indice archivio: " + err.message;
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
