const state = {
  apiKey: localStorage.getItem("ims_api_key") || "",
  user: null,
  items: [],
  selectedItemIds: new Set(),
  editingItemId: null,
  currentView: "dashboard-view",
};

const titles = {
  "login-view": {
    title: "Sign In",
    subtitle: "Authenticate to access inventory workflows.",
  },
  "dashboard-view": {
    title: "Dashboard",
    subtitle: "Track stock health and recent operational movement.",
  },
  "inventory-view": {
    title: "Inventory",
    subtitle: "Manage items, quantities, statuses, and bulk operations.",
  },
  "search-view": {
    title: "Search",
    subtitle: "Run standard filters or natural language AI search.",
  },
  "ai-view": {
    title: "AI Insights",
    subtitle: "Use reorder copilot and anomaly detection with fallback resilience.",
  },
};

const els = {
  nav: document.getElementById("app-nav"),
  viewTitle: document.getElementById("view-title"),
  viewSubtitle: document.getElementById("view-subtitle"),
  roleBadge: document.getElementById("role-badge"),
  logoutBtn: document.getElementById("logout-btn"),
  feedback: document.getElementById("global-feedback"),

  loginView: document.getElementById("login-view"),
  loginForm: document.getElementById("login-form"),
  loginSubmitBtn: document.getElementById("login-submit-btn"),
  loginError: document.getElementById("login-error"),

  dashboardView: document.getElementById("dashboard-view"),
  dashboardLoading: document.getElementById("dashboard-loading"),
  dashboardError: document.getElementById("dashboard-error"),
  kpiTotalItems: document.getElementById("kpi-total-items"),
  kpiActiveItems: document.getElementById("kpi-active-items"),
  kpiTotalQty: document.getElementById("kpi-total-qty"),
  kpiLowStock: document.getElementById("kpi-low-stock"),
  categoryTableBody: document.getElementById("category-table-body"),
  activityList: document.getElementById("activity-list"),

  inventoryView: document.getElementById("inventory-view"),
  inventorySearch: document.getElementById("inventory-search"),
  inventoryCategoryFilter: document.getElementById("inventory-category-filter"),
  inventoryStatusFilter: document.getElementById("inventory-status-filter"),
  inventorySort: document.getElementById("inventory-sort"),
  inventoryRefresh: document.getElementById("inventory-refresh"),
  newItemBtn: document.getElementById("new-item-btn"),
  inventoryLoading: document.getElementById("inventory-loading"),
  inventoryError: document.getElementById("inventory-error"),
  inventoryTableBody: document.getElementById("inventory-table-body"),
  inventoryEmpty: document.getElementById("inventory-empty"),
  emptyCreateBtn: document.getElementById("empty-create-btn"),
  selectAllItems: document.getElementById("select-all-items"),
  bulkBar: document.getElementById("bulk-bar"),
  bulkSelectedCount: document.getElementById("bulk-selected-count"),
  bulkStatusSelect: document.getElementById("bulk-status-select"),
  bulkApplyBtn: document.getElementById("bulk-apply-btn"),

  searchView: document.getElementById("search-view"),
  nlSearchForm: document.getElementById("nl-search-form"),
  nlSearchSubmitBtn: document.getElementById("nl-search-submit-btn"),
  nlQuery: document.getElementById("nl-query"),
  nlSearchMeta: document.getElementById("nl-search-meta"),
  standardSearchForm: document.getElementById("standard-search-form"),
  stdSearchSubmitBtn: document.getElementById("std-search-submit-btn"),
  stdQuery: document.getElementById("std-query"),
  stdCategory: document.getElementById("std-category"),
  stdStatus: document.getElementById("std-status"),
  stdMinQty: document.getElementById("std-min-qty"),
  stdMaxQty: document.getElementById("std-max-qty"),
  searchLoading: document.getElementById("search-loading"),
  searchError: document.getElementById("search-error"),
  searchEmpty: document.getElementById("search-empty"),
  resetSearchBtn: document.getElementById("reset-search-btn"),
  searchResultsBody: document.getElementById("search-results-body"),

  aiView: document.getElementById("ai-view"),
  refreshReorderBtn: document.getElementById("refresh-reorder-btn"),
  reorderSource: document.getElementById("reorder-source"),
  reorderLoading: document.getElementById("reorder-loading"),
  reorderError: document.getElementById("reorder-error"),
  reorderBody: document.getElementById("reorder-body"),
  refreshAnomalyBtn: document.getElementById("refresh-anomaly-btn"),
  anomalySource: document.getElementById("anomaly-source"),
  anomalyLoading: document.getElementById("anomaly-loading"),
  anomalyError: document.getElementById("anomaly-error"),
  anomalyList: document.getElementById("anomaly-list"),

  itemModal: document.getElementById("item-modal"),
  itemForm: document.getElementById("item-form"),
  itemFormTitle: document.getElementById("item-form-title"),
  itemFormError: document.getElementById("item-form-error"),
  itemId: document.getElementById("item-id"),
  itemSku: document.getElementById("item-sku"),
  itemName: document.getElementById("item-name"),
  itemCategory: document.getElementById("item-category"),
  itemQuantity: document.getElementById("item-quantity"),
  itemThreshold: document.getElementById("item-threshold"),
  itemUnitCost: document.getElementById("item-unit-cost"),
  itemStatus: document.getElementById("item-status"),
  itemDetails: document.getElementById("item-details"),
  closeItemModal: document.getElementById("close-item-modal"),
  itemFormSave: document.getElementById("item-form-save"),
};

