const state = {
  objects: [],
  filteredObjects: [],
  selectedObject: null,
  selectedMeta: null,
  selectedData: null,
  jobs: [],
  syncSummary: [],
  runHistory: [],
  config: null,
  excludedPatternsDraft: [],
  schemaObjects: null,
  reports: [],
  reportDraft: {
    name: "My Saved Report",
    entries: [],
  },
  pollTimer: null,
  query: {
    search: "",
    page: 1,
    pageSize: 100,
    sortColumn: "",
    sortDirection: "asc",
  },
  fieldSearches: [
    { column: "", value: "" },
    { column: "", value: "" },
    { column: "", value: "" },
  ],
  latestResultsRequest: null,
};

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || body.message || `Request failed: ${res.status}`);
  }
  return res.json();
}

function el(id) {
  return document.getElementById(id);
}

function formatNumber(value) {
  return new Intl.NumberFormat().format(value || 0);
}

function formatDate(value) {
  if (!value) return "n/a";
  return new Date(value * 1000 || value).toLocaleString();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function tableMarkup(headers, rows) {
  return `
    <table>
      <thead>
        <tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr>
      </thead>
      <tbody>
        ${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell ?? ""}</td>`).join("")}</tr>`).join("")}
      </tbody>
    </table>
  `;
}

function inferDataColumnClass(column, rows) {
  const name = String(column.column_name || "").toLowerCase();
  const type = String(column.data_type || "").toLowerCase();
  const values = rows
    .map((row) => row[column.column_name])
    .filter((value) => value != null)
    .map((value) => String(value));
  const maxLength = values.reduce((max, value) => Math.max(max, value.length), name.length);

  if (type.includes("timestamp") || type === "date" || type.includes("time")) {
    return "col-datetime";
  }
  if (type.includes("double") || type.includes("numeric") || type.includes("integer") || type.includes("bigint")) {
    return "col-number";
  }
  if (name === "approved" || name.endsWith("_id") || name.endsWith("_nr") || name.endsWith("_no") || name.endsWith("_code") || name.endsWith("_type") || name.endsWith("_ref") || name === "bill" || name === "currency" || name === "unit") {
    return maxLength <= 16 ? "col-compact" : "col-standard";
  }
  if (maxLength <= 12) {
    return "col-compact";
  }
  if (maxLength >= 28 || name.includes("name") || name.includes("country") || name.includes("carrier") || name.includes("origin")) {
    return "col-wide";
  }
  return "col-standard";
}

function setButtonsDisabled(disabled) {
  document.querySelectorAll(".action-btn").forEach((button) => {
    if (["save-credentials", "run-query", "save-report", "export-report", "add-selection", "replace-report", "open-settings", "exit-control-center"].includes(button.id)) {
      return;
    }
    button.disabled = disabled;
  });
}

function setExcludedTables(tables) {
  el("excluded-tables").innerHTML = tables.map((table) => `<span class="pill">${table}</span>`).join("");
}

function normalizeExcludedPatternInput(value) {
  return String(value || "").trim().toLowerCase();
}

function renderExcludedPatternEditor() {
  const root = el("excluded-table-editor");
  const items = state.excludedPatternsDraft.length ? state.excludedPatternsDraft : [""];
  root.innerHTML = items.map((pattern, index) => `
    <div class="excluded-editor-row">
      <input id="excluded-pattern-${index}" type="text" value="${escapeHtml(pattern)}" placeholder="table_name or pattern like site_*">
      <button class="chip-btn" data-remove-excluded-pattern="${index}">Delete</button>
    </div>
  `).join("");

  root.querySelectorAll("[data-remove-excluded-pattern]").forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.dataset.removeExcludedPattern);
      state.excludedPatternsDraft.splice(index, 1);
      renderExcludedPatternEditor();
    });
  });
}

function collectExcludedPatternDraft() {
  const draft = [];
  const inputs = document.querySelectorAll("[id^='excluded-pattern-']");
  inputs.forEach((input) => {
    const value = normalizeExcludedPatternInput(input.value);
    if (value) {
      draft.push(value);
    }
  });
  const deduped = [];
  const seen = new Set();
  for (const value of draft) {
    if (seen.has(value)) continue;
    seen.add(value);
    deduped.push(value);
  }
  return deduped;
}

