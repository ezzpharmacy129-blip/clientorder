(function () {
  'use strict';

  const META = {
    overdue: {
      label: 'متأخرة',
      itemClass: 'action-item-overdue',
      icon: '🔴',
      nextFallback: 'متابعة عاجلة',
      primary: 'واتساب'
    },
    needs_supply: {
      label: 'تحتاج توفير',
      itemClass: 'action-item-supply',
      icon: '📦',
      nextFallback: 'متابعة التوفير',
      primary: 'تحديث التوفر'
    },
    awaiting_reply: {
      label: 'تنتظر رد العميل',
      itemClass: 'action-item-reply',
      icon: '🟣',
      nextFallback: 'متابعة رد العميل',
      primary: 'تواصل مع العميل'
    },
    today: {
      label: 'متابعة اليوم',
      itemClass: 'action-item-today',
      icon: '🔵',
      nextFallback: 'متابعة العميل',
      primary: 'تواصل مع العميل'
    }
  };

  let snapshot = null;
  let selectedCategory = null;

  const $ = (id) => document.getElementById(id);

  function esc(value) {
    return typeof window.esc === 'function'
      ? window.esc(value)
      : String(value ?? '').replace(/[&<>"']/g, function (ch) {
          return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[ch];
        });
  }

  function ageText(order) {
    const created = String(order?.Created_At || '');
    const datePart = created.split(' ')[0];
    if (!/^\d{4}-\d{2}-\d{2}$/.test(datePart)) return '';
    const today = typeof window.todayISO === 'function' ? window.todayISO() : new Date().toISOString().slice(0,10);
    const days = Math.max(0, Math.round(
      (Date.parse(today + 'T00:00:00') - Date.parse(datePart + 'T00:00:00')) / 86400000
    ));
    if (days === 0) return 'اليوم';
    if (days === 1) return 'منذ يوم';
    return 'منذ ' + days + ' أيام';
  }

  function selectedItems() {
    const items = snapshot?.action_center?.items || [];
    return selectedCategory ? items.filter((item) => item.action_key === selectedCategory) : [];
  }

  function renderSummary() {
    const summary = snapshot?.action_center?.summary || {};
    const values = {
      overdue: summary.overdue || 0,
      needs_supply: summary.needs_supply || 0,
      awaiting_reply: summary.awaiting_reply || 0,
      today: summary.today || 0
    };

    Object.keys(values).forEach((key) => {
      const node = $('action-count-' + (key === 'needs_supply' ? 'supply' : key === 'awaiting_reply' ? 'reply' : key));
      if (node) node.textContent = String(values[key]);
    });

    document.querySelectorAll('#action-center [data-action-category]').forEach((button) => {
      const active = button.dataset.actionCategory === selectedCategory;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
    });
  }

  function renderList() {
    const title = $('action-center-title');
    const subtitle = $('action-center-subtitle');
    const list = $('action-center-list');
    if (!title || !subtitle || !list) return;

    const total = Number(snapshot?.action_center?.total_actionable || 0);

    if (!selectedCategory) {
      title.textContent = total ? 'تحتاج إجراء الآن' : 'لا توجد إجراءات معلقة';
      subtitle.textContent = total
        ? total + ' طلبات تحتاج اهتمامًا — اختر نوع الإجراء فقط.'
        : 'كل الطلبات الحالية لا تحتاج إجراءً من الموظف.';
      list.innerHTML = total
        ? '<div class="action-center-empty"><div class="action-empty-icon">⚡</div><strong>اختر نوع الإجراء من الأعلى</strong><span>سيظهر هنا فقط ما يحتاجه الموظف.</span></div>'
        : '<div class="action-center-empty"><div class="action-empty-icon">✓</div><strong>ممتاز، لا توجد طلبات تحتاج إجراء الآن</strong><span>يمكنك متابعة العمل بشكل طبيعي.</span></div>';
      return;
    }

    const meta = META[selectedCategory];
    const items = selectedItems();

    title.textContent = meta ? 'طلبات «' + meta.label + '»' : 'الطلبات';
    subtitle.textContent = items.length
      ? items.length + (items.length === 1 ? ' طلب' : ' طلبات') + ' ضمن هذا الإجراء.'
      : '0 طلبات ضمن هذا الإجراء.';

    if (!items.length) {
      list.innerHTML =
        '<div class="action-center-empty action-empty-selected">' +
          '<div class="action-empty-icon">✓</div>' +
          '<strong>لا توجد طلبات ضمن «' + esc(meta?.label || 'هذا التصنيف') + '»</strong>' +
          '<span>العدد أعلاه هو العدد الفعلي لهذا التصنيف.</span>' +
        '</div>';
      return;
    }

    list.innerHTML = items.map(function (order) {
      const age = ageText(order);
      const shortageCount = Number(order.shortage_count || 0);
      let primary = '';

      if (selectedCategory === 'needs_supply') {
        primary = '<button type="button" class="btn btn-primary btn-sm ac-primary-supply" data-order-id="' + esc(order.Order_ID) + '">تحديث التوفر</button>';
      } else {
        primary = '<button type="button" class="btn btn-primary btn-sm ac-primary-wa" data-order-id="' + esc(order.Order_ID) + '">💬 ' + esc(meta.primary) + '</button>';
      }

      return '<article class="action-item ' + esc(meta.itemClass) + '">' +
        '<div class="action-item-main">' +
          '<div class="action-item-head"><strong>' + esc(order.Order_ID) + '</strong><span class="action-badge">' + esc(meta.icon + ' ' + meta.label) + '</span></div>' +
          '<div class="action-customer"><strong>' + esc(order.Customer_Name) + '</strong><span>' + esc(order.Phone) + '</span></div>' +
          '<div class="action-item-meta">' +
            '<span>➡️ ' + esc(order.next_action || meta.nextFallback) + '</span>' +
            (age ? '<span>⏱ ' + esc(age) + '</span>' : '') +
            (shortageCount ? '<span>📦 ' + shortageCount + ' نواقص</span>' : '') +
          '</div>' +
          '<div class="action-item-hint">' + esc(order.action_hint || '') + '</div>' +
        '</div>' +
        '<div class="action-item-actions">' +
          primary +
          '<button type="button" class="btn btn-secondary btn-sm ac-open-order" data-order-id="' + esc(order.Order_ID) + '">فتح الطلب</button>' +
        '</div>' +
      '</article>';
    }).join('');

    list.querySelectorAll('.ac-primary-wa').forEach((button) => {
      button.addEventListener('click', function () {
        if (typeof window.openClientWhatsApp === 'function') window.openClientWhatsApp(button.dataset.orderId);
      });
    });

    list.querySelectorAll('.ac-primary-supply').forEach((button) => {
      button.addEventListener('click', function () {
        if (typeof window.openAvailability === 'function') window.openAvailability(button.dataset.orderId);
      });
    });

    list.querySelectorAll('.ac-open-order').forEach((button) => {
      button.addEventListener('click', function () {
        if (typeof window.details === 'function') window.details(button.dataset.orderId);
      });
    });
  }

  function render() {
    renderSummary();
    renderList();
  }

  function receiveDashboard(event) {
    snapshot = event?.detail || null;
    render();
  }

  function init() {
    const root = $('action-center');
    if (!root) return;

    document.addEventListener('ezz:dashboard-data', receiveDashboard);

    const refresh = $('action-center-refresh');
    if (refresh) {
      refresh.addEventListener('click', function () {
        selectedCategory = null;
        if (typeof window.loadDashboard === 'function') window.loadDashboard();
        else render();
      });
    }

    root.addEventListener('click', function (event) {
      const button = event.target.closest?.('[data-action-category]');
      if (!button || !root.contains(button)) return;
      event.preventDefault();
      event.stopPropagation();
      const category = button.dataset.actionCategory || null;
      selectedCategory = selectedCategory === category ? null : category;
      render();
      const list = $('action-center-list');
      if (selectedCategory && list) list.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    });

    // Supports dashboards that finish loading before this module runs.
    if (window.dashboardStats) {
      snapshot = window.dashboardStats;
      render();
    } else {
      render();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, {once: true});
  } else {
    init();
  }
})();