const allViews = [
  els.loginView,
  els.dashboardView,
  els.inventoryView,
  els.searchView,
  els.aiView,
];

function setFeedback(message, isError = false) {
  els.feedback.textContent = message;
  els.feedback.style.color = isError ? "#d7263d" : "#4f6580";
}

function show(el) {
  el.classList.remove("hidden");
}

function hide(el) {
  el.classList.add("hidden");
}

function setButtonBusy(button, isBusy, idleText, busyText) {
  if (!button) return;
  button.disabled = isBusy;
  button.textContent = isBusy ? busyText : idleText;
}

function statusBadge(status) {
  const labels = {
    in_stock: "In Stock",
    low_stock: "Low Stock",
    ordered: "Ordered",
    discontinued: "Discontinued",
  };
  return `<span class="status-badge status-${status}">${labels[status] || status}</span>`;
}

function canEdit() {
  return state.user && (state.user.role === "admin" || state.user.role === "manager");
}

function canAdmin() {
  return state.user && state.user.role === "admin";
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.apiKey) {
    headers["X-API-Key"] = state.apiKey;
  }

  const response = await fetch(path, { ...options, headers });
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = payload?.detail;
    if (typeof detail === "string") {
      throw new Error(detail);
    }
    if (Array.isArray(detail)) {
      throw new Error(detail.map((entry) => entry.msg || "Validation error").join("; "));
    }
    throw new Error(`Request failed with status ${response.status}`);
  }

  return payload;
}

function switchView(viewId) {
  state.currentView = viewId;
  for (const view of allViews) {
    if (view.id === viewId) {
      show(view);
    } else {
      hide(view);
    }
  }

  for (const button of els.nav.querySelectorAll(".nav-item")) {
    button.classList.toggle("active", button.dataset.target === viewId);
  }

  const heading = titles[viewId];
  if (heading) {
    els.viewTitle.textContent = heading.title;
    els.viewSubtitle.textContent = heading.subtitle;
  }
}

function openItemModal(item = null) {
  if (!canEdit()) {
    setFeedback("Your role is read-only and cannot create or edit items.", true);
    return;
  }

  state.editingItemId = item?.id ?? null;
  els.itemFormError.textContent = "";
  hide(els.itemFormError);

  if (item) {
    els.itemFormTitle.textContent = "Edit Item";
    els.itemId.value = String(item.id);
    els.itemSku.value = item.sku;
    els.itemName.value = item.name;
    els.itemCategory.value = item.category;
    els.itemQuantity.value = String(item.quantity);
    els.itemThreshold.value = String(item.reorder_threshold);
    els.itemUnitCost.value = String(item.unit_cost);
    els.itemStatus.value = item.status;
    els.itemDetails.value = item.details || "";
  } else {
    els.itemFormTitle.textContent = "Create Item";
    els.itemForm.reset();
    els.itemId.value = "";
    els.itemStatus.value = "";
  }

  els.itemModal.showModal();
}

