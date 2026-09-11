function replyItems(order){
  if(['تم الاستلام','ملغي'].includes(order.Status))return [];
  return (order.Items||[]).filter(item=>
    ['متوفر','غير متوفر'].includes(item.Availability_Status)&&item.Customer_Decision!=='rejected');
}
function customerReplyPanel(order){
  const items=replyItems(order);
  if(!items.length)return '';
  const canAccept=items.some(item=>item.Availability_Status==='متوفر');
  return `<section class="panel customer-reply-panel" aria-labelledby="customer-reply-heading">
    <h4 id="customer-reply-heading">تسجيل رد العميل</h4>
    <p>حالة التواصل الحالية: <strong>${esc(order.Contact_Status||'لم يتم التواصل')}</strong></p>
    <label for="customer-reply-choice">رد العميل</label>
    <select id="customer-reply-choice">
      <option value="">اختر الرد…</option>
      ${canAccept?'<option value="العميل موافق">العميل موافق على المنتجات المتوفرة</option>':''}
      <option value="العميل رفض">العميل رفض منتجات محددة</option>
    </select>
    <p>الموافقة تشمل المنتجات المتوفرة غير المرفوضة. المنتجات بانتظار التوفر تبقى للمتابعة.</p>
    <fieldset id="customer-reply-rejected" hidden>
      <legend>حدد المنتجات التي رفضها العميل</legend>
      ${items.map(item=>`<label style="display:block;margin:8px 0"><input type="checkbox" value="${esc(item.Item_ID)}"> ${esc(item.Product_Name)} — ${esc(item.Availability_Status)}</label>`).join('')}
    </fieldset>
    <label for="customer-reply-note">ملاحظة عن الرد (اختياري)</label>
    <textarea id="customer-reply-note" rows="2" maxlength="2000"></textarea>
    <button type="button" class="btn btn-primary" id="save-customer-reply">حفظ رد العميل</button>
    <p id="customer-reply-error" role="alert"></p>
  </section>`;
}
function customerReplyPayload(order,status,note,rejectedIds){
  const items=replyItems(order);
  if(!items.length)throw new Error('لا توجد منتجات يمكن تسجيل رد العميل عليها');
  if(!['العميل موافق','العميل رفض'].includes(status))throw new Error('اختر رد العميل أولًا');
  if(status==='العميل موافق'&&!items.some(item=>item.Availability_Status==='متوفر'))
    throw new Error('لا يوجد منتج متوفر لتسجيل الموافقة');
  if(status==='العميل رفض'){
    if(!rejectedIds.length)throw new Error('حدد منتجًا واحدًا على الأقل رفضه العميل');
    const allowed=new Set(items.map(item=>String(item.Item_ID)));
    if(rejectedIds.some(id=>!allowed.has(String(id))))throw new Error('المنتجات المحددة لا تطابق الطلب');
  }
  return {contact_status:status,note:note.trim(),rejected_item_ids:status==='العميل رفض'?rejectedIds:[]};
}
function bindCustomerReply(order){
  const panel=document.querySelector('#order-modal .customer-reply-panel');
  if(!panel)return;
  const choice=panel.querySelector('#customer-reply-choice');
  const rejected=panel.querySelector('#customer-reply-rejected');
  const button=panel.querySelector('#save-customer-reply');
  const error=panel.querySelector('#customer-reply-error');
  choice.addEventListener('change',()=>{rejected.hidden=choice.value!=='العميل رفض';error.textContent='';});
  button.addEventListener('click',async()=>{
    if(button.disabled)return;
    error.textContent='';
    try{
      const ids=[...rejected.querySelectorAll('input:checked')].map(input=>input.value);
      const payload=customerReplyPayload(order,choice.value,panel.querySelector('#customer-reply-note').value,ids);
      setButtonLoading(button,true,'جارٍ حفظ الرد');
      await apiFetch(`/api/orders/${encodeURIComponent(order.Order_ID)}/contact-status`,{method:'POST',body:JSON.stringify(payload)});
      toast('تم حفظ رد العميل');
      refresh();
      await details(order.Order_ID);
    }catch(exc){error.textContent=exc.message;}
    finally{setButtonLoading(button,false);}
  });
}
