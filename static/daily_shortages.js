/* Ezz Pharmacy — Daily shortages module */
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

  const escLocal = window.esc || (s => String(s ?? "").replace(/[&<>"]/g, c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"
  }[c])));
  const dateLocal = window.fmtDate || (s => s ? String(s).split(" ")[0].split("-").reverse().join("/") : "—");
  const callApi = window.apiFetch || (async (url, options={}) => {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "حدث خطأ");
    return data;
  });
  const notify = window.toast || ((message) => alert(message));

  function normalizeCustomerRows(orders) {
    const rows = [];
    (orders || []).forEach(order => {
      const pending = (order.Items || []).filter(
        item => item.Availability_Status === "بانتظار التوفير"
      );
      if (pending.length) {
        pending.forEach(item => rows.push({
          type: "customer",
          orderId: order.Order_ID || "—",
          customer: order.Customer_Name || "—",
          phone: order.Phone || "—",
          product: item.Product_Name || "—",
          quantity: item.Quantity || 1,
          date: order.Order_Date || order.Created_At || "",
          status: "بانتظار التوفير"
        }));
      } else if (order.Status === "بانتظار التوفير") {
        rows.push({
          type: "customer",
          orderId: order.Order_ID || "—",
          customer: order.Customer_Name || "—",
          phone: order.Phone || "—",
          product: order.Product_Name || "—",
          quantity: order.Quantity || 1,
          date: order.Order_Date || order.Created_At || "",
          status: "بانتظار التوفير"
        });
      }
    });
    return rows;
  }

  function normalizePharmacyRows(items) {
    return (items || []).map(item => ({
      type: "pharmacy",
      shortageId: item.shortage_id,
      orderId: "—",
      customer: "—",
      phone: "—",
      product: item.product_name || "—",
      quantity: item.quantity || 1,
      date: item.created_at || "",
      status: item.status === "available" ? "تم التوفير" : "بانتظار التوفير",
      note: item.note || "",
      createdBy: item.created_by || "موظف"
    }));
  }

  function allRows() {
    if (state.filter === "pharmacy") return state.pharmacyRows;
    if (state.filter === "customer") return state.customerRows;
    return [...state.customerRows, ...state.pharmacyRows].sort(
      (a, b) => String(b.date || "").localeCompare(String(a.date || ""))
    );
  }

  function pageCount() {
    if (state.pageSize === "all") return 1;
    const size = Math.max(1, Number(state.pageSize) || 20);
    return Math.max(1, Math.ceil(allRows().length / size));
  }

  function pageRows() {
    const rows = allRows();
    if (state.pageSize === "all") return rows;
    const size = Math.max(1, Number(state.pageSize) || 20);
    const start = (state.page - 1) * size;
    return rows.slice(start, start + size);
  }

  function syncFilterButtons() {
    document.querySelectorAll("[data-shortages-view]").forEach(button => {
      const active = button.dataset.shortagesView === state.filter;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
  }

  function updateHeaders() {
    const head = document.getElementById("daily-shortages-table-head");
    if (!head) return;

    const headers =
      state.filter === "pharmacy"
        ? ["المنتج", "الكمية", "التاريخ", "الحالة", "الإجراء"]
        : state.filter === "customer"
          ? ["رقم الطلب", "العميل", "الهاتف", "المنتج", "الكمية", "التاريخ", "الإجراء"]
          : ["النوع", "رقم الطلب", "العميل", "الهاتف", "المنتج", "الكمية", "التاريخ", "الحالة", "الإجراء"];

    head.innerHTML =
      "<tr>" + headers.map(label => "<th>" + label + "</th>").join("") + "</tr>";
  }

  function renderPagination() {
    const host = document.getElementById("daily-shortages-pagination");
    if (!host) return;

    const total = allRows().length;
    const pages = pageCount();

    if (state.pageSize === "all" || pages <= 1 || total === 0) {
      host.innerHTML = "";
      return;
    }

    let start = Math.max(1, state.page - 2);
    let end = Math.min(pages, start + 4);
    if (end - start < 4) start = Math.max(1, end - 4);

    const html = [];
    html.push(
      '<button type="button" class="shortage-page-btn" data-page="' +
      Math.max(1, state.page - 1) + '"' +
      (state.page === 1 ? " disabled" : "") + '>السابق</button>'
    );

    if (start > 1) {
      html.push('<button type="button" class="shortage-page-btn" data-page="1">1</button>');
      if (start > 2) html.push('<span class="shortage-page-ellipsis">…</span>');
    }

    for (let p = start; p <= end; p += 1) {
      html.push(
        '<button type="button" class="shortage-page-btn ' +
        (p === state.page ? "active" : "") +
        '" data-page="' + p + '"' +
        (p === state.page ? ' aria-current="page"' : "") + ">" + p + "</button>"
      );
    }

    if (end < pages) {
      if (end < pages - 1) html.push('<span class="shortage-page-ellipsis">…</span>');
      html.push('<button type="button" class="shortage-page-btn" data-page="' + pages + '">' + pages + "</button>");
    }

    html.push(
      '<button type="button" class="shortage-page-btn" data-page="' +
      Math.min(pages, state.page + 1) + '"' +
      (state.page === pages ? " disabled" : "") + '>التالي</button>'
    );

    host.innerHTML =
      '<div class="shortages-pagination-info">صفحة ' + state.page + ' من ' + pages + ' — ' + total + ' نتيجة</div>' +
      '<div class="shortages-pagination-buttons">' + html.join("") + "</div>";

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
    const head = document.getElementById("daily-shortages-table-head");
    const body = document.getElementById("daily-shortages-table-body");
    const limitSelect = document.getElementById("pharmacy-shortages-limit");

    if (!body) return;

    const labels = {
      all: "الكل",
      pharmacy: "نواقص الصيدلية",
      customer: "طلبات العملاء"
    };

    const total = allRows().length;
    const pages = pageCount();

    if (state.page > pages) state.page = pages;

    const rows = pageRows();

    title.textContent =
      state.filter === "all" ? "النواقص" : "📦 " + labels[state.filter];

    subtitle.textContent =
      state.filter === "all"
        ? "عرض موحد لنواقص الصيدلية وطلبات العملاء."
        : state.filter === "pharmacy"
          ? "النواقص المسجلة على مستوى الصيدلية."
          : "المنتجات غير المتوفرة المرتبطة بطلبات العملاء.";

    if (limitSelect) {
      limitSelect.value = ["20", "30", "all"].includes(state.pageSize)
        ? state.pageSize
        : "20";
    }

    updateHeaders();
    syncFilterButtons();

    summary.textContent =
      state.pageSize === "all"
        ? "عرض جميع النتائج: " + total
        : "عرض " + rows.length + " من أصل " + total +
          " — الصفحة " + state.page + " من " + pages;

    if (!rows.length) {
      const colspan = state.filter === "pharmacy" ? 5 :
        state.filter === "customer" ? 7 : 9;
      body.innerHTML =
        '<tr><td colspan="' + colspan +
        '" class="empty-state">لا توجد نواقص ضمن هذا التصنيف ✅</td></tr>';
      renderPagination();
      return;
    }

    body.innerHTML = rows.map(row => {
      const type = row.type === "pharmacy"
        ? '<span class="shortage-type shortage-type-pharmacy">الصيدلية</span>'
        : '<span class="shortage-type shortage-type-customer">طلب عميل</span>';

      const status = row.type === "pharmacy"
        ? '<span class="status-badge ' +
          (row.status === "تم التوفير" ? "status-picked" : "status-pending") +
          '">' + escLocal(row.status) + "</span>"
        : '<span class="status-badge status-pending">بانتظار التوفير</span>';

      let action;
      if (row.type === "pharmacy") {
        action =
          (row.status === "تم التوفير"
            ? '<button type="button" class="btn btn-secondary btn-sm ps-undo" data-id="' + escLocal(row.shortageId) + '">↩ تراجع</button>'
            : '<button type="button" class="btn btn-primary btn-sm ps-available" data-id="' + escLocal(row.shortageId) + '">تم التوفير</button>') +
          '<button type="button" class="btn btn-outline btn-sm ps-edit" data-id="' + escLocal(row.shortageId) + '">تعديل</button>';
      } else {
        action =
          '<button type="button" class="btn btn-outline btn-sm ps-detail" data-id="' +
          escLocal(row.orderId) + '">التفاصيل</button>';
      }

      if (state.filter === "pharmacy") {
        return "<tr>" +
          "<td><strong>" + escLocal(row.product) + "</strong>" +
          (row.note ? '<div class="daily-shortage-note">' + escLocal(row.note) + "</div>" : "") +
          "</td><td>" + escLocal(row.quantity) + "</td>" +
          "<td>" + dateLocal(row.date) + "</td><td>" + status + "</td>" +
          '<td><div class="daily-shortage-actions">' + action + "</div></td></tr>";
      }

      if (state.filter === "customer") {
        return "<tr>" +
          "<td><strong>" + escLocal(row.orderId) + "</strong></td>" +
          "<td>" + escLocal(row.customer) + "</td>" +
          '<td dir="ltr">' + escLocal(row.phone) + "</td>" +
          "<td><strong>" + escLocal(row.product) + "</strong></td>" +
          "<td>" + escLocal(row.quantity) + "</td>" +
          "<td>" + dateLocal(row.date) + "</td>" +
          '<td><div class="daily-shortage-actions">' + action + "</div></td></tr>";
      }

      return "<tr>" +
        "<td>" + type + "</td>" +
        "<td><strong>" + escLocal(row.orderId) + "</strong></td>" +
        "<td>" + escLocal(row.customer) + "</td>" +
        '<td dir="ltr">' + escLocal(row.phone) + "</td>" +
        "<td><strong>" + escLocal(row.product) + "</strong></td>" +
        "<td>" + escLocal(row.quantity) + "</td>" +
        "<td>" + dateLocal(row.date) + "</td>" +
        "<td>" + status + "</td>" +
        '<td><div class="daily-shortage-actions">' + action + "</div></td></tr>";
    }).join("");

    body.querySelectorAll(".ps-detail").forEach(button => {
      button.onclick = () => window.details?.(button.dataset.id);
    });
    body.querySelectorAll(".ps-available").forEach(button => {
      button.onclick = () => setAvailable(button.dataset.id);
    });
    body.querySelectorAll(".ps-undo").forEach(button => {
      button.onclick = () => undo(button.dataset.id);
    });
    body.querySelectorAll(".ps-edit").forEach(button => {
      button.onclick = () => {
        const row = state.pharmacyRows.find(item => item.shortageId === button.dataset.id);
        if (row) openForm(row);
      };
    });

    renderPagination();
  }

  async function load() {
    try {
      const [pharmacyData, orderData] = await Promise.all([
        callApi("/api/pharmacy-shortages"),
        callApi("/api/orders")
      ]);

      state.pharmacyRows = normalizePharmacyRows(pharmacyData.shortages || []);
      state.customerRows = normalizeCustomerRows(orderData.orders || []);
      state.page = Math.min(state.page, pageCount());
      render();
    } catch (error) {
      notify(error.message, "error");
    }
  }

  async function sendCurrentShortages() {
    try {
      const result = await callApi(
        "/api/pharmacy-shortages/whatsapp?kind=" + encodeURIComponent(state.filter)
      );

      try {
        await navigator.clipboard.writeText(result.message || "");
      } catch (_) {}

      if (window.openWhatsAppOnThisDevice) {
        window.openWhatsAppOnThisDevice(
          "whatsapp://send?text=" + encodeURIComponent(result.message || ""),
          "https://web.whatsapp.com/"
        );
      } else {
        window.open("https://web.whatsapp.com/", "_blank", "noopener");
      }

      notify(
        "تم تجهيز رسالة " +
        (state.filter === "pharmacy" ? "نواقص الصيدلية" :
         state.filter === "customer" ? "طلبات العملاء" : "كل النواقص") +
        " ونسخها."
      );
    } catch (error) {
      notify(error.message, "error");
    }
  }

  async function setAvailable(id) {
    try {
      await callApi(
        "/api/pharmacy-shortages/" + encodeURIComponent(id) + "/available",
        { method: "POST", body: "{}" }
      );
      notify("تم تسجيل توفر المنتج");
      await load();
    } catch (error) {
      notify(error.message, "error");
    }
  }

  async function undo(id) {
    try {
      const result = await callApi(
        "/api/pharmacy-shortages/" + encodeURIComponent(id) + "/undo",
        { method: "POST", body: "{}" }
      );
      notify("تم التراجع عن: " + (result.undone_action || "آخر إجراء"));
      await load();
    } catch (error) {
      notify(error.message, "error");
    }
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
    submit && (submit.disabled = true);

    try {
      if (state.editingId) {
        await callApi("/api/pharmacy-shortages/" + encodeURIComponent(state.editingId), {
          method: "PUT",
          body: JSON.stringify({ product_name: product, quantity, note })
        });
        notify("تم تعديل نقص الصيدلية");
      } else {
        await callApi("/api/pharmacy-shortages", {
          method: "POST",
          body: JSON.stringify({ product_name: product, quantity, note })
        });
        notify("تمت إضافة نقص الصيدلية");
      }
      closeForm();
      state.filter = "pharmacy";
      state.page = 1;
      await load();
    } catch (error) {
      notify(error.message, "error");
    } finally {
      submit && (submit.disabled = false);
    }
  }

  function bindPage() {
    document.querySelectorAll("[data-shortages-view]").forEach(button => {
      button.addEventListener("click", () => {
        state.filter = ["all", "pharmacy", "customer"].includes(button.dataset.shortagesView)
          ? button.dataset.shortagesView
          : "all";
        state.page = 1;
        render();
      });
    });

    document.getElementById("refresh-daily-shortages-btn")?.addEventListener("click", load);

    document.getElementById("pharmacy-shortages-limit")?.addEventListener("change", event => {
      state.pageSize = ["20", "30", "all"].includes(event.target.value)
        ? event.target.value
        : "20";
      state.page = 1;
      localStorage.setItem("ezz_shortages_page_size", state.pageSize);
      render();
    });

    document.getElementById("send-shortages-btn")?.addEventListener("click", sendCurrentShortages);
    document.getElementById("add-pharmacy-shortage-btn")?.addEventListener("click", () => openForm());
    document.getElementById("pharmacy-shortage-close-btn")?.addEventListener("click", closeForm);
    document.getElementById("pharmacy-shortage-cancel-btn")?.addEventListener("click", closeForm);
    document.getElementById("pharmacy-shortage-form")?.addEventListener("submit", saveForm);

    document.getElementById("pharmacy-shortage-modal")?.addEventListener("click", event => {
      if (event.target.id === "pharmacy-shortage-modal") closeForm();
    });

    state.filter = "all";
    state.page = 1;
    render();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindPage, { once: true });
  } else {
    bindPage();
  }

  window.dailyShortages = {
    load,
    open: () => {
      state.filter = "all";
      state.page = 1;
      render();
      return load();
    },
    switchFilter: setFilterCompat
  };

  function setFilterCompat(filter) {
    state.filter = ["all", "pharmacy", "customer"].includes(filter) ? filter : "all";
    state.page = 1;
    render();
  }
})();
