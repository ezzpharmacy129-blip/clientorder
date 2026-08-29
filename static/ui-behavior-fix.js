/* EZZ FINAL UI BEHAVIOR
   Keeps core application functions intact.
   Successful modal actions close automatically; failed actions remain visible.
*/
(function () {
  'use strict';

  function hideModal(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.add('hidden');
    el.setAttribute('aria-hidden', 'true');
    el.style.display = 'none';
    el.style.visibility = 'hidden';
    el.style.opacity = '0';
    el.style.pointerEvents = 'none';
  }

  function showModal(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    el.classList.remove('hidden');
    el.setAttribute('aria-hidden', 'false');
    el.style.display = 'flex';
    el.style.visibility = 'visible';
    el.style.opacity = '1';
    el.style.pointerEvents = 'auto';
    return el;
  }

  function closeTransientModals() {
    hideModal('availability-modal');
    hideModal('confirm-modal');
    hideModal('postpone-modal');
    hideModal('order-modal');
  }

  function install() {
    const orderModal = document.getElementById('order-modal');
    if (orderModal && !orderModal.dataset.ezzFinalBoundV2) {
      orderModal.dataset.ezzFinalBoundV2 = '1';
      orderModal.addEventListener('click', e => {
        if (e.target === orderModal) hideModal('order-modal');
      });
    }

    const availabilityModal = document.getElementById('availability-modal');
    if (availabilityModal && !availabilityModal.dataset.ezzFinalBoundV2) {
      availabilityModal.dataset.ezzFinalBoundV2 = '1';
      availabilityModal.addEventListener('click', e => {
        if (e.target === availabilityModal) hideModal('availability-modal');
      });
    }

    if (typeof window.saveAvailability === 'function' && !window.saveAvailability.__ezzFinalWrappedV2) {
      const originalSave = window.saveAvailability;
      const wrappedSave = async function () {
        const result = await originalSave.apply(this, arguments);
        closeTransientModals();
        return result;
      };
      wrappedSave.__ezzFinalWrappedV2 = true;
      window.saveAvailability = wrappedSave;
      const saveBtn = document.getElementById('availability-save-btn');
      if (saveBtn) saveBtn.onclick = wrappedSave;
    }

    if (typeof window.openAvailability === 'function' && !window.openAvailability.__ezzFinalWrappedV2) {
      const originalOpen = window.openAvailability;
      const wrappedOpen = async function () {
        const result = await originalOpen.apply(this, arguments);
        hideModal('order-modal');
        showModal('availability-modal');
        return result;
      };
      wrappedOpen.__ezzFinalWrappedV2 = true;
      window.openAvailability = wrappedOpen;
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, { once: true });
  } else {
    install();
  }
})();
