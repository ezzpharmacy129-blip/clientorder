(() => {
  'use strict';

  const page = document.body.dataset.chronicPage;
  const statusLabels = {active:'نشط', postponed:'مؤجل', stopped:'متوقف', needs_review:'يحتاج مراجعة'};
  const customerMap = new Map();
  const medicationMap = new Map();
  let messageTemplates = {
    general: 'السلام عليكم {اسم_العميل}، معك صيدلية عز الصحة. هذه رسالة متابعة للعلاج المزمن، ويسعدنا خدمتك ومتابعة مواعيد إعادة صرف أدويتك.',
    refill: 'السلام عليكم {اسم_العميل}، نذكّرك من صيدلية عز الصحة بأن موعد إعادة صرف {اسم_الدواء} {التركيز} متوقع بتاريخ {موعد_إعادة_الصرف}. للتأكيد أو الاستفسار يسعدنا تواصلك معنا.',
  };
  let forecastRows = [];
  let toastTimer;

  const $ = (selector, root=document) => root.querySelector(selector);
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const statusBadge = status => `<span class="cc-badge ${escapeHtml(status)}">${escapeHtml(statusLabels[status] || status)}</span>`;
  const formatNumber = value => new Intl.NumberFormat('ar-SA', {maximumFractionDigits:3}).format(Number(value || 0));
  const formatDate = value => value ? new Intl.DateTimeFormat('ar-SA-u-ca-gregory', {dateStyle:'medium', timeStyle:'short', timeZone:'Asia/Riyadh'}).format(new Date(value)) : '—';
  const localDateTimeValue = date => {
    const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return shifted.toISOString().slice(0,16);
  };

  function normalizeWhatsAppPhone(value) {
    let phone = String(value || '')
      .replace(/[٠-٩]/g, digit => String('٠١٢٣٤٥٦٧٨٩'.indexOf(digit)))
      .replace(/\D/g, '');
    if (phone.startsWith('00')) phone = phone.slice(2);
    if (phone.startsWith('0') && phone.length === 10) phone = `966${phone.slice(1)}`;
    else if (phone.startsWith('5') && phone.length === 9) phone = `966${phone}`;
    return phone;
  }

  function openWhatsApp(phoneValue, message) {
    const phone = normalizeWhatsAppPhone(phoneValue);
    if (!phone || phone.length < 9) {
      showToast('رقم هاتف العميل غير صالح للإرسال عبر واتساب', true);
      return;
    }
    window.open(`https://wa.me/${phone}?text=${encodeURIComponent(message)}`, '_blank', 'noopener,noreferrer');
  }

  function sendCustomerWhatsApp(customer) {
    if (!customer?.reminder_consent) return showToast('العميل لم يوافق على رسائل التذكير', true);
    openWhatsApp(customer.phone, renderMessageTemplate(messageTemplates.general, {'اسم_العميل':customer.name}));
  }

  function sendMedicationWhatsApp(medication) {
    if (!medication?.reminder_consent) return showToast('العميل لم يوافق على رسائل التذكير', true);
    if (!medication.expected_refill_at) return showToast('سجّل عملية صرف أولًا لحساب موعد إعادة الصرف', true);
    openWhatsApp(medication.phone, renderMessageTemplate(messageTemplates.refill, {
      'اسم_العميل': medication.customer_name,
      'اسم_الدواء': medication.name,
      'التركيز': medication.strength || '',
      'موعد_إعادة_الصرف': formatDate(medication.expected_refill_at),
    }));
  }

  function renderMessageTemplate(template, values) {
    let result = String(template || '');
    Object.entries(values).forEach(([key, value]) => {
      result = result.split(`{${key}}`).join(String(value ?? ''));
    });
    return result.replace(/ +([،,.])/g, '$1').trim();
  }

  async function loadMessageTemplates() {
    const data = await api('/api/chronic-care/message-templates');
    messageTemplates = {...messageTemplates, ...(data.templates || {})};
  }

  function openMessageTemplates() {
    const form = $('#message-templates-form');
    form.elements.general.value = messageTemplates.general;
    form.elements.refill.value = messageTemplates.refill;
    $('#message-templates-dialog').showModal();
  }

  function showToast(message, error=false) {
    const toast = $('#cc-toast');
    if (!toast) return;
    clearTimeout(toastTimer);
    toast.textContent = message;
    toast.className = `cc-toast show${error ? ' error' : ''}`;
    toastTimer = setTimeout(() => toast.className = 'cc-toast', 3200);
  }

  async function api(url, options={}) {
    const request = {...options, headers:{'Content-Type':'application/json', ...(options.headers || {})}};
    const sender = window.ezzCsrf?.fetch || window.fetch.bind(window);
    const response = await sender(url, request);
    let body = {};
    try { body = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(body.error || 'تعذر إكمال العملية');
    return body;
  }

  function debounce(fn, wait=250) {
    let timer;
    return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), wait); };
  }

  function closeDialog(dialog) {
    if (dialog?.open) dialog.close();
  }

  function setupDialogClosers() {
    document.addEventListener('click', event => {
      const button = event.target.closest('[data-close]');
      if (button) closeDialog(button.closest('dialog'));
    });
    document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('click', event => {
      if (event.target === dialog) dialog.close();
    }));
  }

  async function loadDashboardSummary() {
    const data = await api('/api/chronic-care/dashboard');
    $('#stat-active-customers').textContent = data.active_customers;
    $('#stat-active-medications').textContent = data.active_medications;
    $('#stat-due-today').textContent = data.due_today;
    $('#stat-due-7').textContent = data.due_7;
    $('#stat-due-14').textContent = data.due_14;
    $('#stat-due-30').textContent = data.due_30;
    $('#stat-overdue').textContent = data.overdue;
  }

  async function loadCustomers() {
    const search = $('#cc-search').value.trim();
    const data = await api(`/api/chronic-care/customers?search=${encodeURIComponent(search)}`);
    customerMap.clear();
    data.customers.forEach(item => customerMap.set(item.id, item));
    $('#customers-body').innerHTML = data.customers.map(customer => `
      <tr>
        <td class="cc-name">${escapeHtml(customer.name)}</td>
        <td dir="ltr">${escapeHtml(customer.phone)}</td>
        <td>${statusBadge(customer.followup_status)}</td>
        <td>${customer.reminder_consent ? '✓ موافق' : 'غير موافق'}</td>
        <td>${formatNumber(customer.medication_count)}</td>
        <td><div class="cc-actions"><button class="whatsapp" data-action="whatsapp-customer" data-id="${escapeHtml(customer.id)}" ${customer.reminder_consent && customer.phone ? '' : 'disabled title="يتطلب رقم هاتف وموافقة العميل"'}>💬 واتساب</button><button data-action="add-medication" data-id="${escapeHtml(customer.id)}">+ دواء</button><button data-action="edit-customer" data-id="${escapeHtml(customer.id)}">تعديل</button></div></td>
      </tr>`).join('') || '<tr><td colspan="6" class="cc-empty">لا توجد ملفات عملاء.</td></tr>';
  }

  async function loadMedications() {
    const params = new URLSearchParams({
      search: $('#cc-search').value.trim(),
      window: $('#cc-window-filter').value,
      status: $('#cc-status-filter').value,
    });
    const data = await api(`/api/chronic-care/medications?${params}`);
    medicationMap.clear();
    data.medications.forEach(item => medicationMap.set(item.id, item));
    $('#medications-body').innerHTML = data.medications.map(medication => `
      <tr>
        <td><span class="cc-name">${escapeHtml(medication.customer_name)}</span><span class="cc-sub" dir="ltr">${escapeHtml(medication.phone)}</span></td>
        <td><span class="cc-name">${escapeHtml(medication.name)}</span><span class="cc-sub">${escapeHtml(medication.strength || 'بدون تركيز مسجل')}</span></td>
        <td>${formatDate(medication.dispensed_at)}${medication.quantity != null ? `<span class="cc-sub">الكمية: ${formatNumber(medication.quantity)} • ${medication.days_supply} يوم</span>` : ''}</td>
        <td>${formatDate(medication.expected_refill_at)}</td>
        <td>${medication.reminder_consent ? formatDate(medication.reminder_at) : '<span class="cc-sub">العميل غير موافق</span>'}</td>
        <td>${statusBadge(medication.status)}</td>
        <td><div class="cc-actions"><button class="whatsapp" data-action="whatsapp-medication" data-id="${escapeHtml(medication.id)}" ${medication.reminder_consent && medication.phone && medication.expected_refill_at ? '' : 'disabled title="يتطلب موعد صرف وموافقة العميل"'}>💬 تذكير واتساب</button><button class="primary" data-action="dispense" data-id="${escapeHtml(medication.id)}">إعادة صرف</button><button data-action="history" data-id="${escapeHtml(medication.id)}">السجل</button><button data-action="edit-medication" data-id="${escapeHtml(medication.id)}">تعديل</button></div></td>
      </tr>`).join('');
    $('#medications-empty').classList.toggle('hidden', data.medications.length > 0);
  }

  async function refreshAll() {
    try { await Promise.all([loadDashboardSummary(), loadCustomers(), loadMedications(), loadMessageTemplates()]); }
    catch (error) { showToast(error.message, true); }
  }

  function openCustomer(customer=null) {
    const form = $('#customer-form');
    form.reset();
    form.elements.id.value = customer?.id || '';
    form.elements.name.value = customer?.name || '';
    form.elements.phone.value = customer?.phone || '';
    form.elements.followup_status.value = customer?.followup_status || 'active';
    form.elements.reminder_consent.checked = Boolean(customer?.reminder_consent);
    $('#customer-dialog-title').textContent = customer ? 'تعديل ملف العميل' : 'إضافة عميل';
    $('#customer-dialog').showModal();
  }

  function openMedication(customerId, medication=null) {
    const form = $('#medication-form');
    form.reset();
    form.elements.id.value = medication?.id || '';
    form.elements.customer_id.value = medication?.customer_id || customerId;
    form.elements.name.value = medication?.name || '';
    form.elements.strength.value = medication?.strength || '';
    form.elements.status.value = medication?.status || 'active';
    $('#medication-dialog-title').textContent = medication ? 'تعديل الدواء' : 'إضافة دواء';
    $('#medication-dialog').showModal();
  }

  function updateCalculation() {
    const form = $('#dispense-form');
    const date = new Date(form.elements.dispensed_at.value);
    const days = Number(form.elements.days_supply.value);
    if (!form.elements.dispensed_at.value || !Number.isInteger(days) || days <= 0) {
      $('#calculated-refill').textContent = '—';
      $('#calculated-reminder').textContent = '—';
      return;
    }
    const refill = new Date(date.getTime() + days * 86400000);
    const reminder = new Date(refill.getTime() - 3 * 86400000);
    $('#calculated-refill').textContent = formatDate(refill.toISOString());
    $('#calculated-reminder').textContent = formatDate(reminder.toISOString());
  }

  function openDispense(medication) {
    const form = $('#dispense-form');
    form.reset();
    form.elements.medication_id.value = medication.id;
    form.elements.quantity.value = medication.quantity || '';
    form.elements.days_supply.value = medication.days_supply || '';
    form.elements.dispensed_at.value = localDateTimeValue(new Date());
    $('#dispense-medication-name').textContent = `${medication.name}${medication.strength ? ` — ${medication.strength}` : ''} • ${medication.customer_name}`;
    updateCalculation();
    $('#dispense-dialog').showModal();
  }

  async function openHistory(medication) {
    $('#history-medication-name').textContent = `${medication.name}${medication.strength ? ` — ${medication.strength}` : ''} • ${medication.customer_name}`;
    $('#history-body').innerHTML = '<tr><td colspan="6">جارِ التحميل...</td></tr>';
    $('#history-dialog').showModal();
    try {
      const data = await api(`/api/chronic-care/medications/${encodeURIComponent(medication.id)}/dispenses`);
      $('#history-body').innerHTML = data.dispenses.map(item => `<tr><td>${formatDate(item.dispensed_at)}</td><td>${formatNumber(item.quantity)}</td><td>${item.days_supply}</td><td>${formatDate(item.expected_refill_at)}</td><td>${formatDate(item.reminder_at)}</td><td>${escapeHtml(item.created_by_name || '—')}</td></tr>`).join('') || '<tr><td colspan="6">لم تسجل عمليات صرف بعد.</td></tr>';
    } catch (error) { showToast(error.message, true); closeDialog($('#history-dialog')); }
  }

  async function submitLocked(form, task) {
    const button = form.querySelector('[type="submit"]');
    if (button.disabled) return;
    button.disabled = true;
    try { await task(); } finally { button.disabled = false; }
  }

  function setupDashboard() {
    setupDialogClosers();
    $('#add-customer-btn').addEventListener('click', () => openCustomer());
    $('#message-templates-btn').addEventListener('click', openMessageTemplates);
    $('#cc-refresh').addEventListener('click', refreshAll);
    $('#cc-window-filter').addEventListener('change', loadMedications);
    $('#cc-status-filter').addEventListener('change', loadMedications);
    $('#cc-search').addEventListener('input', debounce(() => Promise.all([loadCustomers(), loadMedications()]).catch(error => showToast(error.message, true))));
    $('#cc-stats').addEventListener('click', event => {
      const card = event.target.closest('button[data-window]');
      if (!card) return;
      $('#cc-window-filter').value = card.dataset.window || '';
      if (card.dataset.status) $('#cc-status-filter').value = card.dataset.status;
      loadMedications().catch(error => showToast(error.message, true));
    });
    document.addEventListener('click', event => {
      const button = event.target.closest('[data-action]');
      if (!button) return;
      const action = button.dataset.action;
      const id = button.dataset.id;
      if (action === 'edit-customer') openCustomer(customerMap.get(id));
      if (action === 'add-medication') openMedication(id);
      if (action === 'whatsapp-customer') sendCustomerWhatsApp(customerMap.get(id));
      if (action === 'edit-medication') openMedication('', medicationMap.get(id));
      if (action === 'dispense') openDispense(medicationMap.get(id));
      if (action === 'history') openHistory(medicationMap.get(id));
      if (action === 'whatsapp-medication') sendMedicationWhatsApp(medicationMap.get(id));
    });
    $('#dispense-form').elements.days_supply.addEventListener('input', updateCalculation);
    $('#dispense-form').elements.dispensed_at.addEventListener('input', updateCalculation);

    $('#customer-form').addEventListener('submit', event => {
      event.preventDefault();
      submitLocked(event.currentTarget, async () => {
        const form = event.currentTarget;
        const id = form.elements.id.value;
        await api(id ? `/api/chronic-care/customers/${encodeURIComponent(id)}` : '/api/chronic-care/customers', {
          method: id ? 'PUT' : 'POST', body: JSON.stringify({name:form.elements.name.value, phone:form.elements.phone.value, followup_status:form.elements.followup_status.value, reminder_consent:form.elements.reminder_consent.checked})
        });
        closeDialog($('#customer-dialog')); showToast(id ? 'تم تحديث ملف العميل' : 'تم إنشاء ملف العميل'); await refreshAll();
      }).catch(error => showToast(error.message, true));
    });

    $('#medication-form').addEventListener('submit', event => {
      event.preventDefault();
      submitLocked(event.currentTarget, async () => {
        const form = event.currentTarget;
        const id = form.elements.id.value;
        const customerId = form.elements.customer_id.value;
        await api(id ? `/api/chronic-care/medications/${encodeURIComponent(id)}` : `/api/chronic-care/customers/${encodeURIComponent(customerId)}/medications`, {
          method: id ? 'PUT' : 'POST', body: JSON.stringify({name:form.elements.name.value, strength:form.elements.strength.value, status:form.elements.status.value})
        });
        closeDialog($('#medication-dialog')); showToast(id ? 'تم تحديث الدواء' : 'تمت إضافة الدواء'); await refreshAll();
      }).catch(error => showToast(error.message, true));
    });

    $('#dispense-form').addEventListener('submit', event => {
      event.preventDefault();
      submitLocked(event.currentTarget, async () => {
        const form = event.currentTarget;
        const id = form.elements.medication_id.value;
        await api(`/api/chronic-care/medications/${encodeURIComponent(id)}/dispenses`, {method:'POST', body:JSON.stringify({quantity:form.elements.quantity.value, days_supply:form.elements.days_supply.value, dispensed_at:form.elements.dispensed_at.value})});
        closeDialog($('#dispense-dialog')); showToast('تم تسجيل إعادة الصرف وحساب الموعد القادم'); await refreshAll();
      }).catch(error => showToast(error.message, true));
    });
    $('#message-templates-form').addEventListener('submit', event => {
      event.preventDefault();
      submitLocked(event.currentTarget, async () => {
        const form = event.currentTarget;
        const data = await api('/api/chronic-care/message-templates', {
          method:'PUT',
          body:JSON.stringify({general:form.elements.general.value, refill:form.elements.refill.value}),
        });
        messageTemplates = {...messageTemplates, ...data.templates};
        closeDialog($('#message-templates-dialog'));
        showToast('تم حفظ قوالب الرسائل');
      }).catch(error => showToast(error.message, true));
    });
    refreshAll();
  }

  function renderForecasts() {
    const query = $('#forecast-search').value.trim().toLocaleLowerCase('ar');
    const rows = forecastRows.filter(row => `${row.name} ${row.strength}`.toLocaleLowerCase('ar').includes(query));
    $('#forecast-body').innerHTML = rows.map((row, index) => `
      <tr>
        <td><button class="forecast-name" data-forecast-index="${index}">${escapeHtml(row.name)}${row.strength ? `<span class="cc-sub">${escapeHtml(row.strength)}</span>` : ''}</button></td>
        <td class="metric">${row.days_0_7}</td><td class="metric">${row.days_8_14}</td><td class="metric">${row.days_15_30}</td><td class="metric">${row.total_30}</td><td>${row.customer_count}</td><td>${row.refill_operations}</td><td>${formatNumber(row.expected_quantity)}</td>
      </tr>
      <tr class="forecast-details hidden" data-details-index="${index}"><td colspan="8"><div class="forecast-details-box"><table><thead><tr><th>العميل</th><th>الهاتف</th><th>موعد إعادة الصرف</th><th>الكمية المتوقعة</th></tr></thead><tbody>${row.customers.map(customer => `<tr><td>${escapeHtml(customer.customer_name)}</td><td dir="ltr">${escapeHtml(customer.phone)}</td><td>${formatDate(customer.expected_refill_at)}</td><td>${formatNumber(customer.quantity)}</td></tr>`).join('')}</tbody></table></div></td></tr>`).join('');
    $('#forecast-empty').classList.toggle('hidden', rows.length > 0);
  }

  async function loadForecasts() {
    try {
      const data = await api('/api/chronic-care/forecasts');
      forecastRows = data.medications;
      const total = key => forecastRows.reduce((sum, row) => sum + Number(row[key] || 0), 0);
      $('#forecast-7').textContent = total('days_0_7');
      $('#forecast-14').textContent = total('days_0_7') + total('days_8_14');
      $('#forecast-30').textContent = total('total_30');
      const customers = new Set(forecastRows.flatMap(row => row.customers.map(customer => customer.customer_id)));
      $('#forecast-customers').textContent = customers.size;
      renderForecasts();
    } catch (error) { showToast(error.message, true); }
  }

  function setupForecasts() {
    $('#forecast-search').addEventListener('input', renderForecasts);
    $('#forecast-body').addEventListener('click', event => {
      const button = event.target.closest('[data-forecast-index]');
      if (!button) return;
      const details = $(`[data-details-index="${button.dataset.forecastIndex}"]`);
      details?.classList.toggle('hidden');
    });
    loadForecasts();
  }

  if (page === 'dashboard') setupDashboard();
  if (page === 'forecasts') setupForecasts();
})();


