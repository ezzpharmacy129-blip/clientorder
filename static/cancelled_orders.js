(() => {
  const CANCELLED_STATUS = "ملغي";
  const CANCELLED_KEY = "cancelled";
  const CANCELLED_LABEL = "الطلبات الملغية";

  // Keep the existing dashboard architecture and extend it with one first-class filter.
  const originalDashboardFilterLabel = dashboardFilterLabel;
  const originalDashboardFilterOrders = dashboardFilterOrders;
  const originalRenderDashboardCards = renderDashboardCards;
  const originalRenderDashboardResults = renderDashboardResults;
  const originalCancelOrder = cancelOrder;

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

    const contactFilter = document.getElementById("dashboard-contact-filter");
    if (contactFilter) contactFilter.value = "";

    const search = document.getElementById("dashboard-results-search").value.trim().toLowerCase();
    let orders = dashboardFilterOrders(dashboardAllOrders, CANCELLED_KEY);

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
      ? `يتم عرض ${orders.length} من أصل ${dashboardFilterOrders(dashboardAllOrders, CANCELLED_KEY).length} طلب ملغي.`
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
    originalRenderDashboardResults();
  };

  // Direct cancellation now records a human-readable reason in the existing activity log.
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

  // app.js registers its DOMContentLoaded handler before this file is loaded.
  // This handler only refreshes the new card/filter after the initial dashboard load.
  document.addEventListener("DOMContentLoaded", () => {
    if (typeof window.dashboardStats === "object" && window.dashboardStats) {
      renderDashboardCards(window.dashboardStats);
    }
  });
})();
