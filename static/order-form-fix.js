/* EZZ ORDER FORM FIX
   Important: do not replace the application's real submit handler.
   This file only augments the existing initializer so /api/orders continues to fire.
*/
(function () {
  'use strict';
  const FORM_ID = 'new-order-form';
  let originalInit = null;
  let wrapperInstalled = false;
  let helperBound = false;

  function normalizePhoneFixed(value) {
    let s = String(value || '')
      .replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
      .replace(/[۰-۹]/g, d => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))
      .trim();
    const explicitIntl = s.startsWith('+') || /^00\d+/.test(s);
    let digits = s.replace(/\D/g, '');
    if (digits.startsWith('00')) digits = digits.slice(2);
    if (explicitIntl) return digits;
    if (digits.startsWith('0') && digits.length === 10 && digits[1] === '5') return '966' + digits.slice(1);
    if (digits.startsWith('5') && digits.length === 9) return '966' + digits;
    return digits;
  }

  window.normalizePhoneClient = normalizePhoneFixed;

  function ensureProductRow() {
    const wrap = document.getElementById('product-items');
    if (!wrap) return;
    if (wrap.querySelector('.product-row')) return;
    if (typeof window.addProductRow === 'function') {
      window.addProductRow('', 1);
    }
  }

  function bindHelpers() {
    const form = document.getElementById(FORM_ID);
    if (!form || helperBound) return;
    helperBound = true;
    ensureProductRow();

    const addBtn = document.getElementById('add-product-btn');
    if (addBtn && !addBtn.dataset.orderFixBound) {
      addBtn.dataset.orderFixBound = '1';
      addBtn.addEventListener('click', () => {
        if (typeof window.addProductRow === 'function') window.addProductRow('', 1);
        else ensureProductRow();
      });
    }
  }

  function installWrapper() {
    if (wrapperInstalled) return;
    originalInit = typeof window.initNewOrder === 'function' ? window.initNewOrder : null;
    if (!originalInit) return;

    const wrapped = function () {
      if (wrapped.__ezzRunning) return;
      wrapped.__ezzRunning = true;
      try {
        originalInit.apply(this, arguments);
        bindHelpers();
      } finally {
        wrapped.__ezzRunning = false;
      }
    };
    wrapped.__ezzOrderFormWrapped = true;
    window.initNewOrder = wrapped;
    wrapperInstalled = true;
  }

  // app.js defines initNewOrder before this script in the production page.
  installWrapper();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindHelpers, { once: true });
  } else {
    bindHelpers();
  }
})();