function openExcludedTablesModal() {
  state.excludedPatternsDraft = [...(state.config?.sync_defaults?.excluded_tables || [])];
  renderExcludedPatternEditor();
  el("excluded-tables-status").textContent = "These exclusions will apply to dashboard-launched syncs and the sync engine defaults.";
  el("excluded-tables-modal").classList.remove("hidden");
}

function closeExcludedTablesModal() {
  el("excluded-tables-modal").classList.add("hidden");
}

async function saveExcludedTables() {
  try {
    const excludedTables = collectExcludedPatternDraft();
    el("excluded-tables-status").textContent = "Saving exclusions...";
    const payload = {
      remote: {
        base_url: el("remote-base-url").value.trim(),
        username: el("remote-username").value.trim(),
        password: "",
        group: el("remote-group").value.trim(),
        timeout_seconds: Number(el("remote-timeout").value || 600),
      },
      local: state.config?.local || {},
      sync_defaults: {
        excluded_tables: excludedTables,
      },
    };
    await fetchJson("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await loadConfig();
    state.excludedPatternsDraft = [...(state.config?.sync_defaults?.excluded_tables || [])];
    renderExcludedPatternEditor();
    el("excluded-tables-status").textContent = "Excluded sync-table patterns saved.";
  } catch (error) {
    el("excluded-tables-status").textContent = error.message;
  }
}

function renderOverviewCards(targetId, cards) {
  const root = el(targetId);
  root.innerHTML = cards.map((card) => `
    <article class="overview-card">
      <span>${card.label}</span>
      <strong>${card.value}</strong>
    </article>
  `).join("");
}

function pathFileLink(filePath, label) {
  if (!filePath) return label || "";
  const href = filePath.replaceAll("\\", "/");
  return `<a href="file:///${href}">${escapeHtml(label || filePath)}</a>`;
}

function renderObjectList() {
  const list = el("table-list");
  list.innerHTML = "";
  const term = el("table-search").value.trim();
  const selectedChip = el("selected-object-chip");
  selectedChip.textContent = state.selectedObject ? `Selected: ${state.selectedObject}` : "No object selected";

  if (!term) {
    el("object-picker-status").textContent = "Start typing to find a table or view, then click it to open it in the main pane.";
    list.innerHTML = `<div class="empty">Matching tables will appear here as you type.</div>`;
    return;
  }

  if (!state.filteredObjects.length) {
    el("object-picker-status").textContent = `No matches for "${term}".`;
    list.innerHTML = `<div class="empty">No matching tables or views.</div>`;
    return;
  }

  const shownObjects = state.filteredObjects.slice(0, 12);
  el("object-picker-status").textContent = `${shownObjects.length} match${shownObjects.length === 1 ? "" : "es"} shown${state.filteredObjects.length > shownObjects.length ? ` out of ${state.filteredObjects.length}` : ""}. Click one to open it in the main pane.`;

  for (const object of shownObjects) {
    const item = document.createElement("button");
    item.className = `table-item${state.selectedObject === object.object_name ? " active" : ""}`;
    item.innerHTML = `
      <div class="table-topline">
        <strong>${object.object_name}</strong>
        <span class="badge neutral">${object.object_type}</span>
      </div>
      <div class="table-meta">${object.column_count} columns · ${object.constraint_count} constraints · ${object.index_count} indexes</div>
    `;
    item.addEventListener("click", () => selectObject(object.object_name));
    list.appendChild(item);
  }
}

function renderJobs() {
  const root = el("jobs-panel");
  const runningRuns = state.runHistory.filter((run) => run.status === "running");
  if (!state.jobs.length && !runningRuns.length) {
    root.innerHTML = `<div class="empty">No jobs yet. Launch one from the left rail.</div>`;
    return;
  }
  const jobCards = state.jobs.map((job) => `
    <article class="job-card">
      <div class="job-head">
        <strong>${job.label}</strong>
        <span class="badge ${job.status}">${job.status}</span>
      </div>
      <div class="job-meta">
        <span>${formatDate(job.started_at)}</span>
      </div>
      <div class="log-box">${escapeHtml(job.stderr_tail || job.stdout_tail || "Running...")}</div>
    </article>
  `);
  const runCards = runningRuns.map((run) => `
    <article class="job-card">
      <div class="job-head">
        <strong>${run.mode === "full" ? "Full Sync" : "Incremental Sync"}</strong>
        <span class="badge running">running</span>
      </div>
      <div class="job-meta">
        <span>database run ${run.run_id}</span>
        <span>${formatDate(run.started_at)}</span>
      </div>
      <div class="log-box">Tracked from database history. No live stdout is attached to this run card.</div>
    </article>
  `);
  root.innerHTML = [...jobCards, ...runCards].join("");
}

function renderSyncSummary() {
  const root = el("sync-summary-panel");
  if (!state.syncSummary.length && !state.runHistory.length) {
    root.innerHTML = `<div class="empty">No sync runs recorded yet.</div>`;
    return;
  }

  const historyRows = state.runHistory.slice(0, 6).map((item) => [
    item.run_id,
    item.mode,
    item.status,
    item.table_filter || "all tables",
  ]);

  root.innerHTML = historyRows.length
    ? tableMarkup(["Run", "Mode", "Status", "Filter"], historyRows)
    : `<div class="empty">No run history yet.</div>`;
}

async function refreshControlPanels() {
  try {
    const data = await fetchJson("/api/control/jobs");
    state.jobs = data.jobs || [];
    state.syncSummary = data.sync_summary || [];
    state.runHistory = data.run_history || [];
    renderJobs();
    renderSyncSummary();

    const running = state.jobs.some((job) => job.status === "running") || state.runHistory.some((run) => run.status === "running");
    setButtonsDisabled(running);
    const latest = state.jobs[0];
    if (latest) {
      el("job-status").textContent = `${latest.label}: ${latest.status}\nStarted: ${formatDate(latest.started_at)}\n${latest.stdout_tail || latest.stderr_tail || ""}`.trim();
    } else {
      const latestRunning = state.runHistory.find((run) => run.status === "running");
      if (latestRunning) {
        el("job-status").textContent = `${latestRunning.mode === "full" ? "Full Sync" : "Incremental Sync"} is running.\nStarted: ${formatDate(latestRunning.started_at)}\nTracking via database run history.`;
      } else if (data.database_error) {
        el("job-status").textContent = `Dashboard is up. Local PostgreSQL is unavailable: ${data.database_error}`;
      } else {
        el("job-status").textContent = "No sync job is running right now.";
      }
    }
  } catch (error) {
    el("job-status").textContent = error.message;
  }
}

async function runAction(action, extra = {}) {
  try {
    setButtonsDisabled(true);
    const payload = {
      action,
      tables: el("tables-filter").value.trim(),
      ...extra,
    };
    const job = await fetchJson("/api/control/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    el("job-status").textContent = `Started ${job.label}.`;
    if (action === "refresh_metadata") {
      el("metadata-status").textContent = "Refreshing remote metadata snapshot...";
    }
    await refreshControlPanels();
  } catch (error) {
    el("job-status").textContent = error.message;
    setButtonsDisabled(false);
  }
}

async function loadConfig() {
  const data = await fetchJson("/api/config");
  state.config = data;
  setExcludedTables(data.sync_defaults?.excluded_tables || []);
  state.excludedPatternsDraft = [...(data.sync_defaults?.excluded_tables || [])];
  el("remote-base-url").value = data.remote?.base_url || "";
  el("remote-username").value = data.remote?.username || "";
  el("remote-group").value = data.remote?.group || "org.ofbiz";
  el("remote-timeout").value = data.remote?.timeout_seconds || 600;
  el("credentials-status").textContent = data.remote?.password_set
    ? "A password is already saved. Leave the field blank to keep it."
    : "No password is saved yet.";
}

async function saveConfig() {
  try {
    el("credentials-status").textContent = "Saving...";
    const payload = {
      remote: {
        base_url: el("remote-base-url").value.trim(),
        username: el("remote-username").value.trim(),
        password: el("remote-password").value,
        group: el("remote-group").value.trim(),
        timeout_seconds: Number(el("remote-timeout").value || 600),
      },
      local: state.config?.local || {},
    };
    await fetchJson("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    el("remote-password").value = "";
    await loadConfig();
    el("credentials-status").textContent = "Saved.";
  } catch (error) {
    el("credentials-status").textContent = error.message;
  }
}

async function exitControlCenter() {
  try {
    const confirmed = window.confirm("Exit the Control Center and shut down the local PostgreSQL clone cleanly?");
    if (!confirmed) {
      return;
    }
    const exitButton = el("exit-control-center");
    exitButton.disabled = true;
    exitButton.textContent = "Shutting Down...";
    el("job-status").textContent = "Shutting down dashboard and local PostgreSQL...";
    document.body.insertAdjacentHTML("beforeend", `
      <div id="shutdown-overlay" style="position:fixed;inset:0;background:rgba(238,246,243,0.9);display:grid;place-items:center;z-index:999;">
        <div style="padding:28px 34px;border-radius:24px;background:#ffffff;border:1px solid rgba(22,53,84,0.14);box-shadow:0 18px 40px rgba(22,53,84,0.12);text-align:center;color:#163554;font-family:Georgia,serif;">
          <div style="font-size:24px;font-weight:700;">Closing Control Center</div>
          <div style="margin-top:10px;font-size:14px;color:#46626f;">The dashboard and local PostgreSQL clone are being shut down cleanly.</div>
        </div>
      </div>
    `);
    await fetchJson("/api/control/exit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    window.setTimeout(() => {
      el("job-status").textContent = "Shutdown started. This page will stop responding once the dashboard exits.";
    }, 300);
    window.setTimeout(() => {
      document.body.innerHTML = '<div style="padding:40px;font-family:Georgia,serif;text-align:center;color:#163554;background:#eef6f3;min-height:100vh;">Control Center closed. The local dashboard and database shutdown were requested.</div>';
    }, 1800);
  } catch (error) {
    el("job-status").textContent = error.message;
  }
}

async function loadSchemaObjects() {
  const data = await fetchJson("/api/schema/objects");
  state.schemaObjects = data;
  const cards = [
    { label: "Tables", value: formatNumber(data.tables) },
    { label: "Views", value: formatNumber(data.views) },
    { label: "Sequences", value: formatNumber(data.sequences) },
    { label: "Routines", value: formatNumber(data.routines) },
    { label: "Triggers", value: formatNumber(data.triggers) },
  ];
  renderOverviewCards("schema-object-summary", cards);

  const refreshedAt = data.metadata?.refreshed_at_utc
    ? new Date(data.metadata.refreshed_at_utc).toLocaleString()
    : "unknown";
  el("metadata-status").textContent = `Last snapshot: ${refreshedAt}`;
  el("metadata-summary").textContent = data.views
    ? `Tables and views appear together in the explorer. Metadata snapshot refreshed ${refreshedAt}.`
    : `The latest remote metadata snapshot refreshed ${refreshedAt} and reports no SQL views, sequences, routines, or triggers exposed by the remote PostgreSQL schema.`;
}

function applyObjectSearch() {
  const typeFilter = el("object-type-filter").value;
  const term = el("table-search").value.toLowerCase().trim();
  state.filteredObjects = state.objects.filter((object) => {
    const typeMatches = typeFilter === "all" || object.object_type === typeFilter;
    const textMatches = !term || object.object_name.toLowerCase().includes(term);
    return typeMatches && textMatches;
  });
  renderObjectList();
}

async function loadObjects() {
  const payload = await fetchJson("/api/objects");
  state.objects = payload.objects || [];
  state.filteredObjects = [...state.objects];
  el("table-count").textContent = formatNumber(state.objects.length);
  renderObjectList();
}

function renderFieldSearches() {
  const root = el("column-filters");
  if (!state.selectedMeta?.columns?.length) {
    root.innerHTML = `<div class="empty">Select a table or view first.</div>`;
    return;
  }

  const options = ['<option value="">Choose field</option>']
    .concat(state.selectedMeta.columns.map((column) => `<option value="${column.column_name}">${column.column_name}</option>`))
    .join("");

  root.innerHTML = state.fieldSearches.map((search, index) => `
    <div class="fixed-filter-row">
      <span>Field ${index + 1}</span>
      <select id="field-search-column-${index}" class="filter-select">${options}</select>
      <input id="field-search-value-${index}" class="filter-input" type="search" placeholder="Partial text match">
    </div>
  `).join("");

  state.fieldSearches.forEach((search, index) => {
    el(`field-search-column-${index}`).value = search.column || "";
    el(`field-search-value-${index}`).value = search.value || "";
  });
}

function currentFiltersPayload() {
  return state.fieldSearches
    .map((search, index) => ({
      column: el(`field-search-column-${index}`)?.value || "",
      operator: "contains",
      value: el(`field-search-value-${index}`)?.value || "",
    }))
    .filter((item) => item.column && item.value);
}

function currentQueryRequest(page = 1) {
  return {
    object_name: state.selectedObject,
    page,
    page_size: Number(el("page-size").value || 100),
    search: el("data-search").value.trim(),
    filters: currentFiltersPayload(),
    sort_column: el("sort-column").value || "",
    sort_direction: el("sort-direction").value || "asc",
  };
}

function persistLatestResultsRequest(request) {
  const key = `ofbiz-results-${Date.now()}`;
  localStorage.setItem(key, JSON.stringify(request));
  localStorage.setItem("ofbiz-results-latest", key);
  state.latestResultsRequest = key;
  return key;
}

function resultsTabUrlFromRequest(request) {
  return `/query-results?payload=${encodeURIComponent(JSON.stringify(request))}`;
}

function openResultsTab(request = null) {
  const effectiveRequest = request || (state.latestResultsRequest ? JSON.parse(localStorage.getItem(state.latestResultsRequest) || "null") : null);
  if (!effectiveRequest) {
    el("results-tab-status").textContent = "Run a query first so there is something to open.";
    return;
  }
  const newTab = window.open(resultsTabUrlFromRequest(effectiveRequest), "_blank", "noopener");
  if (newTab) {
    el("results-tab-status").textContent = "Results opened in a separate tab.";
  } else {
    el("results-tab-status").textContent = "The browser blocked the new tab. Please allow pop-ups for this page and try again.";
  }
}

function resetMainPane() {
  state.selectedObject = null;
  state.selectedMeta = null;
  state.selectedData = null;
  el("table-title").textContent = "Choose a table or view";
  el("table-subtitle").textContent = "Search in Objects on the left, click a matching table, then use Data Explorer to filter records.";
  renderOverviewCards("overview", [
    { label: "Columns", value: "-" },
    { label: "Constraints", value: "-" },
    { label: "Indexes", value: "-" },
    { label: "Local Rows", value: "-" },
  ]);
  el("object-info-panel").innerHTML = `<div class="empty">Select a table or view from the Objects list.</div>`;
  el("columns-panel").innerHTML = `<div class="empty">Columns will appear here after you choose an object.</div>`;
  el("constraints-panel").innerHTML = `<div class="empty">Constraints will appear here after you choose an object.</div>`;
  el("indexes-panel").innerHTML = `<div class="empty">Indexes will appear here after you choose an object.</div>`;
  el("query-status").textContent = "Choose an object to begin.";
  el("page-indicator").textContent = "No query yet";
  el("query-result-summary").textContent = "Run a query to open matching rows in a separate tab.";
  el("results-tab-status").textContent = "The separate results tab uses the full browser width for rows.";
  el("sort-column").innerHTML = "";
  renderFieldSearches();
  renderObjectList();
}

function friendlyObjectLoadError(error) {
  const message = String(error?.message || "");
  if (message.includes("connection to server at \"127.0.0.1\"") || message.includes("Connection refused")) {
    return "The local PostgreSQL clone is still waking up, so rows cannot be loaded yet. Wait a few seconds, then click the table again.";
  }
  return message || "Object details could not be loaded.";
}

async function selectObject(objectName) {
  state.selectedObject = objectName;
  state.query.page = 1;
  state.selectedData = null;
  renderObjectList();
  window.scrollTo({ top: 0, behavior: "smooth" });
  el("table-title").textContent = objectName;
  el("table-subtitle").textContent = `Opening ${objectName}...`;
  renderOverviewCards("overview", [
    { label: "Columns", value: "..." },
    { label: "Constraints", value: "..." },
    { label: "Indexes", value: "..." },
    { label: "Local Rows", value: "..." },
  ]);
  el("object-info-panel").innerHTML = `<div class="empty">Loading object details...</div>`;
  el("columns-panel").innerHTML = `<div class="empty">Loading columns...</div>`;
  el("constraints-panel").innerHTML = `<div class="empty">Loading constraints...</div>`;
  el("indexes-panel").innerHTML = `<div class="empty">Loading indexes...</div>`;
  try {
    const meta = await fetchJson(`/api/object/${encodeURIComponent(objectName)}`);
    state.selectedMeta = meta;
    state.query.sortColumn = meta.columns?.[0]?.column_name || "";
    el("data-search").value = "";
    el("sort-column").innerHTML = meta.columns.map((column) => `<option value="${column.column_name}">${column.column_name}</option>`).join("");
    el("sort-column").value = state.query.sortColumn;
    state.fieldSearches = [
      { column: "", value: "" },
      { column: "", value: "" },
      { column: "", value: "" },
    ];
    renderFieldSearches();
    renderObjectMeta();
    await runQuery();
    el("object-picker-status").textContent = `${objectName} is open in the main pane. Adjust Data Explorer to work with its records.`;
  } catch (error) {
    state.selectedMeta = null;
    const friendlyMessage = friendlyObjectLoadError(error);
    el("table-subtitle").textContent = friendlyMessage;
    el("object-info-panel").innerHTML = `<div class="empty">Object details could not be loaded.</div>`;
    el("columns-panel").innerHTML = `<div class="empty">Columns could not be loaded.</div>`;
    el("constraints-panel").innerHTML = `<div class="empty">Constraints could not be loaded.</div>`;
    el("indexes-panel").innerHTML = `<div class="empty">Indexes could not be loaded.</div>`;
    el("query-status").textContent = friendlyMessage;
    renderOverviewCards("overview", [
      { label: "Columns", value: "n/a" },
      { label: "Constraints", value: "n/a" },
      { label: "Indexes", value: "n/a" },
      { label: "Local Rows", value: "n/a" },
    ]);
  }
}

function renderObjectMeta() {
  if (!state.selectedMeta) return;
  const object = state.selectedMeta.object;
  const viewNote = object.object_type === "view" && !state.schemaObjects?.views
    ? "Views are supported here, but the current schema export still reports zero saved view definitions."
    : "";

  el("table-title").textContent = object.object_name;
  el("table-subtitle").textContent = `Schema ${object.table_schema} · ${object.object_type} · local rows ${formatNumber(state.selectedMeta.local_row_count)}${viewNote ? ` · ${viewNote}` : ""}`;

  renderOverviewCards("overview", [
    { label: "Columns", value: formatNumber(state.selectedMeta.columns.length) },
    { label: "Constraints", value: formatNumber(state.selectedMeta.constraints.length) },
    { label: "Indexes", value: formatNumber(state.selectedMeta.indexes.length) },
    { label: "Local Rows", value: formatNumber(state.selectedMeta.local_row_count) },
  ]);

  el("object-info-panel").innerHTML = `
    <div class="detail-grid">
      <div><span class="detail-label">Object</span><strong>${object.object_name}</strong></div>
      <div><span class="detail-label">Type</span><strong>${object.object_type}</strong></div>
      <div><span class="detail-label">Schema</span><strong>${object.table_schema}</strong></div>
      <div><span class="detail-label">Source Rows</span><strong>${formatNumber(object.source_record_count || 0)}</strong></div>
    </div>
  `;

  el("columns-panel").innerHTML = tableMarkup(
    ["Pos", "Column", "Type", "Nullable", "Default"],
    state.selectedMeta.columns.map((column) => [
      column.ordinal_position,
      column.column_name,
      column.character_maximum_length
        ? `${column.data_type}(${column.character_maximum_length})`
        : column.numeric_precision
          ? `${column.data_type}(${column.numeric_precision}${column.numeric_scale ? `,${column.numeric_scale}` : ""})`
          : column.data_type,
      column.is_nullable,
      column.column_default || '<span class="pill">none</span>',
    ]),
  );

  el("constraints-panel").innerHTML = state.selectedMeta.constraints.length
    ? tableMarkup(
      ["Name", "Type", "Columns", "References"],
      state.selectedMeta.constraints.map((constraint) => [
        constraint.constraint_name,
        constraint.constraint_type,
        constraint.columns || "",
        constraint.foreign_table_name
          ? `${constraint.foreign_table_schema}.${constraint.foreign_table_name} (${constraint.foreign_columns})`
          : "",
      ]),
    )
    : `<div class="empty">No constraints recorded for this ${object.object_type}.</div>`;

  el("indexes-panel").innerHTML = state.selectedMeta.indexes.length
    ? tableMarkup(["Index", "Definition"], state.selectedMeta.indexes.map((index) => [index.index_name, index.index_definition]))
    : `<div class="empty">No indexes recorded for this ${object.object_type}.</div>`;
}

async function runQuery(page = 1) {
  if (!state.selectedObject) return;
  const request = currentQueryRequest(page);
  state.query.page = request.page;
  state.query.search = request.search;
  state.query.pageSize = request.page_size;
  state.query.sortColumn = request.sort_column;
  state.query.sortDirection = request.sort_direction;

  try {
    el("query-status").textContent = "Loading rows...";
    const result = await fetchJson("/api/data/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    state.selectedData = result;
    persistLatestResultsRequest(request);
    openResultsTab(request);

    const fieldSummary = currentFiltersPayload()
      .map((item) => `${item.column} contains "${item.value}"`)
      .join(" | ");
    el("query-status").textContent = `Showing page ${result.page} of ${result.total_pages}. ${formatNumber(result.total_rows)} matching rows.${fieldSummary ? ` ${fieldSummary}` : ""}`;
    el("page-indicator").textContent = `${formatNumber(result.total_rows)} rows`;
    el("query-result-summary").textContent = `${result.object.object_name} · page ${result.page}/${result.total_pages} · sorted by ${result.sort_column || "default"} ${result.sort_direction}`;
  } catch (error) {
    el("query-status").textContent = error.message;
  }
}

function buildDraftEntry() {
  if (!state.selectedObject) return null;
  return {
    object_name: state.selectedObject,
    object_type: state.selectedMeta?.object?.object_type || "table",
    search: el("data-search").value.trim(),
    filters: currentFiltersPayload(),
    sort_column: el("sort-column").value || "",
    sort_direction: el("sort-direction").value || "asc",
  };
}

function renderDraftReport() {
  el("report-name").value = state.reportDraft.name;
  el("report-draft-summary").textContent = state.reportDraft.entries.length
    ? `${state.reportDraft.entries.length} sheet selection${state.reportDraft.entries.length === 1 ? "" : "s"} ready for save/export.`
    : "No sheets in the current draft.";

  const root = el("report-draft-panel");
  if (!state.reportDraft.entries.length) {
    root.innerHTML = `<div class="empty">Add the current filtered table or view to start a multi-sheet report.</div>`;
    return;
  }

  root.innerHTML = state.reportDraft.entries.map((entry, index) => `
    <article class="draft-card">
      <div class="job-head">
        <strong>${index + 1}. ${entry.object_name}</strong>
        <button class="chip-btn" data-remove-entry="${index}">Remove</button>
      </div>
      <div class="table-meta">${entry.object_type} · global search: ${entry.search || "none"} · sort: ${entry.sort_column || "default"} ${entry.sort_direction}</div>
      <div class="helper">${entry.filters.length ? entry.filters.map((filter) => `${filter.column} contains ${filter.value}`).join(" | ") : "No field-specific search values."}</div>
    </article>
  `).join("");

  root.querySelectorAll("[data-remove-entry]").forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.dataset.removeEntry);
      state.reportDraft.entries.splice(index, 1);
      renderDraftReport();
    });
  });
}

