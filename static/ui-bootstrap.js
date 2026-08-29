/* EZZ UI BOOTSTRAP v2
   Creates the modal DOM synchronously before app.js DOMContentLoaded handlers run.
   UI structure only; data/actions remain in app.js/API.
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
  }

  // The script is injected at the end of <body>, so create the DOM now.
  // Waiting for DOMContentLoaded causes app.js to run first and fail in initModals().
  boot();
})();
