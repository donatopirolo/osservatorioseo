/**
 * Handler della search bar globale su pagine NON-home (archive.html,
 * docs.html). Qui non c'è un feed locale da filtrare in-place: quando
 * l'utente preme Enter (o cambia il toggle con una query attiva) viene
 * reindirizzato alla home con ?q=<query> e ?cross=1 se il toggle è on.
 * La home (app.js) legge questi query param e precompila automaticamente.
 */
(function () {
  const input = document.getElementById("search");
  const toggle = document.getElementById("search-archive-toggle");
  if (!input) return;

  function redirect() {
    const q = input.value.trim();
    if (!q) return;
    const params = new URLSearchParams();
    params.set("q", q);
    if (toggle && toggle.checked) params.set("cross", "1");
    window.location.href = "./?" + params.toString();
  }

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      redirect();
    }
  });
  if (toggle) {
    toggle.addEventListener("change", () => {
      if (input.value.trim()) redirect();
    });
  }
})();
