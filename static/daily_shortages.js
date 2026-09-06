/* Ezz Pharmacy — Daily Shortages UI
 * Single source of truth for the shortages screen.
 * Customer shortages are loaded from the server-side pending-shortages endpoint,
 * while pharmacy shortages use /api/pharmacy-shortages.
 */
(() => {
  "use strict";

  const state = {
    pharmacyRows: [],
    customerRows: [],
    filter: "all",
    pageSize: localStorage.getItem("ezz_shortages_page_size") || "20",
    page: 1,
    editingId: null
  };

  const FILTERS = new Set(["all", "pharmacy", "pharmacy_available", "customer"]);
  const PAGE_SIZES = new Set(["20", "30", "all"]);

  const esc = window.esc || (value => String(value ?? "").replace(/[&<>\"]/g, ch => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;"
  }[ch])));

  const fmtDate = window.fmtDate || (value => {
    if (!value) return "—";
    const parts = String(value).split(" ")[0].split("-");
    return parts.length === 3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : String(value);
  });

  const api = window.apiFetch || (async (url, options = {}) => {
    const response = await fetch(url, {
      credentials: "same-origin",
      ...options
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "حدث خطأ أثناء الاتصال بالخادم");
    return data;
  });

  const notify = window.toast || ((message) => alert(message));

  function value(object, ...keys) {
    for (const key of keys) {
      if (object && object[key] !== undefined && object[key] !== null && object[key] !== "") {
        return object[key];
      }
    }
    return "";
  }

  function normalizeCustomerRows(rows) {
    return (rows || []).map(row => ({
      type: "customer",
      orderId: value(row, "order_id", "Order_ID") || "—",
      customer: value(row, "customer_name", "Customer_Name") || "—",
      phone: value(row, "phone", "Phone") || "—",
      product: value(row, "product_name", "Product_Name") || "—",
      quantity: Number(value(row, "quantity", "Quantity")) || 1,
      date: value(row, "order_date", "Order_Date", "created_at", "Created_At") || "",
      status: value(row, "status", "Status") || "بانتظار التوفير"
    }));
  }

  function normalizePharmacyRows(items) {
    return (items || []).map(item => ({
      type: "pharmacy",
      shortageId: value(item, "shortage_id", "id"),
      orderId: "—",
      customer: "—",
      phone: "—",
      product: value(item, "product_name", "Product_Name") || "—",
      quantity: Number(value(item, "quantity", "Quantity")) || 1,
      date: value(item, "created_at", "Created_At") || "",
      statusKey: String(value(item, "status", "Status") || "pending").toLowerCase() === "available" ? "available" : "pending",
      status: String(value(item, "status", "Status") || "pending").toLowerCase() === "available" ? "تم التوفير" : "بانتظار التوفير",
      note: value(item, "note", "Note") || "",
      createdBy: value(item, "created_by", "Created_By") || "موظف"
    }));
  }

  function rowsForFilter() {
    if (state.filter === "pharmacy") return state.pharmacyRows.filter(row => row.statusKey === "pending");
    if (state.filter === "pharmacy_available") return state.pharmacyRows.filter(row => row.statusKey === "available");
    if (state.filter === "customer") return state.customerRows;
    return [...state.customerRows, ...state.pharmacyRows].sort((a, b) =>
      String(b.date || "").localeCompare(String(a.date || ""))
    );
  }

  function pageCount() {
    const total = rowsForFilter().length;
    if (state.pageSize === "all") return 1;
    return Math.max(1, Math.ceil(total / Math.max(1, Number(state.pageSize) || 20)));
  }

  function pageRows() {
    const rows = rowsForFilter();
    if (state.pageSize === "all") return rows;
    const size = Math.max(1, Number(state.pageSize) || 20);
    return rows.slice((state.page - 1) * size, state.page * size);
  }

  function syncTabs() {
    document.querySelectorAll("[data-shortages-view]").forEach(button => {
      const active = button.dataset.shortagesView === state.filter;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
  }

  function updateCounts() {
    const pharmacy = document.getElementById("pharmacy-shortages-tab-count");
    const customer = document.getElementById("customer-shortages-tab-count");
    const all = document.getElementById("all-shortages-tab-count");
    const pendingPharmacy = state.pharmacyRows.filter(row => row.statusKey === "pending").length;
    const availablePharmacy = state.pharmacyRows.filter(row => row.statusKey === "available").length;
    if (pharmacy) pharmacy.textContent = pendingPharmacy;
    if (customer) customer.textContent = state.customerRows.length;
    if (all) all.textContent = pendingPharmacy + state.customerRows.length;
    const provided = document.getElementById("pharmacy-shortages-provided-count");
    if (provided) provided.textContent = availablePharmacy;
  }

  function updateHeaders() {
    const head = document.getElementById("daily-shortages-table-head");
    if (!head) return;

    const headers = (state.filter === "pharmacy" || state.filter === "pharmacy_available")
      ? ["المنتج", "الكمية", "التاريخ", "الحالة", "الإجراء"]
      : state.filter === "customer"
        ? ["رقم الطلب", "العميل", "الهاتف", "المنتج", "الكمية", "التاريخ", "الإجراء"]
        : ["النوع", "رقم الطلب", "العميل", "الهاتف", "المنتج", "الكمية", "التاريخ", "الحالة", "الإجراء"];

    head.innerHTML = `<tr>${headers.map(header => `<th>${header}</th>`).join("")}</tr>`;
  }

  function pharmacyAction(row) {
    const availability = row.status === "تم التوفير"
      ? `<button type="button" class="btn btn-secondary btn-sm ps-undo" data-id="${esc(row.shortageId)}">↩ تراجع</button>`
      : `<button type="button" class="btn btn-primary btn-sm ps-available" data-id="${esc(row.shortageId)}">تم توفيره</button>`;
    return `${availability}<button type="button" class="btn btn-outline btn-sm ps-edit" data-id="${esc(row.shortageId)}">تعديل</button>`;
  }

  function customerAction(row) {
    return `<button type="button" class="btn btn-outline btn-sm ps-detail" data-id="${esc(row.orderId)}">التفاصيل</button>`;
  }

  function renderRows() {
    const body = document.getElementById("daily-shortages-table-body");
    if (!body) return;

    const rows = pageRows();
    const colspan = (state.filter === "pharmacy" || state.filter === "pharmacy_available") ? 5 : state.filter === "customer" ? 7 : 9;

    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="${colspan}" class="empty-state">لا توجد نواقص ضمن هذا التصنيف ✅</td></tr>`;
      return;
    }

    body.innerHTML = rows.map(row => {
      const status = row.type === "pharmacy"
        ? `<span class="status-badge ${row.status === "تم التوفير" ? "status-picked" : "status-pending"}">${esc(row.status)}</span>`
        : `<span class="status-badge status-pending">بانتظار التوفير</span>`;
      const action = row.type === "pharmacy" ? pharmacyAction(row) : customerAction(row);

      if (state.filter === "pharmacy" || state.filter === "pharmacy_available") {
        return `<tr>
          <td><strong>${esc(row.product)}</strong>${row.note ? `<div class="daily-shortage-note">${esc(row.note)}</div>` : ""}</td>
          <td>${esc(row.quantity)}</td>
          <td>${fmtDate(row.date)}</td>
          <td>${status}</td>
          <td><div class="daily-shortage-actions">${action}</div></td>
        </tr>`;
      }

      if (state.filter === "customer") {
        return `<tr>
          <td><strong>${esc(row.orderId)}</strong></td>
          <td>${esc(row.customer)}</td>
          <td dir="ltr">${esc(row.phone)}</td>
          <td><strong>${esc(row.product)}</strong></td>
          <td>${esc(row.quantity)}</td>
          <td>${fmtDate(row.date)}</td>
          <td><div class="daily-shortage-actions">${action}</div></td>
        </tr>`;
      }

      return `<tr>
        <td><span class="shortage-type ${row.type === "pharmacy" ? "shortage-type-pharmacy" : "shortage-type-customer"}">${row.type === "pharmacy" ? "الصيدلية" : "طلب عميل"}</span></td>
        <td><strong>${esc(row.orderId)}</strong></td>
        <td>${esc(row.customer)}</td>
        <td dir="ltr">${esc(row.phone)}</td>
        <td><strong>${esc(row.product)}</strong></td>
        <td>${esc(row.quantity)}</td>
        <td>${fmtDate(row.date)}</td>
        <td>${status}</td>
        <td><div class="daily-shortage-actions">${action}</div></td>
      </tr>`;
    }).join("");

    bindRowActions(body);
  }

  function renderPagination() {
    const host = document.getElementById("daily-shortages-pagination");
    if (!host) return;

    const total = rowsForFilter().length;
    const pages = pageCount();
    if (state.pageSize === "all" || pages <= 1 || total === 0) {
      host.innerHTML = "";
      return;
    }

    let start = Math.max(1, state.page - 2);
    let end = Math.min(pages, start + 4);
    if (end - start < 4) start = Math.max(1, end - 4);

    const buttons = [];
    buttons.push(`<button type="button" class="shortage-page-btn" data-page="${Math.max(1, state.page - 1)}" ${state.page === 1 ? "disabled" : ""}>السابق</button>`);
    if (start > 1) {
      buttons.push(`<button type="button" class="shortage-page-btn" data-page="1">1</button>`);
      if (start > 2) buttons.push(`<span class="shortage-page-ellipsis">…</span>`);
    }
    for (let page = start; page <= end; page += 1) {
      buttons.push(`<button type="button" class="shortage-page-btn ${page === state.page ? "active" : ""}" data-page="${page}" ${page === state.page ? "aria-current=\"page\"" : ""}>${page}</button>`);
    }
    if (end < pages) {
      if (end < pages - 1) buttons.push(`<span class="shortage-page-ellipsis">…</span>`);
      buttons.push(`<button type="button" class="shortage-page-btn" data-page="${pages}">${pages}</button>`);
    }
    buttons.push(`<button type="button" class="shortage-page-btn" data-page="${Math.min(pages, state.page + 1)}" ${state.page === pages ? "disabled" : ""}>التالي</button>`);

    host.innerHTML = `<div class="shortages-pagination-info">صفحة ${state.page} من ${pages} — ${total} نتيجة</div><div class="shortages-pagination-buttons">${buttons.join("")}</div>`;
    host.querySelectorAll("[data-page]").forEach(button => {
      button.addEventListener("click", () => {
        if (button.disabled) return;
        state.page = Number(button.dataset.page) || 1;
        render();
      });
    });
  }

  function render() {
    const title = document.getElementById("daily-shortages-title");
    const subtitle = document.getElementById("daily-shortages-subtitle");
    const summary = document.getElementById("daily-shortages-summary");
    const limit = document.getElementById("pharmacy-shortages-limit");
    const labels = { all: "الكل", pharmacy: "النواقص الحالية", pharmacy_available: "تم توفيره", customer: "طلبات العملاء" };

    if (state.page > pageCount()) state.page = pageCount();
    updateCounts();
    syncTabs();
    updateHeaders();

    if (title) title.textContent = state.filter === "all" ? "النواقص" : `📦 ${labels[state.filter]}`;
    if (subtitle) subtitle.textContent = state.filter === "all"
      ? "عرض موحد للنواقص الحالية وطلبات العملاء."
      : state.filter === "pharmacy"
        ? "النواقص التي لم يتم توفيرها بعد."
        : state.filter === "pharmacy_available"
          ? "المنتجات التي تم توفيرها مسبقًا."
          : "المنتجات غير المتوفرة المرتبطة بطلبات العملاء.";

    if (limit) limit.value = PAGE_SIZES.has(state.pageSize) ? state.pageSize : "20";

    const total = rowsForFilter().length;
    const shown = pageRows().length;
    if (summary) summary.textContent = state.pageSize === "all"
      ? `عرض جميع النتائج: ${total}`
      : `عرض ${shown} من أصل ${total} — الصفحة ${state.page} من ${pageCount()}`;

    renderRows();
    renderPagination();
  }

  function bindRowActions(body) {
    body.querySelectorAll(".ps-detail").forEach(button => {
      button.addEventListener("click", () => window.details?.(button.dataset.id));
    });
    body.querySelectorAll(".ps-available").forEach(button => {
      button.addEventListener("click", () => setAvailable(button.dataset.id));
    });
    body.querySelectorAll(".ps-undo").forEach(button => {
      button.addEventListener("click", () => undo(button.dataset.id));
    });
    body.querySelectorAll(".ps-edit").forEach(button => {
      button.addEventListener("click", () => {
        const row = state.pharmacyRows.find(item => String(item.shortageId) === String(button.dataset.id));
        if (row) openForm(row);
      });
    });
  }

  async function load() {
    try {
      const [pharmacyData, customerData] = await Promise.all([
        api("/api/pharmacy-shortages"),
        api("/api/customer-shortages")
      ]);

      state.pharmacyRows = normalizePharmacyRows(pharmacyData.shortages || []);
      state.customerRows = normalizeCustomerRows(customerData.shortages || []);
      state.page = Math.min(state.page, pageCount());
      render();
    } catch (error) {
      notify(error.message, "error");
    }
  }

  async function sendShortages(kind) {
    if (!FILTERS.has(kind) || kind === "all" && !confirm("هل تريد تجهيز رسالة تشمل نواقص الصيدلية وطلبات العملاء معًا؟")) return;

    try {
      const result = await api(`/api/pharmacy-shortages/whatsapp?kind=${encodeURIComponent(kind)}`);
      const message = result.message || "";

      try { await navigator.clipboard.writeText(message); } catch (_) {}

      if (window.openWhatsAppOnThisDevice) {
        window.openWhatsAppOnThisDevice(
          `whatsapp://send?text=${encodeURIComponent(message)}`,
          "https://web.whatsapp.com/"
        );
      } else {
        window.open(`https://web.whatsapp.com/send?text=${encodeURIComponent(message)}`, "_blank", "noopener");
      }

      notify(`تم تجهيز رسالة ${kind === "pharmacy" ? "نواقص الصيدلية" : kind === "customer" ? "طلبات العملاء" : "كل النواقص"} ونسخها.`);
    } catch (error) {
      notify(error.message, "error");
    }
  }

  async function setAvailable(id) {
    try {
      await api(`/api/pharmacy-shortages/${encodeURIComponent(id)}/available`, { method: "POST", body: "{}" });
      notify("تم تسجيل توفر المنتج");
      await load();
    } catch (error) { notify(error.message, "error"); }
  }

  async function undo(id) {
    try {
      const result = await api(`/api/pharmacy-shortages/${encodeURIComponent(id)}/undo`, { method: "POST", body: "{}" });
      notify(`تم التراجع عن: ${result.undone_action || "آخر إجراء"}`);
      await load();
    } catch (error) { notify(error.message, "error"); }
  }

  function openForm(row = null) {
    const modal = document.getElementById("pharmacy-shortage-modal");
    const form = document.getElementById("pharmacy-shortage-form");
    if (!modal || !form) return;

    state.editingId = row?.shortageId || null;
    form.reset();
    if (form.product_name) form.product_name.value = row?.product || "";
    if (form.quantity) form.quantity.value = row?.quantity || 1;
    if (form.note) form.note.value = row?.note || "";
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
    setTimeout(() => form.product_name?.focus(), 0);
  }

  function closeForm() {
    const modal = document.getElementById("pharmacy-shortage-modal");
    const form = document.getElementById("pharmacy-shortage-form");
    modal?.classList.add("hidden");
    modal?.setAttribute("aria-hidden", "true");
    form?.reset();
    state.editingId = null;
  }

  async function saveForm(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const product = form.product_name?.value.trim();
    const quantity = Number(form.quantity?.value);
    const note = form.note?.value.trim() || "";

    if (!product || !Number.isInteger(quantity) || quantity < 1) {
      notify("اسم المنتج مطلوب والكمية يجب أن تكون رقمًا صحيحًا أكبر من صفر", "error");
      return;
    }

    const submit = form.querySelector('button[type="submit"]');
    if (submit) submit.disabled = true;

    try {
      const url = state.editingId
        ? `/api/pharmacy-shortages/${encodeURIComponent(state.editingId)}`
        : "/api/pharmacy-shortages";
      await api(url, {
        method: state.editingId ? "PUT" : "POST",
        body: JSON.stringify({ product_name: product, quantity, note })
      });
      notify(state.editingId ? "تم تعديل نقص الصيدلية" : "تمت إضافة نقص الصيدلية");
      closeForm();
      state.filter = "pharmacy";
      state.page = 1;
      await load();
    } catch (error) {
      notify(error.message, "error");
    } finally {
      if (submit) submit.disabled = false;
    }
  }

  function bindPage() {
    document.querySelectorAll("[data-shortages-view]").forEach(button => {
      button.addEventListener("click", () => {
        state.filter = FILTERS.has(button.dataset.shortagesView) ? button.dataset.shortagesView : "all";
        state.page = 1;
        render();
      });
    });

    document.getElementById("pharmacy-shortages-limit")?.addEventListener("change", event => {
      state.pageSize = PAGE_SIZES.has(event.target.value) ? event.target.value : "20";
      state.page = 1;
      localStorage.setItem("ezz_shortages_page_size", state.pageSize);
      render();
    });

    document.querySelectorAll("[data-send-shortages]").forEach(button => {
      button.addEventListener("click", () => sendShortages(button.dataset.sendShortages));
    });

    document.getElementById("refresh-daily-shortages-btn")?.addEventListener("click", load);
    document.getElementById("add-pharmacy-shortage-btn")?.addEventListener("click", () => openForm());
    document.getElementById("pharmacy-shortage-close-btn")?.addEventListener("click", closeForm);
    document.getElementById("pharmacy-shortage-cancel-btn")?.addEventListener("click", closeForm);
    document.getElementById("pharmacy-shortage-form")?.addEventListener("submit", saveForm);
    document.getElementById("pharmacy-shortage-modal")?.addEventListener("click", event => {
      if (event.target.id === "pharmacy-shortage-modal") closeForm();
    });

    state.filter = "pharmacy";
    state.page = 1;
    render();
    load();
  }

  window.dailyShortages = {
    load,
    open: () => {
      state.filter = "pharmacy";
      state.page = 1;
      render();
      return load();
    },
    switchFilter: filter => {
      state.filter = FILTERS.has(filter) ? filter : "all";
      state.page = 1;
      render();
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindPage, { once: true });
  } else {
    bindPage();
  }
})();
