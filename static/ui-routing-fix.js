/* EZZ UI ROUTING FIX v1
   Guarantees the order-details and availability modals exist and remain usable.
*/
(function(){
  function q(id){return document.getElementById(id)}
  function escv(v){return typeof window.esc==='function'?window.esc(v):String(v??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
  function toast(msg,type){if(typeof window.toast==='function') window.toast(msg,type||'success')}
  function api(url,opts){
    const o=Object.assign({},opts||{}); o.headers=Object.assign({},o.headers||{});
    if(!(o.body instanceof FormData)) o.headers['Content-Type']='application/json';
    return fetch(url,o).then(async r=>{let d=null;try{d=await r.json()}catch(_){ } if(!r.ok){const e=new Error(d?.error||(d?.errors?Object.values(d.errors).join('، '):'حدث خطأ'));e.status=r.status;e.data=d;throw e}return d})
  }
  function ensureStyles(){
    if(q('ezz-routing-styles')) return;
    const s=document.createElement('style');s.id='ezz-routing-styles';s.textContent=`
      .ezz-modal-overlay{position:fixed;inset:0;background:rgba(8,25,40,.48);display:flex;align-items:center;justify-content:center;padding:16px;z-index:9999}
      .ezz-modal-overlay.hidden{display:none!important}.ezz-modal{width:min(960px,96vw);max-height:92vh;overflow:auto;background:#fff;border-radius:18px;box-shadow:0 20px 80px rgba(0,0,0,.22);padding:20px;direction:rtl}
      .ezz-modal-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}.ezz-modal-title{font-size:20px;font-weight:800}.ezz-close{border:0;background:#eef3f6;border-radius:10px;padding:8px 12px;cursor:pointer}
      .ezz-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.ezz-box{border:1px solid #dfe7ec;border-radius:12px;padding:12px}.ezz-box.full{grid-column:1/-1}.ezz-label{font-size:12px;color:#71808f;margin-bottom:5px}.ezz-value{font-weight:700}
      .ezz-items{display:grid;gap:10px}.ezz-item{border:1px solid #e0e7eb;border-radius:12px;padding:12px}.ezz-item-head{display:flex;justify-content:space-between;gap:8px;align-items:center}.ezz-item-row{display:grid;grid-template-columns:1fr 190px;gap:10px;align-items:start}.ezz-item select,.ezz-item input{width:100%;box-sizing:border-box;padding:9px;border:1px solid #ccd8df;border-radius:9px;background:#fff}.ezz-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}.ezz-log{margin-top:16px;border-top:1px solid #e6ecef;padding-top:12px}.ezz-log-row{padding:8px 0;border-bottom:1px solid #edf1f3;font-size:13px}.ezz-note{color:#6e7d89;font-size:13px}
      @media(max-width:700px){.ezz-grid{grid-template-columns:1fr}.ezz-item-row{grid-template-columns:1fr}}
    `;document.head.appendChild(s)
  }
  function ensureModal(id,title){
    if(q(id)) return q(id)
    const wrap=document.createElement('div');wrap.id=id;wrap.className='ezz-modal-overlay hidden';wrap.setAttribute('aria-hidden','true');wrap.innerHTML=`<div class="ezz-modal"><div class="ezz-modal-head"><div class="ezz-modal-title">${title}</div><button type="button" class="ezz-close">إغلاق ✕</button></div><div class="ezz-modal-body"></div></div>`;
    document.body.appendChild(wrap);wrap.querySelector('.ezz-close').onclick=()=>{wrap.classList.add('hidden');wrap.setAttribute('aria-hidden','true')};wrap.addEventListener('click',e=>{if(e.target===wrap){wrap.classList.add('hidden');wrap.setAttribute('aria-hidden','true')}});return wrap
  }
  function ensureAll(){ensureStyles();ensureModal('order-modal','تفاصيل الطلب');ensureModal('availability-modal','تحديث توفر المنتجات');ensureModal('confirm-modal','تأكيد العملية');ensureModal('postpone-modal','تأجيل المتابعة')}
  function show(el){el.classList.remove('hidden');el.setAttribute('aria-hidden','false')}
  function hide(el){el.classList.add('hidden');el.setAttribute('aria-hidden','true')}
  function orderBadge(s){return typeof window.badge==='function'?window.badge(s):`<span>${escv(s)}</span>`}
  function contactBadge(s){return typeof window.contactBadge==='function'?window.contactBadge(s):`<span>${escv(s||'لم يتم التواصل')}</span>`}
  async function detailsFixed(id){
    ensureAll();
    const m=q('order-modal');const body=m.querySelector('.ezz-modal-body');body.innerHTML='<div class="ezz-note">جارٍ تحميل تفاصيل الطلب…</div>';show(m);
    try{
      const d=await api(`/api/orders/${encodeURIComponent(id)}`);const o=d.order||{};
      m.querySelector('.ezz-modal-title').textContent=`تفاصيل الطلب ${o.Order_ID||id}`;
      body.innerHTML=`<div class="ezz-grid">
        <div class="ezz-box"><div class="ezz-label">العميل</div><div class="ezz-value">${escv(o.Customer_Name)}</div><div>${escv(o.Phone)}</div></div>
        <div class="ezz-box"><div class="ezz-label">الحالة</div><div class="ezz-value">${orderBadge(o.Status)}</div><div style="margin-top:6px">${contactBadge(o.Contact_Status)}</div></div>
        <div class="ezz-box full"><div class="ezz-label">المنتجات</div><div class="ezz-items">${(o.Items||[]).map(i=>`<div class="ezz-item"><div class="ezz-item-head"><b>${escv(i.Product_Name)}</b><span>× ${escv(i.Quantity||1)}</span></div>${i.Available_Price?`<div class="ezz-note">السعر: ${escv(i.Available_Price)} ريال${i.Discounted_Price?` — بعد الخصم ${escv(i.Discounted_Price)} ريال`:''}</div>`:''}${i.Unavailable_Reason?`<div class="ezz-note">سبب عدم التوفر: ${escv(i.Unavailable_Reason)}</div>`:''}${i.Image_Path?`<div class="ezz-note">📷 توجد صورة مرفقة</div>`:''}</div>`).join('')||'<div class="ezz-note">لا توجد منتجات.</div>'}</div></div>
        <div class="ezz-box"><div class="ezz-label">تاريخ الطلب</div><div class="ezz-value">${escv(o.Order_Date||'—')}</div></div>
        <div class="ezz-box"><div class="ezz-label">تاريخ التوفر</div><div class="ezz-value">${escv(o.Available_Date||'—')}</div></div>
        <div class="ezz-box"><div class="ezz-label">آخر تواصل</div><div class="ezz-value">${escv(o.Last_Contact_Date||'—')}</div></div>
        <div class="ezz-box"><div class="ezz-label">المتابعة القادمة</div><div class="ezz-value">${escv(o.Next_Followup_Date||'—')}</div></div>
        ${o.Notes?`<div class="ezz-box full"><div class="ezz-label">ملاحظات</div><div>${escv(o.Notes)}</div></div>`:''}
      </div>
      <div class="ezz-actions">
        ${['بانتظار التوفر','متوفر - يحتاج اتصال','متوفر جزئيًا - يحتاج اتصال'].includes(o.Status)?'<button class="btn btn-primary" id="ezz-avail">تحديث توفر المنتجات</button>':''}
        ${['متوفر - يحتاج اتصال','متوفر جزئيًا - يحتاج اتصال','تم التواصل - بانتظار الاستلام'].includes(o.Status)&&o.Contact_Status!=='العميل موافق'&&o.Contact_Status!=='العميل رفض'?'<button class="btn btn-primary" id="ezz-contact">تم التواصل</button>':''}
        ${['متوفر - يحتاج اتصال','متوفر جزئيًا - يحتاج اتصال','تم التواصل - بانتظار الاستلام','لم يستلم'].includes(o.Status)?'<button class="btn btn-primary" id="ezz-pickup">تم الاستلام</button><button class="btn btn-outline" id="ezz-postpone">تأجيل المتابعة</button>':''}
        ${!['تم الاستلام','ملغي'].includes(o.Status)?'<button class="btn btn-danger" id="ezz-cancel">إلغاء الطلب</button>':''}
        ${d.undo?.available?`<button class="btn btn-warning" id="ezz-undo">↩ التراجع عن: ${escv(d.undo.action)}</button>`:''}
      </div>
      <div class="ezz-log"><b>سجل المتابعة</b>${(d.activity_log||[]).map(l=>`<div class="ezz-log-row"><b>${escv(l.Created_At)}</b> — ${escv(l.Action)}${l.Note?` — ${escv(l.Note)}`:''} — المستخدم: ${escv(l.User||'موظف')}</div>`).join('')||'<div class="ezz-note">لا يوجد سجل.</div>'}</div>`;
      q('ezz-avail')?.addEventListener('click',()=>{hide(m);availableFixed(id)});
      q('ezz-contact')?.addEventListener('click',async()=>{try{if(typeof window.contact==='function')await window.contact(id);else await api(`/api/orders/${encodeURIComponent(id)}/contact`,{method:'POST',body:'{}'});hide(m)}catch(e){toast(e.message,'error')}});
      q('ezz-pickup')?.addEventListener('click',async()=>{try{if(typeof window.pickup==='function')await window.pickup(id);else await api(`/api/orders/${encodeURIComponent(id)}/pickup`,{method:'POST',body:'{}'});hide(m)}catch(e){toast(e.message,'error')}});
      q('ezz-postpone')?.addEventListener('click',()=>{hide(m);typeof window.openPostpone==='function'?window.openPostpone(id):toast('لا يمكن فتح التأجيل الآن','error')});
      q('ezz-cancel')?.addEventListener('click',async()=>{try{if(typeof window.cancelOrder==='function')await window.cancelOrder(id);hide(m)}catch(e){toast(e.message,'error')}});
      q('ezz-undo')?.addEventListener('click',async()=>{try{if(typeof window.undoOrder==='function')await window.undoOrder(id,d.undo.action);else await api(`/api/orders/${encodeURIComponent(id)}/undo`,{method:'POST',body:'{}'});hide(m)}catch(e){toast(e.message,'error')}});
    }catch(e){body.innerHTML=`<div class="ezz-note" style="color:#a33">تعذر تحميل تفاصيل الطلب: ${escv(e.message)}</div>`;toast(e.message,'error')}
  }
  async function availableFixed(id){
    ensureAll();const m=q('availability-modal');const body=m.querySelector('.ezz-modal-body');body.innerHTML='<div class="ezz-note">جارٍ تحميل المنتجات…</div>';show(m);
    try{
      const d=await api(`/api/orders/${encodeURIComponent(id)}`);const items=d.order?.Items||[];
      if(!items.length){body.innerHTML='<div class="ezz-note">لا توجد منتجات في هذا الطلب.</div>';return}
      body.innerHTML=`<div class="ezz-items">${items.map(i=>`<div class="ezz-item" data-iid="${escv(i.Item_ID)}"><div class="ezz-item-row"><div><div><b>${escv(i.Product_Name)}</b> × ${escv(i.Quantity||1)}</div><div class="ezz-note">${i.Image_Path?'📷 صورة مرفقة':''}</div></div><select class="ezz-status"><option value="بانتظار التوفر" ${i.Availability_Status==='بانتظار التوفر'?'selected':''}>بانتظار التوفر</option><option value="متوفر" ${i.Availability_Status==='متوفر'?'selected':''}>متوفر</option><option value="غير متوفر" ${i.Availability_Status==='غير متوفر'?'selected':''}>غير متوفر</option></select></div><div class="ezz-grid" style="margin-top:10px"><input class="ezz-price" type="number" min="0" step="0.01" placeholder="السعر العادي (اختياري)" value="${escv(i.Available_Price||'')}"><input class="ezz-discount" type="number" min="0" step="0.01" placeholder="السعر بعد الخصم (اختياري)" value="${escv(i.Discounted_Price||'')}"><select class="ezz-reason"><option value="">سبب عدم التوفر</option><option>غير متوفر لدى المورد</option><option>متوقف من الشركة</option><option>لا يوجد مخزون حاليًا</option><option>المنتج غير متاح حاليًا</option><option>السعر من المورد غير مناسب</option><option>سبب آخر</option></select><input class="ezz-note-input" placeholder="ملاحظة إضافية (اختياري)" value="${escv(i.Availability_Note||'')}"></div><label class="ezz-note" style="display:block;margin-top:8px"><input type="checkbox" class="ezz-confirm" ${String(i.Price_Confirmation_Required||'')==='نعم'?'checked':''}> التأكد من السعر مع العميل</label></div>`).join('')}</div><div class="ezz-actions"><button class="btn btn-primary" id="ezz-save-avail">💾 حفظ حالة التوفر</button><button class="btn btn-secondary" id="ezz-close-avail">إلغاء</button></div>`;
      body.querySelectorAll('.ezz-item').forEach(row=>{const st=row.querySelector('.ezz-status');const price=row.querySelector('.ezz-price');const disc=row.querySelector('.ezz-discount');const reason=row.querySelector('.ezz-reason');const note=row.querySelector('.ezz-note-input');const sync=()=>{const a=st.value==='متوفر',u=st.value==='غير متوفر';price.disabled=!a;disc.disabled=!a;row.querySelector('.ezz-confirm').disabled=!a;reason.disabled=!u;note.disabled=!(a||u)};st.addEventListener('change',sync);sync();const old=items.find(x=>String(x.Item_ID)===row.dataset.iid);if(old?.Unavailable_Reason)reason.value=old.Unavailable_Reason});
      q('ezz-close-avail').onclick=()=>hide(m);
      q('ezz-save-avail').onclick=async()=>{const payload=[...body.querySelectorAll('.ezz-item')].map(row=>({Item_ID:row.dataset.iid,availability_status:row.querySelector('.ezz-status').value,available_price:row.querySelector('.ezz-price').value,discounted_price:row.querySelector('.ezz-discount').value,unavailable_reason:row.querySelector('.ezz-reason').value,availability_note:row.querySelector('.ezz-note-input').value,price_confirmation_required:row.querySelector('.ezz-confirm').checked}));const btn=q('ezz-save-avail');btn.disabled=true;try{await api(`/api/orders/${encodeURIComponent(id)}/availability`,{method:'POST',body:JSON.stringify({items:payload})});toast('تم حفظ حالة توفر المنتجات');hide(m);if(typeof window.refresh==='function')window.refresh();detailsFixed(id)}catch(e){toast(e.message,'error')}finally{btn.disabled=false}};
    }catch(e){body.innerHTML=`<div class="ezz-note" style="color:#a33">تعذر فتح تحديث التوفر: ${escv(e.message)}</div>`;toast(e.message,'error')}
  }
  window.details=detailsFixed;window.available=availableFixed;window.openAvailability=availableFixed;
  window.ezzEnsureRoutingModals=ensureAll;
  function boot(){ensureAll()}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();