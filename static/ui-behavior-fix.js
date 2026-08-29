/* Final UI behavior fix: modal visibility + automatic close after successful actions. */
(function () {
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

  function install() {
    if (typeof window.details === 'function' && !window.details.__ezzFinalWrapped) {
      const originalDetails = window.details;
      const wrappedDetails = async function (id) {
        const result = await originalDetails(id);
        showModal('order-modal');
        return result;
      };
      wrappedDetails.__ezzFinalWrapped = true;
      window.details = wrappedDetails;
      document.querySelectorAll('.details-btn,.dashboard-detail-btn,.act-details').forEach(btn => {
        btn.addEventListener('click', () => showModal('order-modal'));
      });
    }

    const modal = document.getElementById('order-modal');
    if (modal && !modal.dataset.ezzFinalBound) {
      modal.dataset.ezzFinalBound = '1';
      modal.addEventListener('click', e => { if (e.target === modal) hideModal('order-modal'); });
    }

    const availability = document.getElementById('availability-modal');
    if (availability && !availability.dataset.ezzFinalBound) {
      availability.dataset.ezzFinalBound = '1';
      availability.addEventListener('click', e => { if (e.target === availability) hideModal('availability-modal'); });
    }

    if (typeof window.saveAvailability === 'function' && !window.saveAvailability.__ezzFinalWrapped) {
      const originalSave = window.saveAvailability;
      const wrappedSave = async function () {
        try {
          const result = await originalSave.apply(this, arguments);
          const modal = document.getElementById('availability-modal');
          if (modal && !modal.classList.contains('hidden')) hideModal('availability-modal');
          const orderModal = document.getElementById('order-modal');
          if (orderModal && !orderModal.classList.contains('hidden')) hideModal('order-modal');
          return result;
        } catch (err) {
          throw err;
        }
      };
      wrappedSave.__ezzFinalWrapped = true;
      window.saveAvailability = wrappedSave;
      const saveBtn = document.getElementById('availability-save-btn');
      if (saveBtn) saveBtn.onclick = wrappedSave;
    }
  }

  // app.js has already defined the functions by the time this file runs;
  // install after DOMContentLoaded so the original initializer has bound its buttons first.
  document.addEventListener('DOMContentLoaded', install);
})();
