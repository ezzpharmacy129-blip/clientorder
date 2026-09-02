/* EZZ UI BOOTSTRAP v3
   Creates required modals and the Az Health structural shell before app.js DOMContentLoaded.
   UI structure only; existing data/API/actions remain unchanged.
*/
(function () {
  'use strict';

  function addModal(id, title, bodyHtml, footerHtml) {
    if (document.getElementById(id)) return;
    const overlay = document.createElement('div');
    overlay.id = id;
    overlay.className = 'modal-overlay hidden';
    overlay.setAttribute('aria-hidden', 'true');
    overlay.innerHTML = `
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="${id}-title">
        <div class="modal-header">
          <h3 id="${id}-title">${title}</h3>
          <button type="button" class="modal-close" data-ezz-close aria-label="إغلاق">✕</button>
        </div>
        <div class="modal-body">${bodyHtml}</div>
        ${footerHtml ? `<div class="modal-footer">${footerHtml}</div>` : ''}
      </div>`;
    document.body.appendChild(overlay);
    const close = overlay.querySelector('[data-ezz-close]');
    close?.addEventListener('click', () => {
      overlay.classList.add('hidden');
      overlay.setAttribute('aria-hidden', 'true');
    });
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        overlay.classList.add('hidden');
        overlay.setAttribute('aria-hidden', 'true');
      }
    });
  }

  function addRedesignAssets() {
    if (!document.head.querySelector('link[data-az-redesign]')) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = '/static/az-health-redesign.css?v=20260902-az-v3';
      link.dataset.azRedesign = 'true';
      document.head.appendChild(link);
    }
  }

  function createTopbar() {
    if (document.getElementById('az-topbar')) return;
    const main = document.querySelector('.app-main');
    if (!main) return;
    const bar = document.createElement('div');
    bar.id = 'az-topbar';
    bar.className = 'az-topbar';
    bar.innerHTML = `
      <div class="az-profile">
        <div class="az-avatar" aria-hidden="true">👤</div>
        <div class="az-profile-copy"><small>أهلًا بك</small><strong>المدير العام</strong></div>
      </div>
      <label class="az-search-shell" aria-label="البحث">
        <input id="az-global-search" class="az-search" type="search" placeholder="ابحث عن طلب، عميل، منتج..." autocomplete="off">
        <span class="az-shortcut">Ctrl K</span>
      </label>
      <button id="az-menu-btn" class="az-menu-btn" type="button" aria-label="فتح القائمة">☰</button>`;
    main.insertBefore(bar, main.firstElementChild);

    const search = document.getElementById('az-global-search');
    search?.addEventListener('input', () => {
      const value = search.value;
      const active = document.querySelector('.view.active')?.id || '';
      const target = active === 'view-orders' ? document.getElementById('orders-search') : document.getElementById('dashboard-search');
      if (target) {
        target.value = value;
        target.dispatchEvent(new Event('input', { bubbles: true }));
      }
    });
    search?.addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        const active = document.querySelector('.view.active')?.id || '';
        if (active !== 'view-orders') document.querySelector('[data-view="orders"]')?.click();
      }
    });
    document.addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        search?.focus();
      }
    });

    const menu = document.getElementById('az-menu-btn');
    menu?.addEventListener('click', () => document.body.classList.toggle('az-nav-open'));
    document.querySelectorAll('.nav-btn[data-view]').forEach(btn => btn.addEventListener('click', () => {
      if (window.matchMedia('(max-width: 720px)').matches) document.body.classList.remove('az-nav-open');
    }));
    window.addEventListener('resize', () => {
      if (!window.matchMedia('(max-width: 720px)').matches) document.body.classList.remove('az-nav-open');
    });
  }

  function createDashboardExtensions() {
    const dashboard = document.getElementById('view-dashboard');
    if (!dashboard || document.getElementById('az-dashboard-lower')) return;

    const lower = document.createElement('section');
    lower.id = 'az-dashboard-lower';
    lower.className = 'az-dashboard-lower';
    lower.innerHTML = `
      <article class="az-quick-card">
        <h3>تواصل سريع مع العملاء</h3>
        <p>انتقل مباشرة للطلبات أو أضف طلبًا جديدًا من نفس الصفحة.</p>
        <div class="az-quick-actions">
          <button type="button" class="btn btn-secondary" data-az-action="orders">عرض الطلبات</button>
          <button type="button" class="btn btn-secondary" data-az-action="new-order">+ طلب جديد</button>
        </div>
      </article>
      <article class="az-overview-card">
        <h3>نظرة عامة</h3>
        <p>ملخص سريع للحالة الحالية للنظام.</p>
        <div class="az-overview-row"><span>إجمالي الطلبات</span><strong data-az-stat="total">0</strong></div>
        <div class="az-overview-row"><span>بانتظار التوفر</span><strong data-az-stat="pending">0</strong></div>
        <div class="az-overview-row"><span>جاهز للتواصل</span><strong data-az-stat="available">0</strong></div>
        <div class="az-overview-row"><span>بانتظار رد العميل</span><strong data-az-stat="awaiting_reply">0</strong></div>
      </article>`;
    dashboard.appendChild(lower);

    lower.querySelector('[data-az-action="orders"]')?.addEventListener('click', () => document.querySelector('[data-view="orders"]')?.click());
    lower.querySelector('[data-az-action="new-order"]')?.addEventListener('click', () => document.querySelector('[data-view="new-order"]')?.click());

    const syncOverview = () => {
      const cards = document.getElementById('stats-grid');
      if (!cards) return;
      const labels = [...cards.querySelectorAll('.stat-card')];
      const values = {};
      labels.forEach(card => {
        const key = card.getAttribute('data-dashboard-filter');
        const value = card.querySelector('.stat-value')?.textContent || '0';
        if (key) values[key] = value;
      });
      Object.entries(values).forEach(([k,v]) => {
        document.querySelector(`[data-az-stat="${k}"]`)?.replaceChildren(document.createTextNode(v));
      });
    };
    const observer = new MutationObserver(syncOverview);
    const stats = document.getElementById('stats-grid');
    if (stats) observer.observe(stats, { childList: true, subtree: true, characterData: true });
    syncOverview();
  }

  function createFooter() {
    if (document.getElementById('az-footer')) return;
    const main = document.querySelector('.app-main');
    if (!main) return;
    const footer = document.createElement('footer');
    footer.id = 'az-footer';
    footer.className = 'az-footer';
    footer.innerHTML = `<span class="az-footer-mark">♥ صيدلية عز الصحة — رعاية من القلب</span><span class="az-footer-note">جميع الحقوق محفوظة</span>`;
    main.appendChild(footer);
  }

  function buildRedesign() {
    addRedesignAssets();
    createTopbar();
    createDashboardExtensions();
    createFooter();
  }

  function boot() {
    if (!document.body) return;

    addModal(
      'order-modal',
      'تفاصيل الطلب',
      '<div id="modal-body"></div>',
      '<button type="button" class="btn btn-secondary" id="modal-close-btn">إغلاق</button>'
    );

    const orderModal = document.getElementById('order-modal');
    if (orderModal) {
      const nestedBody = orderModal.querySelector('#modal-body');
      const outerBody = orderModal.querySelector('.modal-body');
      if (nestedBody && outerBody && nestedBody.parentElement !== outerBody) outerBody.appendChild(nestedBody);
      const close = document.getElementById('modal-close-btn');
      close?.addEventListener('click', () => {
        orderModal.classList.add('hidden');
        orderModal.setAttribute('aria-hidden', 'true');
        orderModal.style.display = 'none';
      });
    }

    addModal(
      'availability-modal',
      'تحديث توفر المنتجات',
      '<div id="availability-items"></div>',
      '<button type="button" class="btn btn-secondary" id="availability-cancel-btn">إلغاء</button><button type="button" class="btn btn-primary" id="availability-save-btn">حفظ حالة التوفر</button>'
    );
    const availability = document.getElementById('availability-modal');
    if (availability && !document.getElementById('availability-close-btn')) {
      const close = document.createElement('button');
      close.type = 'button';
      close.id = 'availability-close-btn';
      close.className = 'modal-close';
      close.setAttribute('aria-label', 'إغلاق');
      close.textContent = '✕';
      availability.querySelector('.modal-header')?.appendChild(close);
    }

    addModal(
      'confirm-modal',
      'تأكيد العملية',
      '<div id="confirm-message"></div>',
      '<button type="button" class="btn btn-secondary" id="confirm-no-btn">إلغاء</button><button type="button" class="btn btn-danger" id="confirm-yes-btn">تأكيد</button>'
    );

    addModal(
      'postpone-modal',
      'تأجيل المتابعة',
      '<div class="postpone-options"><button type="button" class="btn btn-outline postpone-quick" data-days="1">غدًا</button><button type="button" class="btn btn-outline postpone-quick" data-days="3">بعد 3 أيام</button><button type="button" class="btn btn-outline postpone-quick" data-days="7">بعد أسبوع</button><div class="form-row"><label>تاريخ مخصص</label><input type="date" id="postpone-custom-date"></div></div>',
      '<button type="button" class="btn btn-secondary" id="postpone-close-btn">إلغاء</button><button type="button" class="btn btn-primary" id="postpone-custom-confirm">حفظ</button>'
    );

    buildRedesign();
  }

  boot();
})();
