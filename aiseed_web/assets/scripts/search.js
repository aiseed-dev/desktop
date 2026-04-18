// Minimal search: POST nothing, fetch read-only public API.
// Progressive enhancement: form also works as a plain GET fallback to /search/.

const API = "https://api.aiseed.dev";

function initSearch(form) {
  if (!form) return;
  const input = form.querySelector("input[name='q']");
  const results = document.querySelector("#search-results");
  if (!input || !results) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    results.textContent = "検索中…";
    try {
      const res = await fetch(`${API}/search?q=${encodeURIComponent(q)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      render(results, data);
    } catch (err) {
      results.textContent = "検索に失敗しました。しばらく経ってから再度お試しください。";
    }
  });
}

function render(container, data) {
  container.replaceChildren();
  const items = Array.isArray(data) ? data : (data.items || []);
  if (items.length === 0) {
    container.textContent = "該当する結果がありませんでした。";
    return;
  }
  const ul = document.createElement("ul");
  ul.className = "search-list";
  for (const item of items) {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = item.url || `/${item.type}s/${item.id}.html`;
    a.textContent = item.name || item.title || item.id;
    li.appendChild(a);
    ul.appendChild(li);
  }
  container.appendChild(ul);
}

document.addEventListener("DOMContentLoaded", () => {
  initSearch(document.querySelector("#search-form"));
});
