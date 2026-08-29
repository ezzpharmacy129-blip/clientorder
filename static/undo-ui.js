(function(){
  'use strict';
  let installed = false;
  function addGeneralAvailabilityControls(orderId){
    const body = document.getElementById('modal-body');
    const modal = document.getElementById('order-modal');
    if(!body || !modal || modal.classList.contains('hidden') || !orderId) return;
    const old = body.querySelector('[data-availability-ui]'); if(old) old.remove();
    const box = document.createElement('div'); box.setAttribute('data-availability-ui','1'); box.style.cssText='margin:12px 0;padding:12px;border:1px solid #cfd8e3;background:#f7fafc;border-radius:12px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;';
    const copy = document.createElement('div'); copy.style.cssText='display:flex;flex-direction:column;gap:3px;';
    const title = document.createElement('strong'); title.textContent='حالة توفر الطلب';
    const hint = document.createElement('span'); hint.textContent='يمكن تغيير الحالة في أي اتجاه، للطلبات القديمة والجديدة.'; hint.style.cssText='font-size:12px;color:#667085;'; copy.appendChild(title); copy.appendChild(hint);
    const actions = document.createElement('div'); actions.style.cssText='display:flex;gap:8px;flex-wrap:wrap;';
    const manage = document.createElement('button'); manage.type='button'; manage.className='btn btn-primary btn-sm'; manage.textContent='🔄 إدارة حالة التوفر';
    manage.addEventListener('click', function(){ if(typeof window.openAvailability==='function') window.openAvailability(orderId); else if(typeof window.available==='function') window.available(orderId); });
    actions.appendChild(manage); box.appendChild(copy); box.appendChild(actions); body.insertBefore(box, body.firstChild);
  }
  async function refreshUndoButton(orderId){
    const body=document.getElementById('modal-body'), modal=document.getElementById('order-modal'); if(!body||!modal||modal.classList.contains('hidden')||!orderId)return;
    try{ const r=await fetch('/api/orders/'+encodeURIComponent(orderId),{credentials:'same-origin'}); if(!r.ok)return; const data=await r.json(),undo=data&&data.undo,old=body.querySelector('[data-undo-ui]'); if(old)old.remove(); if(!undo||!undo.available)return;
      const box=document.createElement('div'); box.setAttribute('data-undo-ui','1'); box.style.cssText='margin:12px 0;padding:10px;border:1px solid #f1d58a;background:#fff9e8;border-radius:10px;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;';
      const text=document.createElement('span'); text.textContent='آخر إجراء قابل للتراجع: '+(undo.action||'تغيير'); text.style.cssText='font-size:12px;font-weight:700;color:#6d5a18;';
      const btn=document.createElement('button'); btn.type='button'; btn.className='btn btn-sm btn-warning'; btn.textContent='↩️ تراجع عن آخر إجراء';
      btn.addEventListener('click',async function(){ if(!confirm('هل تريد التراجع عن آخر إجراء لهذا الطلب والعودة للحالة السابقة؟'))return; btn.disabled=true; try{const rr=await fetch('/api/orders/'+encodeURIComponent(orderId)+'/undo',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:'{}'}),dd=await rr.json().catch(()=>({})); if(!rr.ok)throw new Error(dd.error||'تعذر التراجع'); if(typeof window.toast==='function')window.toast('تم التراجع عن آخر إجراء بنجاح'); if(typeof window.details==='function')await window.details(orderId); setTimeout(function(){addGeneralAvailabilityControls(orderId);refreshUndoButton(orderId)},80); if(typeof window.refresh==='function')window.refresh();}catch(e){btn.disabled=false;if(typeof window.toast==='function')window.toast(e.message||'تعذر التراجع','error');else alert(e.message||'تعذر التراجع');} });
      box.appendChild(text); box.appendChild(btn); body.appendChild(box);
    }catch(e){}
  }
  function install(){
    if(installed)return; installed=true; const originalDetails=window.details;
    if(typeof originalDetails==='function'&&!originalDetails.__undoWrapped){ const wrapped=async function(id){const result=await originalDetails.apply(this,arguments);setTimeout(function(){addGeneralAvailabilityControls(id);refreshUndoButton(id)},120);return result;}; wrapped.__undoWrapped=true;window.details=wrapped; }
    else document.addEventListener('click',function(e){const target=e.target.closest&&e.target.closest('.details-btn,.dashboard-detail-btn,[data-id]');if(!target)return;const id=target.dataset.id;if(id&&/تفاصيل|details|detail/i.test(target.textContent||''))setTimeout(function(){addGeneralAvailabilityControls(id);refreshUndoButton(id)},150);},true);
  }

  /* Safe new-order fallback: runs independently after app.js. */
  function phoneForSave(v){let s=String(v||'').trim().replace(/[٠-٩]/g,d=>String('٠١٢٣٤٥٦٧٨٩'.indexOf(d))).replace(/[۰-۹]/g,d=>String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)));if(s.startsWith('+'))return '+'+s.slice(1).replace(/\D/g,'');if(s.startsWith('00'))return '+'+s.slice(2).replace(/\D/g,'');let d=s.replace(/\D/g,'');if(d.startsWith('0')&&d.length===10)return '966'+d.slice(1);if(d.startsWith('5')&&d.length===9)return '966'+d;if(d.startsWith('966'))return d;return d;}
  function installNewOrderSave(){
    const form=document.getElementById('new-order-form'),wrap=document.getElementById('product-items'),add=document.getElementById('add-product-btn'); if(!form||!wrap)return;
    const renumber=()=>{const rows=[...wrap.querySelectorAll('.product-row')];rows.forEach((r,i)=>{const n=r.querySelector('.product-number');if(n)n.textContent=String(i+1)});const c=document.getElementById('products-count'),t=document.getElementById('products-total');if(c)c.textContent=String(rows.length);if(t)t.textContent=String(rows.reduce((n,r)=>n+(parseInt(r.querySelector('.product-qty')?.value)||0),0));};
    const addRow=()=>{const r=document.createElement('div');r.className='product-row';r.innerHTML='<div class="product-number"></div><input class="product-name" type="text" placeholder="اسم المنتج" autocomplete="off"><input class="product-qty" type="number" min="1" value="1"><div class="product-image-cell"><label class="image-upload-btn">📷 صورة المنتج<input class="product-image" type="file" accept="image/jpeg,image/png,image/webp" hidden></label><div class="image-preview"></div></div><button type="button" class="remove-product">✕</button>';r.querySelector('.remove-product').onclick=()=>{r.remove();if(!wrap.querySelector('.product-row'))addRow();renumber()};r.querySelector('.product-qty').oninput=renumber;wrap.appendChild(r);renumber();};
    if(!wrap.querySelector('.product-row'))addRow();else renumber(); if(add&&!add.dataset.ezzBound){add.dataset.ezzBound='1';add.onclick=addRow;} if(form.dataset.ezzBound)return; form.dataset.ezzBound='1';
    form.addEventListener('submit',async function(e){e.preventDefault();e.stopImmediatePropagation();const rows=[...wrap.querySelectorAll('.product-row')];const products=rows.map(r=>({product_name:(r.querySelector('.product-name')?.value||'').trim(),quantity:parseInt(r.querySelector('.product-qty')?.value)||0}));const name=(form.querySelector('[name="customer_name"]')?.value||'').trim();const phone=phoneForSave(form.querySelector('[name="phone"]')?.value||'');const pe=document.querySelector('[data-for="products"]');if(!name||phone.replace(/\D/g,'').length<9||products.some(p=>!p.product_name||p.quantity<1)){if(pe)pe.textContent='أدخل اسم العميل ورقم الجوال واسم المنتج والكمية';return;}if(pe)pe.textContent='';const btn=form.querySelector('button[type="submit"]');if(btn)btn.disabled=true;try{const response=await fetch('/api/orders',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({customer_name:name,phone,products,order_date:form.querySelector('[name="order_date"]')?.value||'',notes:(form.querySelector('[name="notes"]')?.value||'').trim()})});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.error||(data.errors?Object.values(data.errors).join('، '):'تعذر حفظ الطلب'));const success=document.getElementById('new-order-success');if(success)success.textContent='تم حفظ الطلب بنجاح — رقم الطلب: '+data.order.Order_ID;form.reset();wrap.innerHTML='';addRow();if(typeof window.refresh==='function')window.refresh();}catch(err){if(typeof window.toast==='function')window.toast(err.message||'تعذر حفظ الطلب','error');else alert(err.message||'تعذر حفظ الطلب');}finally{if(btn)btn.disabled=false;}},true);
  }
  function installAll(){install();installNewOrderSave();}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',installAll);else installAll();
})();
