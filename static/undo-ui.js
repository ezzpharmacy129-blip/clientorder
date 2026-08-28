(function(){
  'use strict';
  let lastOrderId = null;
  let installed = false;

  function rememberFromTarget(target){
    const el = target && target.closest ? target.closest('[data-id]') : null;
    if(el && el.dataset.id) lastOrderId = el.dataset.id;
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
      const old = body.querySelector('[data-undo-ui]');
      if(old) old.remove();
      if(!undo || !undo.available) return;

      const box = document.createElement('div');
      box.setAttribute('data-undo-ui','1');
      box.style.cssText='margin:12px 0;padding:10px;border:1px solid #f1d58a;background:#fff9e8;border-radius:10px;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;';
      const text = document.createElement('span');
      text.textContent = 'آخر إجراء قابل للتراجع: ' + (undo.action || 'تغيير');
      text.style.cssText='font-size:12px;font-weight:700;color:#6d5a18;';
      const btn = document.createElement('button');
      btn.type='button';
      btn.className='btn btn-sm btn-warning';
      btn.textContent='↩️ تراجع عن آخر إجراء';
      btn.addEventListener('click', async function(){
        if(!confirm('هل تريد التراجع عن آخر إجراء لهذا الطلب والعودة للحالة السابقة؟')) return;
        btn.disabled=true;
        try{
          const rr = await fetch('/api/orders/' + encodeURIComponent(orderId) + '/undo', {
            method:'POST', headers:{'Content-Type':'application/json'}, credentials:'same-origin', body:'{}'
          });
          let dd={}; try{dd=await rr.json()}catch(e){}
          if(!rr.ok) throw new Error(dd.error || 'تعذر التراجع');
          if(typeof window.toast==='function') window.toast('تم التراجع عن آخر إجراء بنجاح');
          if(typeof window.details==='function') await window.details(orderId);
          setTimeout(function(){refreshUndoButton(orderId)},50);
          if(typeof window.refresh==='function') window.refresh();
        }catch(e){
          btn.disabled=false;
          if(typeof window.toast==='function') window.toast(e.message || 'تعذر التراجع','error');
          else alert(e.message || 'تعذر التراجع');
        }
      });
      box.appendChild(text); box.appendChild(btn);
      body.insertBefore(box, body.firstChild);
    }catch(e){ /* Keep the existing details view usable even if the optional undo UI fails. */ }
  }

  function install(){
    if(installed) return; installed=true;
    document.addEventListener('click', function(e){
      rememberFromTarget(e.target);
      const detailsBtn = e.target.closest && e.target.closest('[data-id]');
      if(detailsBtn && /details|detail|تفاصيل/i.test((detailsBtn.textContent||'').trim())){
        const id=detailsBtn.dataset.id;
        if(id){ lastOrderId=id; setTimeout(function(){refreshUndoButton(id)},120); }
      }
    }, true);

    const modal=document.getElementById('order-modal');
    if(modal){
      new MutationObserver(function(){
        if(lastOrderId) refreshUndoButton(lastOrderId);
      }).observe(modal,{subtree:true,childList:true,attributes:true,attributeFilter:['class']});
    }

    const originalDetails = window.details;
    if(typeof originalDetails === 'function' && !originalDetails.__undoWrapped){
      const wrapped = async function(id){
        lastOrderId=id;
        const result = await originalDetails.apply(this, arguments);
        setTimeout(function(){refreshUndoButton(id)},80);
        return result;
      };
      wrapped.__undoWrapped=true;
      window.details=wrapped;
    }
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',install); else install();
})();
