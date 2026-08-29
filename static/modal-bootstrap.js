(function(){
  'use strict';
  function ensure(id, html){
    if(document.getElementById(id)) return;
    const wrap=document.createElement('div');
    wrap.id=id;
    wrap.className='modal-overlay hidden';
    wrap.setAttribute('aria-hidden','true');
    wrap.innerHTML=html;
    document.body.appendChild(wrap);
  }
  function boot(){
    if(!document.body) return;
    ensure('order-modal','<div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div class="modal-header"><h3 id="modal-title">تفاصيل الطلب</h3><button type="button" class="modal-close" id="modal-close-btn" aria-label="إغلاق">×</button></div><div id="modal-body" class="modal-body"></div></div>');
    ensure('availability-modal','<div class="modal" role="dialog" aria-modal="true"><div class="modal-header"><h3>تحديث توفر المنتجات</h3><button type="button" class="modal-close" id="availability-close-btn" aria-label="إغلاق">×</button></div><div id="availability-items" class="modal-body"></div><div class="modal-actions"><button type="button" class="btn btn-secondary" id="availability-cancel-btn">إلغاء</button><button type="button" class="btn btn-primary" id="availability-save-btn">حفظ</button></div></div>');
    ensure('confirm-modal','<div class="modal small" role="dialog" aria-modal="true"><div class="modal-header"><h3>تأكيد</h3></div><div id="confirm-message" class="modal-body"></div><div class="modal-actions"><button type="button" class="btn btn-secondary" id="confirm-no-btn">إلغاء</button><button type="button" class="btn btn-danger" id="confirm-yes-btn">تأكيد</button></div></div>');
    ensure('postpone-modal','<div class="modal small" role="dialog" aria-modal="true"><div class="modal-header"><h3>تأجيل المتابعة</h3></div><div class="modal-body"><input type="date" id="postpone-custom-date"></div><div class="modal-actions"><button type="button" class="btn btn-secondary" id="postpone-close-btn">إلغاء</button><button type="button" class="btn btn-primary" id="postpone-custom-confirm">حفظ</button></div></div>');
  }
  if(document.readyState==='loading') boot(); else boot();
})();
