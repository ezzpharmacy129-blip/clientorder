(function(){
  'use strict';
  let installed = false;

  function addGeneralAvailabilityControls(orderId){
    const body = document.getElementById('modal-body');
    const modal = document.getElementById('order-modal');
    if(!body || !modal || modal.classList.contains('hidden') || !orderId) return;
    const old = body.querySelector('[data-availability-ui]');
    if(old) old.remove();

    const box = document.createElement('div');
    box.setAttribute('data-availability-ui','1');
    box.style.cssText='margin:12px 0;padding:12px;border:1px solid #cfd8e3;background:#f7fafc;border-radius:12px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;';
    const copy = document.createElement('div');
    copy.style.cssText='display:flex;flex-direction:column;gap:3px;';
    const title = document.createElement('strong'); title.textContent='حالة توفر الطلب';
    const hint = document.createElement('span'); hint.textContent='يمكن تغيير الحالة في أي اتجاه، للطلبات القديمة والجديدة.'; hint.style.cssText='font-size:12px;color:#667085;';
    copy.appendChild(title); copy.appendChild(hint);
    const actions = document.createElement('div'); actions.style.cssText='display:flex;gap:8px;flex-wrap:wrap;';
    const manage = document.createElement('button'); manage.type='button'; manage.className='btn btn-primary btn-sm'; manage.textContent='🔄 إدارة حالة التوفر';
    manage.addEventListener('click', function(){
      if(typeof window.openAvailability === 'function') window.openAvailability(orderId);
      else if(typeof window.available === 'function') window.available(orderId);
    });
    actions.appendChild(manage); box.appendChild(copy); box.appendChild(actions); body.insertBefore(box, body.firstChild);
  }

  async function refreshUndoButton(orderId){
    const body = document.getElementById('modal-body');
    const modal = document.getElementById('order-modal');
    if(!body || !modal || modal.classList.contains('hidden') || !orderId) return;
    try{
      const r = await fetch('/api/orders/' + encodeURIComponent(orderId), {credentials:'same-origin'});
      if(!r.ok) return;
      const data = await r.json();
      const undo = data && data.undo;
      const old = body.querySelector('[data-undo-ui]'); if(old) old.remove();
      if(!undo || !undo.available) return;
      const box = document.createElement('div'); box.setAttribute('data-undo-ui','1');
      box.style.cssText='margin:12px 0;padding:10px;border:1px solid #f1d58a;background:#fff9e8;border-radius:10px;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;';
      const text = document.createElement('span'); text.textContent='آخر إجراء قابل للتراجع: ' + (undo.action || 'تغيير'); text.style.cssText='font-size:12px;font-weight:700;color:#6d5a18;';
      const btn = document.createElement('button'); btn.type='button'; btn.className='btn btn-sm btn-warning'; btn.textContent='↩️ تراجع عن آخر إجراء';
      btn.addEventListener('click', async function(){
        if(!confirm('هل تريد التراجع عن آخر إجراء لهذا الطلب والعودة للحالة السابقة؟')) return;
        btn.disabled=true;
        try{
          const rr = await fetch('/api/orders/' + encodeURIComponent(orderId) + '/undo', {method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:'{}'});
          let dd={}; try{dd=await rr.json()}catch(e){}
          if(!rr.ok) throw new Error(dd.error || 'تعذر التراجع');
          if(typeof window.toast==='function') window.toast('تم التراجع عن آخر إجراء بنجاح');
          if(typeof window.details==='function') await window.details(orderId);
          setTimeout(function(){addGeneralAvailabilityControls(orderId);refreshUndoButton(orderId)},80);
          if(typeof window.refresh==='function') window.refresh();
        }catch(e){btn.disabled=false;if(typeof window.toast==='function')window.toast(e.message||'تعذر التراجع','error');else alert(e.message||'تعذر التراجع')}
      });
      box.appendChild(text); box.appendChild(btn); body.appendChild(box);
    }catch(e){}
  }

  function install(){
    if(installed) return; installed=true;
    const originalDetails = window.details;
    if(typeof originalDetails === 'function' && !originalDetails.__undoWrapped){
      const wrapped = async function(id){
        const result = await originalDetails.apply(this, arguments);
        setTimeout(function(){addGeneralAvailabilityControls(id);refreshUndoButton(id)},120);
        return result;
      };
      wrapped.__undoWrapped=true; window.details=wrapped;
    } else {
      document.addEventListener('click',function(e){
        const target=e.target.closest && e.target.closest('.details-btn,.dashboard-detail-btn,[data-id]');
        if(!target) return;
        const id=target.dataset.id;
        if(id && /تفاصيل|details|detail/i.test(target.textContent||'')) setTimeout(function(){addGeneralAvailabilityControls(id);refreshUndoButton(id)},150);
      },true);
    }
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',install); else install();
})();