function closeItemModal() {
  els.itemModal.close();
}

function parseSortValue() {
  const [sortBy, sortDir] = String(els.inventorySort.value || "updated_at:desc").split(":");
  return { sortBy, sortDir };
}

function updateRoleUI() {
  if (!state.user) {
    els.roleBadge.textContent = "Guest";
    els.roleBadge.className = "role-badge";
    hide(els.logoutBtn);
    hide(els.nav);
    hide(els.bulkBar);
    hide(els.newItemBtn);
    return;
  }

  els.roleBadge.textContent = state.user.role;
  els.roleBadge.className = "role-badge";
  show(els.logoutBtn);
  show(els.nav);

  const editable = canEdit();
  if (editable) {
    show(els.bulkBar);
    show(els.newItemBtn);
    show(els.emptyCreateBtn);
  } else {
    hide(els.bulkBar);
    hide(els.newItemBtn);
    hide(els.emptyCreateBtn);
  }
}

async function login(username, password) {
  const data = await api("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });

  state.apiKey = data.api_key;
  state.user = data.user;
  localStorage.setItem("ims_api_key", state.apiKey);
  updateRoleUI();
}

async function restoreSession() {
  if (!state.apiKey) {
    return false;
  }

  try {
    const me = await api("/api/me");
    state.user = me;
    updateRoleUI();
    return true;
  } catch {
    state.apiKey = "";
    state.user = null;
    localStorage.removeItem("ims_api_key");
    updateRoleUI();
    return false;
  }
}

function logout() {
  state.apiKey = "";
  state.user = null;
  state.items = [];
  state.selectedItemIds.clear();
  localStorage.removeItem("ims_api_key");
  updateRoleUI();
  switchView("login-view");
  setFeedback("Logged out.");
}

async function loadDashboard() {
  show(els.dashboardLoading);
  hide(els.dashboardError);

  try {
    const data = await api("/api/dashboard");
    els.kpiTotalItems.textContent = String(data.total_items);
    els.kpiActiveItems.textContent = String(data.active_items);
    els.kpiTotalQty.textContent = String(data.total_quantity);
    els.kpiLowStock.textContent = String(data.low_stock_alerts);

    els.categoryTableBody.innerHTML = "";
    if (data.items_by_category.length === 0) {
      els.categoryTableBody.innerHTML = '<tr><td colspan="2">No category data yet.</td></tr>';
    } else {
      for (const row of data.items_by_category) {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${row.category}</td><td>${row.count}</td>`;
        els.categoryTableBody.appendChild(tr);
      }
    }

    els.activityList.innerHTML = "";
    if (data.recent_activity.length === 0) {
      els.activityList.innerHTML = "<li>No activity yet. Create an item to start logging events.</li>";
    } else {
      for (const log of data.recent_activity) {
        const li = document.createElement("li");
        li.innerHTML = `<strong>${log.action}</strong><br/><span class="muted">${log.entity_type} #${log.entity_id ?? "-"} • ${new Date(log.created_at).toLocaleString()}</span>`;
        els.activityList.appendChild(li);
      }
    }
  } catch (error) {
    els.dashboardError.textContent = `${error.message}. Retry by refreshing the page.`;
    show(els.dashboardError);
  } finally {
    hide(els.dashboardLoading);
  }
}

function currentInventoryQuery() {
  const params = new URLSearchParams();
  if (els.inventorySearch.value.trim()) params.set("q", els.inventorySearch.value.trim());
  if (els.inventoryCategoryFilter.value) params.set("category", els.inventoryCategoryFilter.value);
  if (els.inventoryStatusFilter.value) params.set("status", els.inventoryStatusFilter.value);
  const { sortBy, sortDir } = parseSortValue();
  params.set("sort_by", sortBy);
  params.set("sort_dir", sortDir);
  params.set("page", "1");
  params.set("page_size", "200");
  return params.toString();
}

async function loadInventory() {
  show(els.inventoryLoading);
  hide(els.inventoryError);
  hide(els.inventoryEmpty);

  try {
    const query = currentInventoryQuery();
    const data = await api(`/api/items?${query}`);
    state.items = data.items;
    state.selectedItemIds.clear();

    const categorySet = new Set(state.items.map((item) => item.category));
    const currentCategory = els.inventoryCategoryFilter.value;
    els.inventoryCategoryFilter.innerHTML = '<option value="">All Categories</option>';
    [...categorySet]
      .sort((a, b) => a.localeCompare(b))
      .forEach((category) => {
        const option = document.createElement("option");
        option.value = category;
        option.textContent = category;
        els.inventoryCategoryFilter.appendChild(option);
      });
    if (currentCategory) {
      els.inventoryCategoryFilter.value = currentCategory;
    }

    renderInventoryTable();

    if (state.items.length === 0) {
      show(els.inventoryEmpty);
    }
  } catch (error) {
    els.inventoryError.textContent = `${error.message}. Try clicking Refresh.`;
    show(els.inventoryError);
  } finally {
    hide(els.inventoryLoading);
  }
}

function renderInventoryTable() {
  const editable = canEdit();
  els.inventoryTableBody.innerHTML = "";

  for (const item of state.items) {
    const selected = state.selectedItemIds.has(item.id) ? "checked" : "";
    const disableSelect = editable ? "" : "disabled";

    const tr = document.createElement("tr");
    tr.dataset.itemId = String(item.id);
    tr.innerHTML = `
      <td><input type="checkbox" class="item-select" data-id="${item.id}" ${selected} ${disableSelect}/></td>
      <td>${item.sku}</td>
      <td>${item.name}</td>
      <td>${item.category}</td>
      <td>${item.quantity}</td>
      <td>${item.reorder_threshold}</td>
      <td>${statusBadge(item.status)}</td>
      <td>$${Number(item.unit_cost).toFixed(2)}</td>
      <td>
        <div class="action-btns">
          ${editable ? `<button class="secondary edit-item-btn" data-id="${item.id}">Edit</button>` : ""}
          ${editable ? `<button class="secondary quick-low-btn" data-id="${item.id}">Mark Low</button>` : ""}
          ${editable ? `<button class="secondary delete-item-btn" data-id="${item.id}">Delete</button>` : ""}
          ${!editable ? `<span class="muted">Read only</span>` : ""}
        </div>
      </td>
    `;
    els.inventoryTableBody.appendChild(tr);
  }

  updateBulkSelectionState();
}

function updateBulkSelectionState() {
  els.bulkSelectedCount.textContent = `${state.selectedItemIds.size} selected`;
  els.selectAllItems.checked = state.items.length > 0 && state.selectedItemIds.size === state.items.length;
}

function findItemById(itemId) {
  return state.items.find((item) => item.id === itemId) || null;
}

function validateItemForm() {
  const sku = els.itemSku.value.trim();
  const name = els.itemName.value.trim();
  const category = els.itemCategory.value.trim();
  const quantity = Number(els.itemQuantity.value);
  const threshold = Number(els.itemThreshold.value);
  const unitCost = Number(els.itemUnitCost.value);

  if (!sku) return "SKU is required";
  if (!name) return "Name is required";
  if (!category) return "Category is required";
  if (!Number.isFinite(quantity) || quantity < 0) return "Quantity must be a non-negative number";
  if (!Number.isFinite(threshold) || threshold < 0) return "Reorder threshold must be non-negative";
  if (!Number.isFinite(unitCost) || unitCost < 0) return "Unit cost must be non-negative";
  return null;
}

function buildItemPayload() {
  return {
    sku: els.itemSku.value.trim(),
    name: els.itemName.value.trim(),
    category: els.itemCategory.value.trim(),
    details: els.itemDetails.value.trim() || null,
    quantity: Number(els.itemQuantity.value),
    reorder_threshold: Number(els.itemThreshold.value),
    unit_cost: Number(els.itemUnitCost.value),
    status: els.itemStatus.value || null,
  };
}

async function submitItemForm() {
  const validationError = validateItemForm();
  if (validationError) {
    els.itemFormError.textContent = validationError;
    show(els.itemFormError);
    return;
  }

  hide(els.itemFormError);
  setButtonBusy(els.itemFormSave, true, "Save Item", "Saving...");

  const payload = buildItemPayload();
  const isEdit = Boolean(state.editingItemId);
  const path = isEdit ? `/api/items/${state.editingItemId}` : "/api/items";
  const method = isEdit ? "PUT" : "POST";
  setFeedback(isEdit ? "Updating item..." : "Creating item...");

  try {
    await api(path, {
      method,
      body: JSON.stringify(payload),
    });
    closeItemModal();
    setFeedback(isEdit ? "Item updated successfully." : "Item created successfully.");
    await Promise.all([loadInventory(), loadDashboard()]);
  } catch (error) {
    els.itemFormError.textContent = error.message;
    show(els.itemFormError);
  } finally {
    setButtonBusy(els.itemFormSave, false, "Save Item", "Saving...");
  }
}

async function deleteItem(itemId, triggerButton = null) {
  if (!confirm("Delete this item? The action is reversible only by updating status manually.")) {
    return;
  }

  try {
    setButtonBusy(triggerButton, true, "Delete", "Deleting...");
    setFeedback("Deleting item...");
    await api(`/api/items/${itemId}`, { method: "DELETE" });
    setFeedback("Item deleted.");
    await Promise.all([loadInventory(), loadDashboard()]);
  } catch (error) {
    setFeedback(error.message, true);
  } finally {
    setButtonBusy(triggerButton, false, "Delete", "Deleting...");
  }
}

async function updateSingleStatus(itemId, statusValue, note = null, triggerButton = null) {
  try {
    setButtonBusy(triggerButton, true, "Mark Low", "Updating...");
    setFeedback("Updating item status...");
    await api(`/api/items/${itemId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: statusValue, note }),
    });
    setFeedback("Item status updated.");
    await Promise.all([loadInventory(), loadDashboard()]);
  } catch (error) {
    setFeedback(error.message, true);
  } finally {
    setButtonBusy(triggerButton, false, "Mark Low", "Updating...");
  }
}

async function applyBulkStatus() {
  const statusValue = els.bulkStatusSelect.value;
  if (!statusValue) {
    setFeedback("Select a status for bulk update.", true);
    return;
  }
  if (state.selectedItemIds.size === 0) {
    setFeedback("Select at least one item for bulk update.", true);
    return;
  }

  setButtonBusy(els.bulkApplyBtn, true, "Apply", "Applying...");
  try {
    setFeedback("Applying bulk status update...");
    await api("/api/items/status/bulk", {
      method: "PATCH",
      body: JSON.stringify({
        item_ids: [...state.selectedItemIds],
        status: statusValue,
        note: "Bulk update from UI",
      }),
    });
    setFeedback("Bulk status update completed.");
    els.bulkStatusSelect.value = "";
    await Promise.all([loadInventory(), loadDashboard()]);
  } catch (error) {
    setFeedback(error.message, true);
  } finally {
    setButtonBusy(els.bulkApplyBtn, false, "Apply", "Applying...");
  }
}

function renderSearchResults(items) {
  els.searchResultsBody.innerHTML = "";
  if (items.length === 0) {
    show(els.searchEmpty);
    return;
  }

  hide(els.searchEmpty);
  for (const item of items) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${item.sku}</td>
      <td>${item.name}</td>
      <td>${item.category}</td>
      <td>${item.quantity}</td>
      <td>${statusBadge(item.status)}</td>
    `;
    els.searchResultsBody.appendChild(tr);
  }
}

async function runNaturalLanguageSearch() {
  show(els.searchLoading);
  hide(els.searchError);
  setButtonBusy(els.nlSearchSubmitBtn, true, "Run AI Search", "Searching...");
  setFeedback("Running AI search...");

  try {
    const response = await api("/api/ai/natural-language-search", {
      method: "POST",
      body: JSON.stringify({ query: els.nlQuery.value.trim() }),
    });

    els.nlSearchMeta.textContent = `Source: ${response.source}${response.model ? ` (${response.model})` : ""} | Filters: ${JSON.stringify(response.parsed_filters)}`;
    renderSearchResults(response.items);
    setFeedback("AI search completed.");
  } catch (error) {
    els.searchError.textContent = `${error.message}. Retry with a different query.`;
    show(els.searchError);
  } finally {
    setButtonBusy(els.nlSearchSubmitBtn, false, "Run AI Search", "Searching...");
    hide(els.searchLoading);
  }
}

async function runStandardSearch() {
  show(els.searchLoading);
  hide(els.searchError);
  setButtonBusy(els.stdSearchSubmitBtn, true, "Run Filter Search", "Searching...");
  setFeedback("Running standard search...");

  const params = new URLSearchParams();
  if (els.stdQuery.value.trim()) params.set("q", els.stdQuery.value.trim());
  if (els.stdCategory.value.trim()) params.set("category", els.stdCategory.value.trim());
  if (els.stdStatus.value) params.set("status", els.stdStatus.value);
  if (els.stdMinQty.value) params.set("min_qty", String(Number(els.stdMinQty.value)));
  if (els.stdMaxQty.value) params.set("max_qty", String(Number(els.stdMaxQty.value)));

  try {
    const response = await api(`/api/items/search?${params.toString()}`);
    els.nlSearchMeta.textContent = "Source: standard filters";
    renderSearchResults(response.items || []);
    setFeedback("Standard search completed.");
  } catch (error) {
    els.searchError.textContent = `${error.message}. Retry your filters.`;
    show(els.searchError);
  } finally {
    setButtonBusy(els.stdSearchSubmitBtn, false, "Run Filter Search", "Searching...");
    hide(els.searchLoading);
  }
}

async function loadAiPanels() {
  await Promise.all([loadReorderSuggestions(), loadAnomalyAlerts()]);
}

async function loadReorderSuggestions() {
  show(els.reorderLoading);
  hide(els.reorderError);
  setButtonBusy(els.refreshReorderBtn, true, "Refresh", "Refreshing...");

  try {
    const response = await api("/api/ai/reorder-suggestions?limit=25");
    els.reorderSource.textContent = `Source: ${response.source}${response.model ? ` (${response.model})` : ""}`;

    els.reorderBody.innerHTML = "";
    if (response.suggestions.length === 0) {
      els.reorderBody.innerHTML = '<tr><td colspan="6">No reorder actions needed right now.</td></tr>';
    } else {
      for (const suggestion of response.suggestions) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${suggestion.sku}</td>
          <td>${suggestion.name}</td>
          <td>${suggestion.current_quantity}</td>
          <td>${suggestion.reorder_threshold}</td>
          <td>${suggestion.recommended_order_qty}</td>
          <td>${suggestion.reason}</td>
        `;
        els.reorderBody.appendChild(tr);
      }
    }
  } catch (error) {
    els.reorderError.textContent = `${error.message}. Click refresh to retry.`;
    show(els.reorderError);
  } finally {
    setButtonBusy(els.refreshReorderBtn, false, "Refresh", "Refreshing...");
    hide(els.reorderLoading);
  }
}

async function loadAnomalyAlerts() {
  show(els.anomalyLoading);
  hide(els.anomalyError);
  setButtonBusy(els.refreshAnomalyBtn, true, "Refresh", "Refreshing...");

  try {
    const response = await api("/api/ai/anomaly-alerts?days=30&limit=20");
    els.anomalySource.textContent = `Source: ${response.source}${response.model ? ` (${response.model})` : ""}`;

    els.anomalyList.innerHTML = "";
    if (response.alerts.length === 0) {
      els.anomalyList.innerHTML = "<li>No anomalies detected in selected window.</li>";
    } else {
      for (const alert of response.alerts) {
        const li = document.createElement("li");
        li.innerHTML = `
          <strong>${alert.sku} • ${alert.severity.toUpperCase()}</strong><br/>
          <span class="muted">${new Date(alert.created_at).toLocaleString()} • Delta ${alert.quantity_delta}</span><br/>
          ${alert.explanation}<br/>
          <em>${alert.suggested_action}</em>
        `;
        els.anomalyList.appendChild(li);
      }
    }
  } catch (error) {
    els.anomalyError.textContent = `${error.message}. Click refresh to retry.`;
    show(els.anomalyError);
  } finally {
    setButtonBusy(els.refreshAnomalyBtn, false, "Refresh", "Refreshing...");
    hide(els.anomalyLoading);
  }
}

async function bootstrapApp() {
  const sessionOk = await restoreSession();
  if (!sessionOk) {
    switchView("login-view");
    setFeedback("Sign in with a demo account.");
    return;
  }

  switchView("dashboard-view");
  await Promise.all([loadDashboard(), loadInventory(), loadAiPanels()]);
  setFeedback(`Welcome ${state.user.full_name} (${state.user.role}).`);
}

els.nav.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLButtonElement)) return;
  const viewId = target.dataset.target;
  if (!viewId) return;
  switchView(viewId);
});

els.logoutBtn.addEventListener("click", () => logout());

els.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  hide(els.loginError);
  const formData = new FormData(els.loginForm);
  const username = String(formData.get("username") || "").trim();
  const password = String(formData.get("password") || "");

  if (!username || !password) {
    els.loginError.textContent = "Username and password are required.";
    show(els.loginError);
    return;
  }

  try {
    setButtonBusy(els.loginSubmitBtn, true, "Sign In", "Signing In...");
    setFeedback("Signing in...");
    await login(username, password);
    switchView("dashboard-view");
    await Promise.all([loadDashboard(), loadInventory(), loadAiPanels()]);
    setFeedback(`Authenticated as ${state.user.full_name} (${state.user.role}).`);
  } catch (error) {
    els.loginError.textContent = `${error.message}. Check credentials and retry.`;
    show(els.loginError);
  } finally {
    setButtonBusy(els.loginSubmitBtn, false, "Sign In", "Signing In...");
  }
});

els.inventoryRefresh.addEventListener("click", async () => {
  await loadInventory();
});

[els.inventorySearch, els.inventoryCategoryFilter, els.inventoryStatusFilter, els.inventorySort].forEach((control) => {
  control.addEventListener("change", async () => {
    await loadInventory();
  });
});
els.inventorySearch.addEventListener("input", async () => {
  await loadInventory();
});

els.newItemBtn.addEventListener("click", () => openItemModal());
els.emptyCreateBtn.addEventListener("click", () => openItemModal());
els.closeItemModal.addEventListener("click", () => closeItemModal());

els.itemForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitItemForm();
});

els.inventoryTableBody.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;

  const editButton = target.closest(".edit-item-btn");
  if (editButton instanceof HTMLButtonElement) {
    const itemId = Number(editButton.dataset.id);
    const item = findItemById(itemId);
    if (item) openItemModal(item);
    return;
  }

  const lowButton = target.closest(".quick-low-btn");
  if (lowButton instanceof HTMLButtonElement) {
    const itemId = Number(lowButton.dataset.id);
    await updateSingleStatus(itemId, "low_stock", "Quick status update from inventory table", lowButton);
    return;
  }

  const deleteButton = target.closest(".delete-item-btn");
  if (deleteButton instanceof HTMLButtonElement) {
    const itemId = Number(deleteButton.dataset.id);
    await deleteItem(itemId, deleteButton);
  }
});

els.inventoryTableBody.addEventListener("change", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement)) return;
  if (!target.classList.contains("item-select")) return;

  const itemId = Number(target.dataset.id);
  if (target.checked) {
    state.selectedItemIds.add(itemId);
  } else {
    state.selectedItemIds.delete(itemId);
  }
  updateBulkSelectionState();
});

els.selectAllItems.addEventListener("change", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement)) return;

  state.selectedItemIds.clear();
  if (target.checked) {
    for (const item of state.items) {
      state.selectedItemIds.add(item.id);
    }
  }

  renderInventoryTable();
});

els.bulkApplyBtn.addEventListener("click", async () => {
  await applyBulkStatus();
});

els.nlSearchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!els.nlQuery.value.trim()) {
    els.searchError.textContent = "Enter a natural language query.";
    show(els.searchError);
    return;
  }
  await runNaturalLanguageSearch();
});

els.standardSearchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await runStandardSearch();
});

els.resetSearchBtn.addEventListener("click", async () => {
  els.stdQuery.value = "";
  els.stdCategory.value = "";
  els.stdStatus.value = "";
  els.stdMinQty.value = "";
  els.stdMaxQty.value = "";
  els.nlSearchMeta.textContent = "Source: standard filters";
  await runStandardSearch();
});

els.refreshReorderBtn.addEventListener("click", async () => {
  await loadReorderSuggestions();
});

els.refreshAnomalyBtn.addEventListener("click", async () => {
  await loadAnomalyAlerts();
});

window.addEventListener("DOMContentLoaded", async () => {
  updateRoleUI();
  await bootstrapApp();
});
