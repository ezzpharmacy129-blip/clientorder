(() => {
  const CANCELLED_STATUS = "ملغي";
  const CANCELLED_KEY = "cancelled";
  const CANCELLED_LABEL = "الطلبات الملغية";

  // Extend the existing dashboard without changing or deleting its existing data flow.
  const originalDashboardFilterLabel = dashboardFilterLabel;
  const originalDashboardFilterOrders = dashboardFilterOrders;
  const originalRenderDashboardCards = renderDashboardCards;
  const originalRenderDashboardResults = renderDashboardResults;
  const STANDARD_RESULTS_HEADER = document.querySelector("#dashboard-results-panel table thead tr")?.innerHTML || "";
  const CANCELLED_RESULTS_HEADER = `
    <th>رقم الطلب</th>
    <th>اسم العميل</th>
    <th>رقم الجوال</th>
    <th>المنتجات</th>
    <th>سبب الإلغاء</th>
    <th>تاريخ الطلب</th>
    <th>الحالة</th>
    <th>الإجراء</th>
  `;

  if (!statCards.some(card => card[2] === CANCELLED_KEY)) {
    statCards.push(["cancelled", CANCELLED_LABEL, CANCELLED_KEY]);
  }

  dashboardFilterLabel = function (key) {
    if (key === CANCELLED_KEY) return CANCELLED_LABEL;
    return originalDashboardFilterLabel(key);
  };

  dashboardFilterOrders = function (orders, key) {
    if (key === CANCELLED_KEY) {
      return orders.filter(o => o.Status === CANCELLED_STATUS);
    }
    return originalDashboardFilterOrders(orders, key);
  };

  renderDashboardCards = function (stats) {
    const cancelledCount = Array.isArray(dashboardAllOrders)
      ? dashboardAllOrders.filter(o => o.Status === CANCELLED_STATUS).length
      : 0;
    originalRenderDashboardCards({ ...(stats || {}), cancelled: cancelledCount });
  };

  function setResultsHeader(cancelled) {
    const header = document.querySelector("#dashboard-results-panel table thead tr");
    if (!header) return;
    header.innerHTML = cancelled ? CANCELLED_RESULTS_HEADER : STANDARD_RESULTS_HEADER;
  }

  function setContactFilterVisibility(cancelled) {
    const filter = document.getElementById("dashboard-contact-filter");
    if (!filter) return;
    filter.style.display = cancelled ? "none" : "";
    if (cancelled) filter.value = "";
  }

  function cancellationReason(order) {
    if (order.Contact_Status === "العميل رفض") {
      return "العميل رفض الطلب";
    }

    const itemReasons = [...new Set(
      (order.Items || [])
        .map(item => String(item.Unavailable_Reason || "").trim())
        .filter(Boolean)
    )];

    if (itemReasons.length) return itemReasons.join("، ");
    if (String(order.Notes || "").trim()) return String(order.Notes).trim();
    return "تم إلغاء الطلب";
  }

  function renderCancelledResults() {
    const panel = document.getElementById("dashboard-results-panel");
    if (!panel) return;

    panel.classList.remove("hidden");
    document.getElementById("dashboard-results-title").textContent = CANCELLED_LABEL;
    setResultsHeader(true);
    setContactFilterVisibility(true);

    const search = document.getElementById("dashboard-results-search").value.trim().toLowerCase();
    const baseOrders = dashboardFilterOrders(dashboardAllOrders, CANCELLED_KEY);
    let orders = baseOrders;

    if (search) {
      orders = orders.filter(order => {
        const products = (order.Items || []).map(item => item.Product_Name).join(" ");
        const reason = cancellationReason(order);
        return `${order.Order_ID} ${order.Customer_Name} ${order.Phone} ${products} ${reason}`
          .toLowerCase()
          .includes(search);
      });
    }

    document.getElementById("dashboard-results-subtitle").textContent = orders.length
      ? `يتم عرض ${orders.length} من أصل ${baseOrders.length} طلب ملغي.`
      : "لا توجد طلبات ملغية مطابقة حاليًا.";

    const body = document.getElementById("dashboard-results-body");
    if (!orders.length) {
      body.innerHTML = '<tr><td colspan="8" class="empty-state">لا توجد طلبات ملغية مطابقة ✅</td></tr>';
    } else {
      body.innerHTML = orders.map(order => `
        <tr>
          <td><strong>${esc(order.Order_ID)}</strong></td>
          <td><strong>${esc(order.Customer_Name)}</strong></td>
          <td>${esc(order.Phone)}</td>
          <td class="products-cell">${productsSummary(order)}</td>
          <td>${esc(cancellationReason(order))}</td>
          <td>${fmtDate(order.Order_Date)}</td>
          <td>${contactBadge(order.Contact_Status)}</td>
          <td>
            <button type="button" class="btn btn-secondary btn-sm dashboard-detail-btn" data-id="${esc(order.Order_ID)}">التفاصيل</button>
          </td>
        </tr>
      `).join("");

      body.querySelectorAll(".dashboard-detail-btn").forEach(button => {
        button.onclick = () => details(button.dataset.id);
      });
    }

    document.getElementById("dashboard-results-count").textContent = `عدد الطلبات الملغية: ${orders.length}`;
  }

  renderDashboardResults = function () {
    if (dashboardFilterKey === CANCELLED_KEY) {
      renderCancelledResults();
      return;
    }
    setResultsHeader(false);
    setContactFilterVisibility(false);
    originalRenderDashboardResults();
  };

  // Direct cancellation keeps the order and records the reason in the existing activity log.
  cancelOrder = function (id) {
    const reason = window.prompt(
      "سبب إلغاء الطلب (مثلاً: المنتج غير متوفر، العميل رفض، السعر غير مناسب):",
      ""
    );
    if (reason === null) return;

    const cleanedReason = reason.trim();
    openConfirm(
      cleanedReason
        ? `هل أنت متأكد من إلغاء هذا الطلب؟\nالسبب: ${cleanedReason}`
        : "هل أنت متأكد من إلغاء هذا الطلب؟",
      async () => {
        try {
          await apiFetch(`/api/orders/${id}/cancel`, {
            method: "POST",
            body: JSON.stringify({ note: cleanedReason })
          });
          toast("تم إلغاء الطلب وحفظ السبب");
          document.getElementById("order-modal").classList.add("hidden");
          await refresh();
          await loadDashboard();
        } catch (e) {
          toast(e.message, "error");
        }
      }
    );
  };
})();
