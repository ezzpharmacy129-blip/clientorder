(function(){
  'use strict';
  let installed = false;

  function ensureDetailsModal(){
    let modal = document.getElementById('order-modal');
    if(!modal){
      modal = document.createElement('div');
      modal.id = 'order-modal';
      modal.className = 'modal-overlay hidden';
      modal.setAttribute('aria-hidden','true');
      modal.innerHTML = '<div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="modal-title">'
        + '<div class="modal-header"><h3 id="modal-title">تفاصيل الطلب</h3><button type="button" class="modal-close" id="modal-close-btn" aria-label="إغلاق">×</button></div>'
        + '<div id="modal-body" class="modal-body"></div>'
        + '</div>';
      document.body.appendChild(modal);
    }
    let title = document.getElementById('modal-title');
    if(!title){ title = document.createElement('h3'); title.id='modal-title'; modal.insertBefore(title, modal.firstChild); }
    let body = document.getElementById('modal-body');
    if(!body){ body=document.createElement('div'); body.id='modal-body'; body.className='modal-body'; modal.appendChild(body); }
    let close = document.getElementById('modal-close-btn');
    if(!close){ close=document.createElement('button'); close.type='button'; close.id='modal-close-btn'; close.className='modal-close'; close.textContent='×'; modal.querySelector('.modal-header')?.appendChild(close); }
    if(!close.dataset.ezzBound){
      close.dataset.ezzBound='1';
      close.addEventListener('click',()=>{modal.classList.add('hidden');modal.setAttribute('aria-hidden','true')});
      modal.addEventListener('click',e=>{if(e.target===modal){modal.classList.add('hidden');modal.setAttribute('aria-hidden','true')}});
    }
    return modal;
  }

  function ensureActionModals(){
    if(!document.getElementById('confirm-modal')){
      const x=document.createElement('div');x.id='confirm-modal';x.className='modal-overlay hidden';x.innerHTML='<div class="modal-card" role="dialog" aria-modal="true"><div class="modal-header"><h3>تأكيد</h3></div><div id="confirm-message" class="modal-body"></div><div class="modal-actions"><button type="button" class="btn btn-secondary" id="confirm-no-btn">إلغاء</button><button type="button" class="btn btn-danger" id="confirm-yes-btn">تأكيد</button></div></div>';document.body.appendChild(x);
    }
    if(!document.getElementById('postpone-modal')){
      const x=document.createElement('div');x.id='postpone-modal';x.className='modal-overlay hidden';x.innerHTML='<div class="modal-card" role="dialog" aria-modal="true"><div class="modal-header"><h3>تأجيل المتابعة</h3></div><div class="modal-body"><input type="date" id="postpone-custom-date"></div><div class="modal-actions"><button type="button" class="btn btn-secondary" id="postpone-close-btn">إلغاء</button><button type="button" class="btn btn-primary" id="postpone-custom-confirm">حفظ</button></div></div>';document.body.appendChild(x);
    }
    if(!document.getElementById('availability-modal')){
      const x=document.createElement('div');x.id='availability-modal';x.className='modal-overlay hidden';x.setAttribute('aria-hidden','true');x.innerHTML='<div class="modal-card" role="dialog" aria-modal="true"><div class="modal-header"><h3>تحديث توفر المنتجات</h3><button type="button" class="modal-close" id="availability-close-btn">×</button></div><div id="availability-items" class="modal-body"></div><div class="modal-actions"><button type="button" class="btn btn-secondary" id="availability-cancel-btn">إلغاء</button><button type="button" class="btn btn-primary" id="availability-save-btn">حفظ</button></div></div>';document.body.appendChild(x);
    }
  }

  function escSafe(s){return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
  function fmtSafe(s){if(!s)return '—';const p=String(s).split(' ')[0].split('-');return p.length===3?`${p[2]}/${p[1]}/${p[0]}`:String(s)}
  function phoneSafe(p){const s=String(p||'').replace(/\D/g,'');return s}

  async function directDetails(id){
    if(!id) return;
    const modal=ensureDetailsModal();
    ensureActionModals();
    const title=document.getElementById('modal-title');
    const body=document.getElementById('modal-body');
    title.textContent='تفاصيل الطلب '+id;
    body.innerHTML='<div class="empty-state">جارِ تحميل تفاصيل الطلب...</div>';
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden','false');
    try{
      const r=await fetch('/api/orders/'+encodeURIComponent(id),{credentials:'same-origin',cache:'no-store'});
      const d=await r.json().catch(()=>({}));
      if(!r.ok) throw new Error(d.error||'تعذر تحميل تفاصيل الطلب');
      const o=d.order||{};
      const items=Array.isArray(o.Items)?o.Items:[];
      const activity=Array.isArray(d.activity_log)?d.activity_log:[];
      const undo=d.undo&&d.undo.available?d.undo:null;
      const products=items.length?items.map(i=>'<div class="item-detail-row"><div><strong>'+escSafe(i.Product_Name)+'</strong> × '+escSafe(i.Quantity)+(i.Image_Path?' 📷':'')+'</div><div>'+(i.Available_Price?escSafe(i.Available_Price)+' ريال':'')+'</div></div>').join(''):'<div class="empty-state">لا توجد منتجات</div>';
      const log=activity.length?activity.map(a=>'<div class="activity-item"><b>'+escSafe(a.Created_At)+'</b><span>'+escSafe(a.Action)+(a.Note?' — '+escSafe(a.Note):'')+'</span></div>').join(''):'<div class="empty-state">لا يوجد سجل متابعة</div>';
      const waBtn=o.Phone?'<button type="button" class="btn btn-outline btn-sm" id="direct-detail-wa">💬 رسالة واتساب</button>':'';
      const availBtn=['بانتظار التوفر','متوفر - يحتاج اتصال','متوفر جزئيًا - يحتاج اتصال'].includes(o.Status)?'<button type="button" class="btn btn-primary" id="direct-detail-availability">تحديث توفر المنتجات</button>':'';
      const contactBtn=['متوفر - يحتاج اتصال','متوفر جزئيًا - يحتاج اتصال','تم التواصل - بانتظار الاستلام'].includes(o.Status)?'<button type="button" class="btn btn-primary" id="direct-detail-contact">تم التواصل</button>':'';
      const pickupBtn=['متوفر - يحتاج اتصال','متوفر جزئيًا - يحتاج اتصال','تم التواصل - بانتظار الاستلام','لم يستلم'].includes(o.Status)?'<button type="button" class="btn btn-primary" id="direct-detail-pickup">تم الاستلام</button>':'';
      const cancelBtn=!['تم الاستلام','ملغي'].includes(o.Status)?'<button type="button" class="btn btn-danger" id="direct-detail-cancel">إلغاء الطلب</button>':'';
      const undoBtn=undo?'<button type="button" class="btn btn-warning" id="direct-detail-undo">↩ التراجع</button>':'';
      body.innerHTML='<div class="order-head"><div><b>'+escSafe(o.Customer_Name)+'</b><div>'+escSafe(o.Phone)+'</div></div><div class="detail-actions-inline">'+waBtn+'</div></div>'
        +'<div class="detail-grid">'
        +'<div class="detail-item full"><div class="di-label">المنتجات</div><div class="items-detail">'+products+'</div></div>'
        +'<div class="detail-item"><div class="di-label">الحالة</div><div class="di-value">'+escSafe(o.Status||'—')+'</div></div>'
        +'<div class="detail-item"><div class="di-label">تاريخ الطلب</div><div class="di-value">'+fmtSafe(o.Order_Date)+'</div></div>'
        +'<div class="detail-item"><div class="di-label">تاريخ التوفر</div><div class="di-value">'+fmtSafe(o.Available_Date)+'</div></div>'
        +'<div class="detail-item"><div class="di-label">آخر تواصل</div><div class="di-value">'+fmtSafe(o.Last_Contact_Date)+'</div></div>'
        +'<div class="detail-item"><div class="di-label">موعد المتابعة</div><div class="di-value">'+fmtSafe(o.Next_Followup_Date)+'</div></div>'
        +'<div class="detail-item"><div class="di-label">تاريخ الاستلام</div><div class="di-value">'+fmtSafe(o.Pickup_Date)+'</div></div>'
        +(o.Notes?'<div class="detail-item full"><div class="di-label">ملاحظات</div><div class="di-value">'+escSafe(o.Notes)+'</div></div>':'')
        +'</div><div class="contact-status-panel"><div class="di-label">حالة التواصل: '+escSafe(o.Contact_Status||'لم يتم التواصل')+'</div></div>'
        +'<div class="detail-actions">'+availBtn+contactBtn+pickupBtn+cancelBtn+undoBtn+'</div>'
        +'<div class="activity-log"><h4>سجل المتابعة</h4>'+log+'</div>';
      document.getElementById('direct-detail-wa')?.addEventListener('click',()=>{if(typeof window.openClientWhatsApp==='function')window.openClientWhatsApp(id)});
      document.getElementById('direct-detail-availability')?.addEventListener('click',()=>{if(typeof window.openAvailability==='function')window.openAvailability(id)});
      document.getElementById('direct-detail-contact')?.addEventListener('click',()=>{if(typeof window.contact==='function')window.contact(id)});
      document.getElementById('direct-detail-pickup')?.addEventListener('click',()=>{if(typeof window.pickup==='function')window.pickup(id)});
      document.getElementById('direct-detail-cancel')?.addEventListener('click',()=>{if(typeof window.cancelOrder==='function')window.cancelOrder(id)});
      document.getElementById('direct-detail-undo')?.addEventListener('click',()=>{if(typeof window.undoOrder==='function')window.undoOrder(id,undo.action||'آخر إجراء')});
    }catch(e){body.innerHTML='<div class="empty-state">تعذر تحميل تفاصيل الطلب: '+escSafe(e.message)+'</div>';}
  }

  function installDetailRouting(){
    ensureDetailsModal();
    ensureActionModals();
    window.details=directDetails;
    document.addEventListener('click',function(e){
      const target=e.target.closest&&e.target.closest('.details-btn,.dashboard-detail-btn,.act-details');
      if(!target)return;
      const id=target.dataset.id;
      if(!id)return;
      e.preventDefault();
      e.stopPropagation();
      directDetails(id);
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
      btn.addEventListener('click',async function(){ if(!confirm('هل تريد التراجع عن آخر إجراء لهذا الطلب والعودة للحالة السابقة؟'))return; btn.disabled=true; try{const rr=await fetch('/api/orders/'+encodeURIComponent(orderId)+'/undo',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:'{}'}),dd=await rr.json().catch(()=>({})); if(!rr.ok)throw new Error(dd.error||'تعذر التراجع'); if(typeof window.toast==='function')window.toast('تم التراجع عن آخر إجراء بنجاح'); await window.details(orderId); if(typeof window.refresh==='function')window.refresh();}catch(e){btn.disabled=false;if(typeof window.toast==='function')window.toast(e.message||'تعذر التراجع','error');else alert(e.message||'تعذر التراجع');} });
      box.appendChild(text); box.appendChild(btn); body.appendChild(box);
    }catch(e){}
  }

  function phoneForSave(v){let s=String(v||'').trim().replace(/[٠-٩]/g,d=>String('٠١٢٣٤٥٦٧٨٩'.indexOf(d))).replace(/[۰-۹]/g,d=>String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)));if(s.startsWith('+'))return '+'+s.slice(1).replace(/\D/g,'');if(s.startsWith('00'))return '+'+s.slice(2).replace(/\D/g,'');let d=s.replace(/\D/g,'');if(d.startsWith('0')&&d.length===10)return '966'+d.slice(1);if(d.startsWith('5')&&d.length===9)return '966'+d;if(d.startsWith('966'))return d;return d;}
  function installNewOrderSave(){
    const form=document.getElementById('new-order-form'),wrap=document.getElementById('product-items'),add=document.getElementById('add-product-btn'); if(!form||!wrap)return;
    const renumber=()=>{const rows=[...wrap.querySelectorAll('.product-row')];rows.forEach((r,i)=>{const n=r.querySelector('.product-number');if(n)n.textContent=String(i+1)});const c=document.getElementById('products-count'),t=document.getElementById('products-total');if(c)c.textContent=String(rows.length);if(t)t.textContent=String(rows.reduce((n,r)=>n+(parseInt(r.querySelector('.product-qty')?.value)||0),0));};
    if(!wrap.querySelector('.product-row') && typeof add==='object'){}
    if(!add.dataset.ezzBoundNew){ add.dataset.ezzBoundNew='1'; }
  }

  function install(){
    if(installed)return; installed=true;
    installDetailRouting();
    installNewOrderSave();
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();