function renderSavedReports() {
  const root = el("saved-reports-panel");
  if (!state.reports.length) {
    root.innerHTML = `<div class="empty">No saved reports yet.</div>`;
    return;
  }
  root.innerHTML = state.reports.map((report, index) => `
    <article class="draft-card">
      <div class="job-head">
        <strong>${report.name}</strong>
        <button class="chip-btn" data-load-report="${index}">Load</button>
      </div>
      <div class="table-meta">${report.entries.length} sheet${report.entries.length === 1 ? "" : "s"} · saved ${report.saved_at || "recently"}</div>
      <div class="helper">${report.file_name ? `Saved file: ${report.file_name}` : ""}</div>
      <div class="helper">${report.entries.map((entry) => entry.object_name).join(", ")}</div>
    </article>
  `).join("");

  root.querySelectorAll("[data-load-report]").forEach((button) => {
    button.addEventListener("click", () => {
      const report = state.reports[Number(button.dataset.loadReport)];
      state.reportDraft = {
        report_id: report.report_id,
        name: report.name,
        entries: [...report.entries],
      };
      renderDraftReport();
      el("report-status").textContent = `Loaded saved report "${report.name}".`;
    });
  });
}

async function loadReports() {
  const payload = await fetchJson("/api/reports");
  state.reports = payload.reports || [];
  renderSavedReports();
}

