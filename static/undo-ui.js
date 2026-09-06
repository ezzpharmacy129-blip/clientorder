(function(){
  'use strict';
  let installed = false;

  function forceModalStyles(modal){
    if(!modal) return;
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden','false');
    modal.style.display='flex';
    modal.style.visibility='visible';
    modal.style.opacity='1';
    modal.style.pointerEvents='auto';
    modal.style.position='fixed';
    modal.style.inset='0';
    modal.style.zIndex='1000';
    const card=modal.querySelector('.modal');
    if(card){
      card.style.display='block';
      card.style.visibility='visible';
      card.style.opacity='1';
      card.style.background='#fff';
      card.style.color='var(--text,#17324d)';
      card.style.width='min(780px,100%)';
      card.style.maxHeight='90vh';
      card.style.overflow='auto';
      card.style.borderRadius='16px';
      card.style.boxShadow='0 20px 70px rgba(0,0,0,.2)';
    }
  }

  function hideModal(modal){
    if(!modal) return;
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden','true');
    modal.style.display='none';
    modal.style.visibility='hidden';
    modal.style.opacity='0';
    modal.style.pointerEvents='none';
  }

  function ensureDetailsModal(){
    let modal = document.getElementById('order-modal');
    if(!modal){
      modal=document.createElement('div');
      modal.id='order-modal';
      modal.className='modal-overlay hidden';
      modal.setAttribute('aria-hidden','true');
      modal.innerHTML='<div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div class="modal-header"><h3 id="modal-title">تفاصيل الطلب</h3><button type="button" class="modal-close" id="modal-close-btn" aria-label="إغلاق">×</button></div><div id="modal-body" class="modal-body"></div></div>';
      document.body.appendChild(modal);
    }else{
      let card=modal.querySelector('.modal');
      if(!card){
        const old=modal.querySelector('.modal-card');
        if(old){old.classList.remove('modal-card');old.classList.add('modal');card=old;}
      }
      if(!card){
        card=document.createElement('div');
        card.className='modal';
        card.setAttribute('role','dialog');
        card.setAttribute('aria-modal','true');
        card.setAttribute('aria-labelledby','modal-title');
        modal.appendChild(card);
      }
      if(!card.querySelector('#modal-title')){
        const header=card.querySelector('.modal-header')||document.createElement('div');
        if(!header.classList.contains('modal-header')){header.className='modal-header';card.insertBefore(header,card.firstChild);}
        const h=document.createElement('h3');h.id='modal-title';h.textContent='تفاصيل الطلب';header.prepend(h);
      }
      if(!card.querySelector('#modal-body')){
        const b=document.createElement('div');b.id='modal-body';b.className='modal-body';card.appendChild(b);
      }
    }
    const close=document.getElementById('modal-close-btn');
    if(close&&!close.dataset.ezzBound){
      close.dataset.ezzBound='1';
      close.addEventListener('click',()=>hideModal(modal));
      modal.addEventListener('click',e=>{if(e.target===modal)hideModal(modal)});
    }
    return modal;
  }

  function ensureActionModals(){
    if(!document.getElementById('availability-modal')){
      const x=document.createElement('div');x.id='availability-modal';x.className='modal-overlay hidden';x.setAttribute('aria-hidden','true');x.innerHTML='<div class="modal" role="dialog" aria-modal="true"><div class="modal-header"><h3>تحديث توفر المنتجات</h3><button type="button" class="modal-close" id="availability-close-btn">×</button></div><div id="availability-items" class="modal-body"></div><div class="modal-actions"><button type="button" class="btn btn-secondary" id="availability-cancel-btn">إلغاء</button><button type="button" class="btn btn-primary" id="availability-save-btn">حفظ</button></div></div>';document.body.appendChild(x);
    }
    if(!document.getElementById('confirm-modal')){
      const x=document.createElement('div');x.id='confirm-modal';x.className='modal-overlay hidden';x.innerHTML='<div class="modal" role="dialog" aria-modal="true"><div class="modal-header"><h3>تأكيد</h3></div><div id="confirm-message" class="modal-body"></div><div class="modal-actions"><button type="button" class="btn btn-secondary" id="confirm-no-btn">إلغاء</button><button type="button" class="btn btn-danger" id="confirm-yes-btn">تأكيد</button></div></div>';document.body.appendChild(x);
    }
    if(!document.getElementById('postpone-modal')){
      const x=document.createElement('div');x.id='postpone-modal';x.className='modal-overlay hidden';x.innerHTML='<div class="modal" role="dialog" aria-modal="true"><div class="modal-header"><h3>تأجيل المتابعة</h3></div><div class="modal-body"><input type="date" id="postpone-custom-date"></div><div class="modal-actions"><button type="button" class="btn btn-secondary" id="postpone-close-btn">إلغاء</button><button type="button" class="btn btn-primary" id="postpone-custom-confirm">حفظ</button></div></div>';document.body.appendChild(x);
    }
  }

  async function directDetails(id){
    if(!id)return;
    const modal=ensureDetailsModal();
    ensureActionModals();
    const title=document.getElementById('modal-title'),body=document.getElementById('modal-body');
    if(!title||!body)return;
    title.textContent='تفاصيل الطلب '+id;
    body.innerHTML='<div class="empty-state">جارِ تحميل تفاصيل الطلب...</div>';
    forceModalStyles(modal);
    try{
      const d=await window.apiFetch('/api/orders/'+encodeURIComponent(id),{cache:'no-store'});
      const o=d.order||{}, items=Array.isArray(o.Items)?o.Items:[], log=Array.isArray(d.activity_log)?d.activity_log:[], undo=d.undo?.available?d.undo:null;
      const esc=s=>String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\"/g,'&quot;');
      const fmt=s=>{if(!s)return '—';const p=String(s).split(' ')[0].split('-');return p.length===3?`${p[2]}/${p[1]}/${p[0]}`:String(s)};
      const products=items.length?items.map(i=>`<div class="item-detail-row"><div><strong>${esc(i.Product_Name)}</strong> × ${esc(i.Quantity)}${i.Image_Path?' 📷':''}</div><div>${i.Available_Price?esc(i.Available_Price)+' ريال':''}</div></div>`).join(''):'<div class="empty-state">لا توجد منتجات</div>';
      const activity=log.length?log.map(a=>`<div class="activity-item"><b>${esc(a.Created_At)}</b><span>${esc(a.Action)}${a.Note?` — ${esc(a.Note)}`:''}</span></div>`).join(''):'<div class="empty-state">لا يوجد سجل متابعة</div>';
      const actions=[];
      if(['بانتظار التوفر','متوفر - يحتاج اتصال','متوفر جزئيًا - يحتاج اتصال'].includes(o.Status))actions.push('<button type="button" class="btn btn-primary" id="direct-availability">تحديث توفر المنتجات</button>');
      if(['متوفر - يحتاج اتصال','متوفر جزئيًا - يحتاج اتصال','تم التواصل - بانتظار الاستلام'].includes(o.Status))actions.push('<button type="button" class="btn btn-primary" id="direct-contact">تم التواصل</button>');
      if(['متوفر - يحتاج اتصال','متوفر جزئيًا - يحتاج اتصال','تم التواصل - بانتظار الاستلام','لم يستلم'].includes(o.Status))actions.push('<button type="button" class="btn btn-primary" id="direct-pickup">تم الاستلام</button>');
      if(!['تم الاستلام','ملغي'].includes(o.Status))actions.push('<button type="button" class="btn btn-danger" id="direct-cancel">إلغاء الطلب</button>');
      if(undo)actions.push(`<button type="button" class="btn btn-warning" id="direct-undo">↩ التراجع عن: ${esc(undo.action||'آخر إجراء')}</button>`);
      if(o.Phone)actions.unshift('<button type="button" class="btn btn-outline btn-sm" id="direct-wa">💬 واتساب</button>');
      body.innerHTML=`<div class="order-head"><div><b>${esc(o.Customer_Name)}</b><div>${esc(o.Phone)}</div></div></div><div class="detail-grid"><div class="detail-item full"><div class="di-label">المنتجات</div><div class="items-detail">${products}</div></div><div class="detail-item"><div class="di-label">الحالة</div><div class="di-value">${esc(o.Status||'—')}</div></div><div class="detail-item"><div class="di-label">تاريخ الطلب</div><div class="di-value">${fmt(o.Order_Date)}</div></div><div class="detail-item"><div class="di-label">تاريخ التوفر</div><div class="di-value">${fmt(o.Available_Date)}</div></div><div class="detail-item"><div class="di-label">آخر تواصل</div><div class="di-value">${fmt(o.Last_Contact_Date)}</div></div><div class="detail-item"><div class="di-label">موعد المتابعة</div><div class="di-value">${fmt(o.Next_Followup_Date)}</div></div><div class="detail-item"><div class="di-label">تاريخ الاستلام</div><div class="di-value">${fmt(o.Pickup_Date)}</div></div>${o.Notes?`<div class="detail-item full"><div class="di-label">ملاحظات</div><div class="di-value">${esc(o.Notes)}</div></div>`:''}</div><div class="contact-status-panel"><div class="di-label">حالة التواصل</div><div class="di-value">${esc(o.Contact_Status||'لم يتم التواصل')}</div></div><div class="detail-actions">${actions.join('')}</div><div class="activity-log"><h4>سجل المتابعة</h4>${activity}</div>`;
      forceModalStyles(modal);
      document.getElementById('direct-wa')?.addEventListener('click',()=>window.openClientWhatsApp?.(id));
      document.getElementById('direct-availability')?.addEventListener('click',()=>window.openAvailability?.(id));
      document.getElementById('direct-contact')?.addEventListener('click',()=>window.contact?.(id));
      document.getElementById('direct-pickup')?.addEventListener('click',()=>window.pickup?.(id));
      document.getElementById('direct-cancel')?.addEventListener('click',()=>window.cancelOrder?.(id));
      document.getElementById('direct-undo')?.addEventListener('click',()=>window.undoOrder?.(id,undo.action||'آخر إجراء'));
    }catch(e){body.innerHTML=`<div class="empty-state">تعذر تحميل تفاصيل الطلب: ${String(e.message||'خطأ')}</div>`;forceModalStyles(modal);}
  }

  function installDetailRouting(){
    ensureDetailsModal();ensureActionModals();
    window.details=directDetails;
    document.addEventListener('click',e=>{
      const target=e.target.closest&&e.target.closest('.details-btn,.dashboard-detail-btn,.act-details');
      if(!target)return;
      const id=target.dataset.id;if(!id)return;
      e.preventDefault();e.stopPropagation();directDetails(id);
    },true);
  }

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
    manage.addEventListener('click', function(){ if(typeof window.openAvailability==='function') window.openAvailability(orderId); });
    actions.appendChild(manage); box.appendChild(copy); box.appendChild(actions); body.insertBefore(box, body.firstChild);
  }
  async function refreshUndoButton(orderId){
    const body=document.getElementById('modal-body'), modal=document.getElementById('order-modal'); if(!body||!modal||modal.classList.contains('hidden')||!orderId)return;
    try{ const r=await fetch('/api/orders/'+encodeURIComponent(orderId),{credentials:'same-origin'}); if(!r.ok)return; const data=await r.json(),undo=data&&data.undo,old=body.querySelector('[data-undo-ui]'); if(old)old.remove(); if(!undo||!undo.available)return;
      const box=document.createElement('div'); box.setAttribute('data-undo-ui','1'); box.style.cssText='margin:12px 0;padding:10px;border:1px solid #f1d58a;background:#fff9e8;border-radius:10px;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;';
      const text=document.createElement('span'); text.textContent='آخر إجراء قابل للتراجع: '+(undo.action||'تغيير'); text.style.cssText='font-size:12px;font-weight:700;color:#6d5a18;';
      const btn=document.createElement('button'); btn.type='button'; btn.className='btn btn-sm btn-warning'; btn.textContent='↩️ تراجع عن آخر إجراء';
      btn.addEventListener('click',async function(){ if(!confirm('هل تريد التراجع عن آخر إجراء لهذا الطلب والعودة للحالة السابقة؟'))return; btn.disabled=true; try{const dd=await window.apiFetch('/api/orders/'+encodeURIComponent(orderId)+'/undo',{method:'POST',body:'{}'}); if(typeof window.toast==='function')window.toast('تم التراجع عن آخر إجراء بنجاح'); await window.details(orderId); if(typeof window.refresh==='function')window.refresh();}catch(e){btn.disabled=false;if(typeof window.toast==='function')window.toast(e.message||'تعذر التراجع','error');else alert(e.message||'تعذر التراجع');} });
      box.appendChild(text); box.appendChild(btn); body.appendChild(box);
    }catch(e){}
  }

  function phoneForSave(v){let s=String(v||'').trim().replace(/[٠-٩]/g,d=>String('٠١٢٣٤٥٦٧٨٩'.indexOf(d))).replace(/[۰-۹]/g,d=>String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)));if(s.startsWith('+'))return '+'+s.slice(1).replace(/\D/g,'');if(s.startsWith('00'))return '+'+s.slice(2).replace(/\D/g,'');let d=s.replace(/\D/g,'');if(d.startsWith('0')&&d.length===10)return '966'+d.slice(1);if(d.startsWith('5')&&d.length===9)return '966'+d;if(d.startsWith('966'))return d;return d;}
  function installNewOrderSave(){
    const form=document.getElementById('new-order-form'),wrap=document.getElementById('product-items'),add=document.getElementById('add-product-btn'); if(!form||!wrap)return;
    const renumber=()=>{const rows=[...wrap.querySelectorAll('.product-row')];rows.forEach((r,i)=>{const n=r.querySelector('.product-number');if(n)n.textContent=String(i+1)});const c=document.getElementById('products-count'),t=document.getElementById('products-total');if(c)c.textContent=String(rows.length);if(t)t.textContent=String(rows.reduce((n,r)=>n+(parseInt(r.querySelector('.product-qty')?.value)||0),0));};
    const addRow=()=>{const r=document.createElement('div');r.className='product-row';r.innerHTML='<div class="product-number"></div><input class="product-name" type="text" placeholder="اسم المنتج" autocomplete="off"><input class="product-qty" type="number" min="1" value="1"><div class="product-image-cell"><label class="image-upload-btn">📷 صورة المنتج<input class="product-image" type="file" accept="image/jpeg,image/png,image/webp" hidden></label><div class="image-preview"></div></div><button type="button" class="remove-product">✕</button>';r.querySelector('.remove-product').onclick=()=>{r.remove();if(!wrap.querySelector('.product-row'))addRow();renumber()};r.querySelector('.product-qty').oninput=renumber;wrap.appendChild(r);renumber();};
    if(!wrap.querySelector('.product-row'))addRow();else renumber(); if(add&&!add.dataset.ezzBound){add.dataset.ezzBound='1';add.onclick=addRow;} if(form.dataset.ezzBound)return; form.dataset.ezzBound='1';
    form.addEventListener('submit',async function(e){e.preventDefault();e.stopImmediatePropagation();const rows=[...wrap.querySelectorAll('.product-row')];const products=rows.map(r=>({product_name:(r.querySelector('.product-name')?.value||'').trim(),quantity:parseInt(r.querySelector('.product-qty')?.value)||0}));const name=(form.querySelector('[name="customer_name"]')?.value||'').trim();const phone=phoneForSave(form.querySelector('[name="phone"]')?.value||'');const pe=document.querySelector('[data-for="products"]');if(!name||phone.replace(/\D/g,'').length<9||products.some(p=>!p.product_name||p.quantity<1)){if(pe)pe.textContent='أدخل اسم العميل ورقم الجوال واسم المنتج والكمية';return;}if(pe)pe.textContent='';const btn=form.querySelector('button[type="submit"]');if(btn)btn.disabled=true;try{const response=await fetch('/api/orders',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({customer_name:name,phone,products,order_date:form.querySelector('[name="order_date"]')?.value||'',notes:(form.querySelector('[name="notes"]')?.value||'').trim()})});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.error||(data.errors?Object.values(data.errors).join('، '):'تعذر حفظ الطلب'));const success=document.getElementById('new-order-success');if(success)success.textContent='تم حفظ الطلب بنجاح — رقم الطلب: '+data.order.Order_ID;form.reset();wrap.innerHTML='';addRow();if(typeof window.refresh==='function')window.refresh();}catch(err){if(typeof window.toast==='function')window.toast(err.message||'تعذر حفظ الطلب','error');else alert(err.message||'تعذر حفظ الطلب');}finally{if(btn)btn.disabled=false;}},true);
  }

  function install(){if(installed)return;installed=true;installDetailRouting();installNewOrderSave();}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();
