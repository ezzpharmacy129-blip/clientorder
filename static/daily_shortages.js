/* Daily Pharmacy Shortages — single owner for shortages page */
(() => {
  "use strict";

  const state = {
    pharmacyRows: [],
    customerRows: [],
    filter: "all",
    limit: localStorage.getItem("ezz_pharmacy_shortages_limit") || "20",
    editingId: null
  };

  const escLocal = window.esc || (s => String(s ?? "").replace(/[&<>"]/g, c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"
  }[c])));
  const dateLocal = window.fmtDate || (s => s ? String(s).split(" ")[0].split("-").reverse().join("/") : "—");
  const callApi = window.apiFetch || (async (url, options={}) => {
    const r = await fetch(url, options);
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || "حدث خطأ");
    return d;
  });
  const notify = window.toast || ((m) => alert(m));

  function normalizeCustomerRows(orders) {
    const rows = [];

    (orders || []).forEach(order => {
      const pending = (order.Items || []).filter(
        item => item.Availability_Status === "بانتظار التوفر"
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

  function currentRows() {
    if (state.filter === "pharmacy") {
      const count = state.limit === "all"
        ? state.pharmacyRows.length
        : Math.max(1, Number(state.limit) || 20);
      return state.pharmacyRows.slice(0, count);
    }

    if (state.filter === "customer") {
      return state.customerRows;
    }

    return [...state.customerRows, ...state.pharmacyRows].sort(
      (a, b) => String(b.date || "").localeCompare(String(a.date || ""))
    );
  }

  function setFilter(filter) {
    state.filter = ["pharmacy", "customer", "all"].includes(filter)
      ? filter
      : "all";

    render();
  }

  function syncFilterButtons() {
    document.querySelectorAll("[data-shortages-view]").forEach(button => {
      const active = button.dataset.shortagesView === state.filter;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
  }

  function render() {
    const title = document.getElementById("daily-shortages-title");
    const subtitle = document.getElementById("daily-shortages-subtitle");
    const summary = document.getElementById("daily-shortages-summary");
    const body = document.getElementById("daily-shortages-table-body");
    const limitWrap = document.getElementById("pharmacy-shortages-limit-wrap");
    const limitSelect = document.getElementById("pharmacy-shortages-limit");

    if (!body) return;

    const labels = {
      all: "الكل",
      pharmacy: "نواقص الصيدلية",
      customer: "طلبات العملاء"
    };

    const rows = currentRows();
    const total =
      state.filter === "pharmacy"
        ? state.pharmacyRows.length
        : state.filter === "customer"
          ? state.customerRows.length
          : state.customerRows.length + state.pharmacyRows.length;

    title.textContent = state.filter === "all" ? "النواقص" : "📦 " + labels[state.filter];
    subtitle.textContent =
      state.filter === "all"
        ? "جميع النواقص الحالية في مكان واحد."
        : state.filter === "pharmacy"
          ? "النواقص المسجلة على مستوى الصيدلية."
          : "المنتجات غير المتوفرة المرتبطة بطلبات العملاء.";

    limitWrap?.classList.toggle("hidden", state.filter !== "pharmacy");

    if (limitSelect) {
      limitSelect.value = ["20", "30", "all"].includes(state.limit)
        ? state.limit
        : "20";
    }

    summary.textContent =
      state.filter === "pharmacy" && state.limit !== "all"
        ? "عرض " + rows.length + " من أصل " + total + " نقص"
        : "عدد النتائج: " + rows.length;

    const pharmacyCount = document.getElementById("pharmacy-shortages-tab-count");
    const customerCount = document.getElementById("customer-shortages-tab-count");
    if (pharmacyCount) pharmacyCount.textContent = state.pharmacyRows.length;
    if (customerCount) customerCount.textContent = state.customerRows.length;

    syncFilterButtons();

    if (!rows.length) {
      body.innerHTML =
        '<tr><td colspan="9" class="empty-state">لا توجد نواقص ضمن هذا التصنيف ✅</td></tr>';
      return;
    }

    body.innerHTML = rows.map(row => {
      const type = row.type === "pharmacy"
        ? '<span class="shortage-type shortage-type-pharmacy">الصيدلية</span>'
        : '<span class="shortage-type shortage-type-customer">طلب عميل</span>';

      const status = row.type === "pharmacy"
        ? '<span class="status-badge ' +
          (row.status === "تم التوفير" ? "status-picked" : "status-pending") +
          '">' + escLocal(row.status) + '</span>'
        : '<span class="status-badge status-pending">بانتظار التوفير</span>';

      let action = "";
      if (row.type === "pharmacy") {
        action =
          (row.status === "تم التوفير"
            ? '<button type="button" class="btn btn-secondary btn-sm ps-undo" data-id="' + escLocal(row.shortageId) + '">↩️ تراجع</button>'
            : '<button type="button" class="btn btn-primary btn-sm ps-available" data-id="' + escLocal(row.shortageId) + '">تم التوفير</button>') +
          '<button type="button" class="btn btn-outline btn-sm ps-edit" data-id="' + escLocal(row.shortageId) + '">تعديل</button>';
      } else {
        action =
          '<button type="button" class="btn btn-outline btn-sm ps-detail" data-id="' +
          escLocal(row.orderId) + '">التفاصيل</button>';
      }

      return '<tr>' +
        '<td>' + type + '</td>' +
        '<td><strong>' + escLocal(row.orderId) + '</strong></td>' +
        '<td>' + escLocal(row.customer) + '</td>' +
        '<td dir="ltr">' + escLocal(row.phone) + '</td>' +
        '<td><strong>' + escLocal(row.product) + '</strong>' +
          (row.note ? '<div class="daily-shortage-note">' + escLocal(row.note) + '</div>' : '') +
        '</td>' +
        '<td>' + escLocal(row.quantity) + '</td>' +
        '<td>' + dateLocal(row.date) + '</td>' +
        '<td>' + status + '</td>' +
        '<td><div class="daily-shortage-actions">' + action + '</div></td>' +
      '</tr>';
    }).join("");

    body.querySelectorAll(".ps-detail").forEach(button => {
      button.onclick = () => {
        if (typeof window.details === "function") {
          window.details(button.dataset.id);
        }
      };
    });

    body.querySelectorAll(".ps-available").forEach(button => {
      button.onclick = () => setAvailable(button.dataset.id);
    });

    body.querySelectorAll(".ps-undo").forEach(button => {
      button.onclick = () => undo(button.dataset.id);
    });

    body.querySelectorAll(".ps-edit").forEach(button => {
      button.onclick = () => {
        const row = state.pharmacyRows.find(x => x.shortageId === button.dataset.id);
        if (row) openForm(row);
      };
    });
  }

  async function load() {
    try {
      const [pharmacyData, orderData] = await Promise.all([
        callApi("/api/pharmacy-shortages"),
        callApi("/api/orders")
      ]);

      state.pharmacyRows = normalizePharmacyRows(pharmacyData.shortages || []);
      state.customerRows = normalizeCustomerRows(orderData.orders || []);

      render();
    } catch (error) {
      notify(error.message, "error");
    }
  }

  function open() {
    state.filter = "all";
    localStorage.setItem("ezz_daily_shortages_filter", "all");
    render();
    return load();
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
      localStorage.setItem("ezz_daily_shortages_filter", "pharmacy");
      await load();
    } catch (error) {
      notify(error.message, "error");
    } finally {
      submit && (submit.disabled = false);
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

  async function sendShortages(kind) {
    try {
      const result = await callApi(
        "/api/pharmacy-shortages/whatsapp?kind=" + encodeURIComponent(kind)
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

      notify("تم تجهيز الرسالة ونسخها. الصقها في القروب ثم أرسلها.");
    } catch (error) {
      notify(error.message, "error");
    }
  }

  function bindPage() {
    document.querySelectorAll("[data-shortages-view]").forEach(button => {
      button.addEventListener("click", () => {
        setFilter(button.dataset.shortagesView || "all");
      });
    });

    document.getElementById("refresh-daily-shortages-btn")?.addEventListener("click", load);

    document.getElementById("pharmacy-shortages-limit")?.addEventListener("change", event => {
      state.limit = ["20", "30", "all"].includes(event.target.value)
        ? event.target.value
        : "20";
      localStorage.setItem("ezz_pharmacy_shortages_limit", state.limit);
      render();
    });

    document.getElementById("add-pharmacy-shortage-btn")?.addEventListener("click", () => openForm());
    document.getElementById("pharmacy-shortage-close-btn")?.addEventListener("click", closeForm);
    document.getElementById("pharmacy-shortage-cancel-btn")?.addEventListener("click", closeForm);
    document.getElementById("pharmacy-shortage-form")?.addEventListener("submit", saveForm);

    document.getElementById("pharmacy-shortage-modal")?.addEventListener("click", event => {
      if (event.target.id === "pharmacy-shortage-modal") closeForm();
    });

    document.getElementById("send-customer-shortages")?.addEventListener("click", () => sendShortages("customer"));
    document.getElementById("send-pharmacy-shortages")?.addEventListener("click", () => sendShortages("pharmacy"));
    document.getElementById("send-all-shortages")?.addEventListener("click", () => sendShortages("all"));

    state.filter = "all";
    render();
  }

  function init() {
    bindPage();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }

  window.dailyShortages = { load, open, switchFilter: setFilter };
})();
