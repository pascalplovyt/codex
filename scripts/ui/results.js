function el(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatNumber(value) {
  return new Intl.NumberFormat().format(value || 0);
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || body.message || `Request failed: ${res.status}`);
  }
  return res.json();
}

function inferDataColumnClass(column, rows) {
  const name = String(column.column_name || "").toLowerCase();
  const type = String(column.data_type || "").toLowerCase();
  const values = rows
    .map((row) => row[column.column_name])
    .filter((value) => value != null)
    .map((value) => String(value));
  const maxLength = values.reduce((max, value) => Math.max(max, value.length), name.length);

  if (type.includes("timestamp") || type === "date" || type.includes("time")) return "col-datetime";
  if (type.includes("double") || type.includes("numeric") || type.includes("integer") || type.includes("bigint")) return "col-number";
  if (name === "approved" || name.endsWith("_id") || name.endsWith("_nr") || name.endsWith("_no") || name.endsWith("_code") || name.endsWith("_type") || name.endsWith("_ref") || name === "bill" || name === "currency" || name === "unit") {
    return maxLength <= 16 ? "col-compact" : "col-standard";
  }
  if (maxLength <= 12) return "col-compact";
  if (maxLength >= 28 || name.includes("name") || name.includes("country") || name.includes("carrier") || name.includes("origin")) return "col-wide";
  return "col-standard";
}

function renderRowsTable(columns, rows) {
  const headers = columns.map((column) => column.column_name);
  const colClasses = columns.map((column) => inferDataColumnClass(column, rows));
  const thead = headers.map((header, index) => `<th class="${colClasses[index]}">${escapeHtml(header)}</th>`).join("");
  const tbody = rows.map((row) => {
    const cells = headers.map((key, index) => {
      const raw = row[key] == null ? "" : String(row[key]);
      const safe = escapeHtml(raw);
      return `<td class="${colClasses[index]}" title="${safe}"><span>${safe}</span></td>`;
    }).join("");
    return `<tr>${cells}</tr>`;
  }).join("");

  return `
    <div class="rows-table-wrap">
      <table class="rows-data-table">
        <thead><tr>${thead}</tr></thead>
        <tbody>${tbody}</tbody>
      </table>
    </div>
  `;
}

function getRequestKey() {
  const params = new URLSearchParams(window.location.search);
  return params.get("key") || localStorage.getItem("ofbiz-results-latest");
}

function loadSavedRequest() {
  const key = getRequestKey();
  if (!key) throw new Error("No saved query was found. Run a query from the main dashboard first.");
  const raw = localStorage.getItem(key);
  if (!raw) throw new Error("The saved query request is no longer available. Run the query again from the main dashboard.");
  return { key, request: JSON.parse(raw) };
}

let current = null;

async function loadResults(pageOverride = null) {
  const loaded = loadSavedRequest();
  current = loaded;
  const payload = { ...loaded.request };
  if (pageOverride != null) payload.page = Math.max(1, pageOverride);

  el("results-table").innerHTML = `<div class="empty">Loading results...</div>`;
  const result = await fetchJson("/api/data/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  localStorage.setItem(loaded.key, JSON.stringify(payload));
  current.request = payload;

  el("results-title").textContent = `Results: ${result.object.object_name}`;
  el("results-object").textContent = result.object.object_name;
  el("results-count").textContent = `${formatNumber(result.total_rows)} rows`;
  el("results-page").textContent = `${result.page} / ${result.total_pages}`;
  el("results-sort").textContent = `${result.sort_column || "default"} ${result.sort_direction}`;
  el("results-filter-summary").textContent = result.filter_descriptions.length
    ? result.filter_descriptions.join(" | ")
    : "No filters applied.";

  if (!result.rows.length) {
    el("results-table").innerHTML = `<div class="empty">No rows matched the current query.</div>`;
  } else {
    el("results-table").innerHTML = renderRowsTable(result.columns, result.rows);
  }

  el("results-prev").disabled = result.page <= 1;
  el("results-next").disabled = result.page >= result.total_pages;
}

el("results-prev").addEventListener("click", () => {
  if (current) loadResults((current.request.page || 1) - 1);
});
el("results-next").addEventListener("click", () => {
  if (current) loadResults((current.request.page || 1) + 1);
});
el("results-refresh").addEventListener("click", () => loadResults());

loadResults().catch((error) => {
  el("results-filter-summary").textContent = error.message;
  el("results-table").innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
});