async function saveReport() {
  try {
    state.reportDraft.name = el("report-name").value.trim() || "My Saved Report";
    const payload = {
      report_id: state.reportDraft.report_id,
      name: state.reportDraft.name,
      entries: state.reportDraft.entries,
    };
    const response = await fetchJson("/api/reports/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.reportDraft.report_id = response.report.report_id;
    el("report-status").innerHTML = `Saved report "${escapeHtml(response.report.name)}" to ${pathFileLink(response.report.file_path, response.report.file_name || response.report.file_path)}.`;
    await loadReports();
  } catch (error) {
    el("report-status").textContent = error.message;
  }
}

async function exportReport() {
  try {
    state.reportDraft.name = el("report-name").value.trim() || "My Saved Report";
    const payload = {
      name: state.reportDraft.name,
      entries: state.reportDraft.entries,
      export_limit: Number(el("export-limit").value || 10000),
    };
    const response = await fetchJson("/api/reports/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    el("report-status").innerHTML = `Saved workbook with ${response.sheet_count} sheet${response.sheet_count === 1 ? "" : "s"} to ${pathFileLink(response.file_path, response.file_name)}.`;
  } catch (error) {
    el("report-status").textContent = error.message;
  }
}

function addCurrentSelectionToReport() {
  const entry = buildDraftEntry();
  if (!entry) {
    el("report-status").textContent = "Select a table or view first.";
    return;
  }
  state.reportDraft.name = el("report-name").value.trim() || state.reportDraft.name;
  state.reportDraft.entries.push(entry);
  renderDraftReport();
  el("report-status").textContent = `Added ${entry.object_name} to the report draft.`;
}

function replaceDraftWithCurrentSelection() {
  const entry = buildDraftEntry();
  if (!entry) {
    el("report-status").textContent = "Select a table or view first.";
    return;
  }
  state.reportDraft.name = el("report-name").value.trim() || state.reportDraft.name;
  state.reportDraft.entries = [entry];
  renderDraftReport();
  el("report-status").textContent = `Replaced the draft with ${entry.object_name}.`;
}

function openSettingsModal() {
  el("settings-modal").classList.remove("hidden");
}

function closeSettingsModal() {
  el("settings-modal").classList.add("hidden");
}

async function load() {
  try {
    const health = await fetchJson("/api/health");
    el("health-status").textContent = health.status === "ok" ? "Connected" : "Issue";
  } catch {
    el("health-status").textContent = "Offline";
  }

  await Promise.all([loadObjects(), loadConfig(), loadSchemaObjects(), loadReports()]);
  resetMainPane();
  renderDraftReport();
  await refreshControlPanels();
  state.pollTimer = window.setInterval(refreshControlPanels, 5000);
}

document.querySelectorAll("[data-action]").forEach((button) => {
  button.addEventListener("click", () => runAction(button.dataset.action));
});

el("open-settings").addEventListener("click", openSettingsModal);
el("open-excluded-tables").addEventListener("click", openExcludedTablesModal);
el("exit-control-center").addEventListener("click", exitControlCenter);
el("close-settings").addEventListener("click", closeSettingsModal);
el("dismiss-settings").addEventListener("click", closeSettingsModal);
el("close-excluded-tables").addEventListener("click", closeExcludedTablesModal);
el("dismiss-excluded-tables").addEventListener("click", closeExcludedTablesModal);
el("add-excluded-pattern").addEventListener("click", () => {
  state.excludedPatternsDraft = collectExcludedPatternDraft();
  state.excludedPatternsDraft.push("");
  renderExcludedPatternEditor();
});
el("save-excluded-tables").addEventListener("click", saveExcludedTables);
el("register-weekly").addEventListener("click", () => {
  runAction("register_weekly", {
    day_of_week: el("schedule-day").value,
    time: el("schedule-time").value || "02:00",
  });
});

el("save-credentials").addEventListener("click", saveConfig);
el("refresh-metadata").addEventListener("click", async () => {
  await runAction("refresh_metadata");
  window.setTimeout(async () => {
    await loadSchemaObjects();
    await loadObjects();
    await loadReports();
    if (state.selectedObject && state.objects.some((item) => item.object_name === state.selectedObject)) {
      await selectObject(state.selectedObject);
    }
  }, 2500);
});

el("table-search").addEventListener("input", applyObjectSearch);
el("object-type-filter").addEventListener("change", applyObjectSearch);
el("run-query").addEventListener("click", () => runQuery(1));
el("open-results-tab").addEventListener("click", () => openResultsTab(currentQueryRequest(state.query.page || 1)));
el("add-selection").addEventListener("click", addCurrentSelectionToReport);
el("replace-report").addEventListener("click", replaceDraftWithCurrentSelection);
el("save-report").addEventListener("click", saveReport);
el("export-report").addEventListener("click", exportReport);
el("report-name").addEventListener("input", (event) => {
  state.reportDraft.name = event.target.value;
});
el("page-size").addEventListener("change", () => runQuery(1));
el("data-search").addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    runQuery(1);
  }
});

load().catch((error) => {
  el("health-status").textContent = "Error";
  el("table-subtitle").textContent = error.message;
});
