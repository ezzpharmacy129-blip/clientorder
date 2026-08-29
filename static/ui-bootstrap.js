/* EZZ UI BOOTSTRAP v1
   Provides the static modal containers required by static/app.js.
   This is UI structure only; all data and actions remain in app.js/API.
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
      <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="${id}-title">
        <div class="modal-header">
          <h3 id="${id}-title">${title}</h3>
          <button type="button" class="modal-close" data-ezz-close>✕</button>
        </div>
        <div class="modal-body">${bodyHtml}</div>
        ${footerHtml ? `<div class="modal-footer">${footerHtml}</div>` : ''}
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('[data-ezz-close]')?.addEventListener('click', () => {
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

  function boot() {
    addModal(
      'order-modal',
      'تفاصيل الطلب',
      '<div id="modal-body"></div>',
      '<button type="button" class="btn btn-secondary" id="modal-close-btn">إغلاق</button>'
    );

    const orderModal = document.getElementById('order-modal');
    if (orderModal) {
      orderModal.querySelector('.modal-card')?.classList.add('ezz-order-modal-card');
      orderModal.querySelector('.modal-body')?.replaceChildren(orderModal.querySelector('#modal-body'));
      const close = document.getElementById('modal-close-btn');
      close?.addEventListener('click', () => {
        orderModal.classList.add('hidden');
        orderModal.setAttribute('aria-hidden', 'true');
      });
    }

    addModal(
      'availability-modal',
      'تحديث توفر المنتجات',
      '<div id="availability-items"></div>',
      '<button type="button" class="btn btn-secondary" id="availability-cancel-btn">إلغاء</button><button type="button" class="btn btn-primary" id="availability-save-btn">حفظ حالة التوفر</button>'
    );

    const availability = document.getElementById('availability-modal');
    if (availability) {
      const extraClose = document.createElement('button');
      extraClose.type = 'button';
      extraClose.id = 'availability-close-btn';
      extraClose.className = 'modal-close sr-only';
      extraClose.setAttribute('aria-hidden', 'true');
      availability.appendChild(extraClose);
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
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
})();
