const STATUS_LABELS={
  "بانتظار التوفر":{cls:"status-pending"},"متوفر - يحتاج اتصال":{cls:"status-available"},"متوفر جزئيًا - يحتاج اتصال":{cls:"status-available"},"غير متوفر - يحتاج اتصال":{cls:"status-cancelled"},
  "تم التواصل - بانتظار الاستلام":{cls:"status-contacted"},"تم الاستلام":{cls:"status-picked"},
  "لم يستلم":{cls:"status-notpicked"},"ملغي":{cls:"status-cancelled"}
};
const STATUS_ORDER=Object.keys(STATUS_LABELS);
const CONTACT_STATUS_LABELS={"لم يتم التواصل":"contact-not","بانتظار رد العميل":"contact-await","العميل موافق":"contact-accepted","العميل رفض":"contact-rejected","مؤجل":"contact-postponed"};
let currentPostpone=null,confirmCallback=null;

async function apiFetch(url,options={}){
  const method=String(options.method||"GET").toUpperCase();
  const csrf=document.querySelector('meta[name="csrf-token"]')?.content||"";
  const headers={...(options.body instanceof FormData?{}:{"Content-Type":"application/json"}),...(options.headers||{})};
  if(!["GET","HEAD","OPTIONS"].includes(method)&&csrf) headers["X-CSRF-Token"]=csrf;
  const opts={...options,credentials:options.credentials||"same-origin",headers};
  const r=await fetch(url,opts);let d=null;try{d=await r.json()}catch{}
  if(!r.ok){const e=new Error(d?.error||(d?.errors?Object.values(d.errors).join("، "):"حدث خطأ"));e.status=r.status;e.data=d;throw e}return d
}
function toast(msg,type="success"){
  const container=document.getElementById("toast-container");
  if(!container)return;
  const e=document.createElement("div");
  e.className=`toast ${type}`;
  e.setAttribute("role", type==="error" ? "alert" : "status");
  e.setAttribute("aria-live", type==="error" ? "assertive" : "polite");
  e.textContent=msg;
  container.appendChild(e);
  setTimeout(()=>e.remove(),3500);
}
function setButtonLoading(button,loading,label){
  if(!button)return;
  if(loading){
    if(!button.dataset.loadingLabel) button.dataset.loadingLabel=button.textContent;
    button.disabled=true;
    button.classList.add("is-loading");
    button.setAttribute("aria-busy","true");
    if(label) button.dataset.loadingText=label;
  }else{
    button.disabled=false;
    button.classList.remove("is-loading");
    button.removeAttribute("aria-busy");
    delete button.dataset.loadingText;
    if(button.dataset.loadingLabel!==undefined){
      button.textContent=button.dataset.loadingLabel;
      delete button.dataset.loadingLabel;
    }
  }
}
function esc(s){return String(s??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}
function fmtDate(s){if(!s)return"—";const p=String(s).split(" ")[0].split("-");return p.length===3?`${p[2]}/${p[1]}/${p[0]}`:String(s)}
function badge(s){return `<span class="status-badge ${STATUS_LABELS[s]?.cls||"status-pending"}">${esc(s)}</span>`}
function normalizePhoneClient(p){let s=String(p||"").replace(/[٠-٩]/g,d=>String("٠١٢٣٤٥٦٧٨٩".indexOf(d))).replace(/\D/g,"");if(s.startsWith("00"))s=s.slice(2);if(s.startsWith("966"))return s;if(s.startsWith("0")&&s.length===10)return "966"+s.slice(1);if(s.startsWith("5")&&s.length===9)return "966"+s;return s}
function waUrl(phone,message){const p=normalizePhoneClient(phone);return `whatsapp://send?phone=${p}&text=${encodeURIComponent(message||"")}`}
function openWhatsAppOnThisDevice(appUrl,webUrl){if(!appUrl)return;let timer=null;const hidden=()=>{if(timer)clearTimeout(timer);document.removeEventListener("visibilitychange",hidden)};document.addEventListener("visibilitychange",hidden);try{window.location.href=appUrl}catch(_e){if(webUrl)window.open(webUrl,"_blank","noopener");return}timer=setTimeout(()=>{document.removeEventListener("visibilitychange",hidden);if(document.visibilityState==="visible"&&webUrl)window.open(webUrl,"_blank","noopener")},1400)}
function phoneLinks(p){const n=normalizePhoneClient(p);if(!n)return"";const wa=waUrl(n,"");return `<span class="contact-links"><a class="btn btn-icon btn-sm" href="tel:${n}">📞</a><a class="btn btn-icon btn-sm wa-desktop-link" href="${wa}">💬</a></span>`}
function todayISO(){return new Date().toLocaleDateString("en-CA",{timeZone:"Asia/Riyadh"})}
function switchView(v){const current=document.querySelector(".view.active")?.id?.replace(/^view-/,"");document.querySelectorAll(".view").forEach(x=>x.classList.remove("active"));document.querySelectorAll(".nav-btn[data-view]").forEach(x=>x.classList.remove("active"));document.getElementById(`view-${v}`)?.classList.add("active");document.querySelector(`.nav-btn[data-view="${v}"]`)?.classList.add("active");if(v==="dashboard"&&current!=="dashboard")loadDashboard();if(v==="orders")loadOrders();if(v==="backups")loadBackups();if(v==="message-templates")loadMessageTemplates();if(v==="shortages")window.dailyShortages?.open?.();if(v==="whatsapp"){loadMessageTemplates();loadShortages();loadWaCustomers();}if(v==="whatsapp_legacy_never"){loadShortages();loadWaCustomers()}if(v==="new-order")document.querySelector('[name="order_date"]').value ||= todayISO()}
function initNav(){
  document.querySelectorAll(".nav-btn[data-view]").forEach(b=>b.addEventListener("click",()=>switchView(b.dataset.view)));
}
const statCards=[
  ['total','إجمالي الطلبات','all'],
  ['pending','بانتظار التوفير','pending'],
  ['available','جاهز للتواصل','available'],
  ['awaiting_reply','بانتظار رد العميل','awaiting_reply'],
  ['pickup_pending','بانتظار الاستلام','pickup_pending'],
  ['picked_up','تم الاستلام','picked_up'],
  ['today_followup','متابعة اليوم','today_followup'],
  ['overdue','متأخرة','overdue']
];
let dashboardAllOrders=[],dashboardFilterKey=null;
function dashboardFilterLabel(key){return statCards.find(x=>x[2]===key)?.[1]||'الطلبات'}
function dashboardFilterOrders(orders,key){
  const serverFilters=window.dashboardStats?.dashboard_filters;
  if(serverFilters && Array.isArray(serverFilters[key])) return serverFilters[key];
  return orders;
}
function renderDashboardCards(stats){
  const wrap=document.getElementById('stats-grid');
  wrap.innerHTML=statCards.map(([k,l,key])=>{
    const active=dashboardFilterKey===key?' active':'';
    const criticalMap={overdue:'overdue',awaiting_reply:'waiting'};
    const statusAttr=criticalMap[key]?` data-status="${criticalMap[key]}"`:'';
    return `<button type="button" class="stat-card${active}"${statusAttr} data-dashboard-filter="${key}" aria-pressed="${dashboardFilterKey===key}"><div class="stat-value">${stats[k]??0}</div><div class="stat-label">${l}</div><span class="stat-hint">اضغط لعرض الطلبات</span></button>`;
  }).join('');
  wrap.querySelectorAll('[data-dashboard-filter]').forEach(b=>b.onclick=()=>toggleDashboardFilter(b.dataset.dashboardFilter));
}
async function toggleDashboardFilter(key){
  dashboardFilterKey=dashboardFilterKey===key?null:key;
  if(!dashboardFilterKey){closeDashboardResults();renderDashboardCards(window.dashboardStats||{});return;}
  try{renderDashboardCards(window.dashboardStats||{});renderDashboardResults();}catch(e){toast(e.message,'error')}
}
function renderDashboardResults(){
  const panel=document.getElementById('dashboard-results-panel');
  if(!dashboardFilterKey){closeDashboardResults();return;}
  panel.classList.remove('hidden');
  document.getElementById('dashboard-results-title').textContent=dashboardFilterLabel(dashboardFilterKey);
  const base=dashboardFilterOrders(dashboardAllOrders,dashboardFilterKey);
  const q=document.getElementById('dashboard-results-search').value.trim().toLowerCase();
  const contactFilter=document.getElementById('dashboard-contact-filter')?.value||'';
  let orders=base;
  if(contactFilter) orders=orders.filter(o=>(o.Contact_Status||'لم يتم التواصل')===contactFilter);
  if(q){orders=orders.filter(o=>{const items=(o.Items||[]).map(i=>i.Product_Name).join(' ');return `${o.Order_ID} ${o.Customer_Name} ${o.Phone} ${o.Product_Name||''} ${items}`.toLowerCase().includes(q)})}
  document.getElementById('dashboard-results-subtitle').textContent=orders.length?`يتم عرض ${orders.length} من أصل ${base.length} طلب — اضغط على التفاصيل لفتح الطلب.`:'لا توجد طلبات ضمن هذا التصنيف حاليًا.';
  const body=document.getElementById('dashboard-results-body');
  if(!orders.length){body.innerHTML='<tr><td colspan="8" class="empty-state">لا توجد طلبات مطابقة ✅</td></tr>';}
  else{body.innerHTML=orders.map(o=>`<tr><td>${esc(o.Order_ID)}</td><td><strong>${esc(o.Customer_Name)}</strong><br><span class="fi-meta">${esc(o.Phone)}</span></td><td class="products-cell">${productsSummary(o)}</td><td>${fmtDate(o.Order_Date)}</td><td>${badge(o.Status)}</td><td>${contactBadge(o.Contact_Status)}</td><td>${fmtDate(o.Next_Followup_Date)}</td><td><button type="button" class="btn btn-secondary btn-sm dashboard-detail-btn" data-id="${esc(o.Order_ID)}">التفاصيل</button><button type="button" class="btn btn-outline btn-sm dashboard-wa-btn" data-id="${esc(o.Order_ID)}">💬 إرسال</button></td></tr>`).join('');body.querySelectorAll('.dashboard-detail-btn').forEach(b=>b.onclick=()=>details(b.dataset.id));body.querySelectorAll('.dashboard-wa-btn').forEach(b=>b.onclick=()=>openClientWhatsApp(b.dataset.id));}
  document.getElementById('dashboard-results-count').textContent=`عدد النتائج: ${orders.length}`;
}
function closeDashboardResults(){const panel=document.getElementById('dashboard-results-panel');panel.classList.add('hidden');document.getElementById('dashboard-results-search').value='';if(document.getElementById('dashboard-contact-filter'))document.getElementById('dashboard-contact-filter').value='';}
let dashboardLoadPromise=null;
let dashboardLoadedOnce=false;

async function loadDashboard(){
  if(dashboardLoadPromise) return dashboardLoadPromise;
  dashboardLoadPromise=(async()=>{
    try{
      const data=await apiFetch('/api/dashboard');
      window.dashboardStats=data;
      dashboardAllOrders=data.orders||[];
      renderDashboardCards(data);
      document.getElementById('today-date').textContent=fmtDate(data.date);
      document.getElementById('today-summary').innerHTML=`لديك <strong>${data.available}</strong> طلبات جاهزة للتواصل، <strong>${data.awaiting_reply}</strong> بانتظار رد العميل، <strong>${data.overdue}</strong> متابعات متأخرة`;

      document.dispatchEvent(new CustomEvent('ezz:dashboard-data',{detail:data}));
      const followupTarget=document.getElementById('followups-list');
      if(followupTarget) renderFollowupsList(data.followups||[]);
      if(dashboardFilterKey) renderDashboardResults();
      dashboardLoadedOnce=true;
    }catch(e){
      toast(e.message,'error');
      throw e;
    }finally{
      dashboardLoadPromise=null;
    }
  })();
  return dashboardLoadPromise;
}


function renderFollowupsList(followups){
  const c=document.getElementById("followups-list");
  if(!c)return;
  if(!followups.length){
    c.innerHTML='<div class="empty-state">لا توجد متابعات مطلوبة اليوم 🎉</div>';
    return;
  }
  c.innerHTML=followups.map(o=>{
    const k=o._followup_kind;
    const tag=k==='overdue'?'🔴 متابعة متأخرة':k==='needs_call'?'🟠 يحتاج اتصال':'🔵 متابعة اليوم';
    const btn=k==='needs_call'
      ? '<button class="btn btn-primary btn-sm act-contact" data-id="'+esc(o.Order_ID)+'">تم الاتصال</button>'
      : '<button class="btn btn-primary btn-sm act-pickup" data-id="'+esc(o.Order_ID)+'">تم الاستلام</button><button class="btn btn-outline btn-sm act-postpone" data-id="'+esc(o.Order_ID)+'">تأجيل</button>';
    return '<div class="followup-card kind-'+esc(k)+'"><div class="followup-info"><div class="followup-tag">'+tag+'</div><div class="fi-name">'+esc(o.Customer_Name)+'</div><div class="fi-meta">'+productsSummary(o)+'<br>'+esc(o.Phone)+'</div></div><div class="followup-actions"><button class="btn btn-outline btn-sm act-wa" data-id="'+esc(o.Order_ID)+'">💬 إرسال الرسالة</button>'+phoneLinks(o.Phone)+btn+'<button class="btn btn-secondary btn-sm act-details" data-id="'+esc(o.Order_ID)+'">التفاصيل</button></div></div>';
  }).join("");
  attachActions(c);
}

function productsSummary(o){if(Array.isArray(o.Items)&&o.Items.length)return o.Items.map(i=>`${esc(i.Product_Name)} × ${i.Quantity}${i.Image_Path?' 📷':''}`).join("<br>");return esc(o.Product_Name)}
function imageHtml(item,compact=false){if(!item?.Image_Path)return `<div class="no-image">لا توجد صورة</div>`;const u=`/uploads/${encodeURIComponent(item.Image_Path).replace(/%2F/g,'/')}`;return `<a href="${u}" target="_blank" rel="noopener" class="product-image-link"><img class="product-thumb ${compact?'compact':''}" src="${u}" alt="${esc(item.Product_Name)}"></a>`}
async function loadFollowups(term=""){
  try{
    let followups;
    if(term){
      const data=await apiFetch("/api/followups/today");
      followups=data.followups||[];
      const q=term.toLowerCase();
      followups=followups.filter(o=>`${o.Customer_Name} ${o.Phone} ${o.Product_Name} ${(o.Items||[]).map(i=>i.Product_Name).join(" ")}`.toLowerCase().includes(q));
    }else{
      followups=(window.dashboardStats?.followups)||[];
    }
    renderFollowupsList(followups);
  }catch(e){
    const c=document.getElementById("followups-list");
    if(c)c.innerHTML='<div class="empty-state">تعذر تحميل المتابعات</div>';
  }
}

function attachActions(c){c.querySelectorAll(".act-wa").forEach(b=>b.onclick=()=>openClientWhatsApp(b.dataset.id));c.querySelectorAll(".act-contact").forEach(b=>b.onclick=()=>contact(b.dataset.id));c.querySelectorAll(".act-pickup").forEach(b=>b.onclick=()=>pickup(b.dataset.id));c.querySelectorAll(".act-postpone").forEach(b=>b.onclick=()=>openPostpone(b.dataset.id));c.querySelectorAll(".act-details").forEach(b=>b.onclick=()=>details(b.dataset.id))}
function contactBadge(s){const v=s||"لم يتم التواصل";return `<span class="contact-badge ${CONTACT_STATUS_LABELS[v]||"contact-not"}">${esc(v)}</span>`}
function renderRejectedItemsChooser(order){
  const host=document.getElementById('detail-rejected-items-host');
  const status=document.getElementById('detail-contact-status')?.value;
  if(!host || status!=='العميل رفض'){ if(host)host.innerHTML=''; return; }
  const available=(order.Items||[]).filter(i=>i.Availability_Status==='متوفر');
  host.innerHTML = available.length ? `<div class="di-label">حدد المنتجات التي رفضها العميل</div><div class="rejected-items-chooser">${available.map(i=>`<label><input type="checkbox" class="detail-rejected-item" value="${esc(i.Item_ID)}" checked> ${esc(i.Product_Name)} × ${i.Quantity}</label>`).join('')}</div>` : '<div class="field-error">لا توجد منتجات متوفرة حاليًا.</div>';
}
async function saveContactStatus(id,status){try{const note=document.getElementById("detail-contact-note")?.value||"";const rejected_item_ids=[...document.querySelectorAll('.detail-rejected-item:checked')].map(x=>x.value);await apiFetch(`/api/orders/${id}/contact-status`,{method:"POST",body:JSON.stringify({contact_status:status,note,rejected_item_ids})});toast("تم تحديث حالة التواصل");details(id);refresh()}catch(e){toast(e.message,"error")}}
async function contact(id){try{await apiFetch(`/api/orders/${id}/contact`,{method:"POST",body:"{}"});toast("تم تسجيل الاتصال بالعميل");refresh()}catch(e){toast(e.message,"error")}}
async function pickup(id){
  openConfirm("تأكيد تسجيل أن العميل استلم الطلب؟",async()=>{
    try{
      await apiFetch("/api/orders/"+id+"/pickup",{method:"POST",body:JSON.stringify({})});
      toast("تم تسجيل استلام الطلب");
      closeModals();
      refresh();
    }catch(e){toast(e.message,"error")}
  });
}
async function notPicked(id){
  openConfirm("تأكيد أن العميل لم يستلم الطلب؟ سيتم إعادته إلى المتابعة.",async()=>{
    try{
      await apiFetch("/api/orders/"+id+"/not-picked",{method:"POST",body:JSON.stringify({})});
      toast("تم تسجيل أن العميل لم يستلم الطلب");
      closeModals();
      refresh();
    }catch(e){toast(e.message,"error")}
  });
}
let currentAvailability=null,availabilityReturnOrder=null; let messageTemplates={};
function openAvailability(id){currentAvailability=id;availabilityReturnOrder=id;const orderModal=document.getElementById('order-modal');orderModal.classList.add('hidden');orderModal.setAttribute('aria-hidden','true');const availabilityModal=document.getElementById('availability-modal');availabilityModal.classList.remove('hidden');availabilityModal.setAttribute('aria-hidden','false');apiFetch(`/api/orders/${id}`).then(d=>{const items=d.order.Items||[];document.getElementById('availability-items').innerHTML=items.map(i=>`<div class="availability-row" data-item-id="${esc(i.Item_ID)}"><div class="availability-item-head"><div><b>${esc(i.Product_Name)}</b><span> × ${i.Quantity}</span>${String(i.Customer_Decision||'').trim()==='rejected'?'<span class="image-attached">❌ مرفوض من العميل</span>':''}</div><select class="avail-status"><option value="بانتظار التوفر" ${i.Availability_Status==='بانتظار التوفر'?'selected':''}>بانتظار التوفر</option><option value="متوفر" ${i.Availability_Status==='متوفر'?'selected':''}>متوفر</option><option value="غير متوفر" ${i.Availability_Status==='غير متوفر'?'selected':''}>غير متوفر</option></select></div><div class="availability-fields"><input class="avail-price" type="number" min="0" step="0.01" placeholder="السعر العادي (اختياري)" value="${esc(i.Available_Price||'')}"><input class="avail-discount" type="number" min="0" step="0.01" placeholder="السعر بعد الخصم (اختياري)" value="${esc(i.Discounted_Price||'')}"><label class="price-confirm-check"><input type="checkbox" class="avail-price-confirm" ${String(i.Price_Confirmation_Required||'').trim()==='نعم'?'checked':''}> التأكد من السعر مع العميل قبل التوفير</label><select class="avail-reason"><option value="">سبب عدم التوفر</option><option ${i.Unavailable_Reason==='غير متوفر لدى المورد'?'selected':''}>غير متوفر لدى المورد</option><option ${i.Unavailable_Reason==='متوقف من الشركة'?'selected':''}>متوقف من الشركة</option><option ${i.Unavailable_Reason==='لا يوجد مخزون حاليًا'?'selected':''}>لا يوجد مخزون حاليًا</option><option ${i.Unavailable_Reason==='المنتج غير متاح حاليًا'?'selected':''}>المنتج غير متاح حاليًا</option><option ${i.Unavailable_Reason==='السعر من المورد غير مناسب'?'selected':''}>السعر من المورد غير مناسب</option><option ${i.Unavailable_Reason==='سبب آخر'?'selected':''}>سبب آخر</option></select><input class="avail-note" placeholder="ملاحظة إضافية (اختياري)" value="${esc(i.Availability_Note||'')}">${String(i.Customer_Decision||'').trim()==='rejected'?'<label class="price-confirm-check"><input type="checkbox" class="avail-reopen-customer"> إعادة فتح المنتج للتواصل مع العميل</label>':''}</div><div class="availability-current">${i.Available_Price?`السعر الحالي: ${esc(i.Available_Price)} ريال`:'السعر غير مسجل'}${i.Discounted_Price?` — بعد الخصم: ${esc(i.Discounted_Price)} ريال`:''}</div></div>`).join('');document.querySelectorAll('.availability-row').forEach(row=>{const st=row.querySelector('.avail-status'),reason=row.querySelector('.avail-reason');const toggle=()=>{const available=st.value==='متوفر',unavailable=st.value==='غير متوفر';row.querySelector('.avail-price').disabled=!available;row.querySelector('.avail-discount').disabled=!available;row.querySelector('.avail-price-confirm').disabled=!available;reason.disabled=!unavailable;row.querySelector('.avail-note').disabled=!(available||unavailable)};st.onchange=toggle;toggle();});}).catch(e=>toast(e.message,'error'))}
function closeAvailability(restore=true){const id=availabilityReturnOrder;const a=document.getElementById('availability-modal'),o=document.getElementById('order-modal');a.classList.add('hidden');a.setAttribute('aria-hidden','true');currentAvailability=null;availabilityReturnOrder=null;if(restore&&id){o.classList.remove('hidden');o.setAttribute('aria-hidden','false');details(id)}}
async function saveAvailability(){if(!currentAvailability)return;const items=[...document.querySelectorAll('.availability-row')].map(r=>({Item_ID:r.dataset.itemId,availability_status:r.querySelector('.avail-status').value,available_price:r.querySelector('.avail-price').value,discounted_price:r.querySelector('.avail-discount').value,unavailable_reason:r.querySelector('.avail-reason').value,availability_note:r.querySelector('.avail-note').value,price_confirmation_required:r.querySelector('.avail-price-confirm').checked,reopen_customer:!!r.querySelector('.avail-reopen-customer')?.checked}));try{const id=currentAvailability;await apiFetch(`/api/orders/${id}/availability`,{method:'POST',body:JSON.stringify({items})});toast('تم حفظ حالة توفر المنتجات');currentAvailability=null;availabilityReturnOrder=null;document.getElementById('availability-modal').classList.add('hidden');document.getElementById('availability-modal').setAttribute('aria-hidden','true');refresh();details(id)}catch(e){toast(e.message,'error')}}
function available(id){openAvailability(id)}
function cancelOrder(id){openConfirm("هل أنت متأكد من إلغاء هذا الطلب؟",async()=>{try{await apiFetch(`/api/orders/${id}/cancel`,{method:"POST",body:"{}"});toast("تم إلغاء الطلب");document.getElementById("order-modal").classList.add("hidden");refresh()}catch(e){toast(e.message,"error")}})}
function openConfirm(msg,cb){confirmCallback=cb;document.getElementById("confirm-message").textContent=msg;document.getElementById("confirm-modal").classList.remove("hidden")}
function closeModals(){document.querySelectorAll(".modal-overlay").forEach(x=>x.classList.add("hidden"));currentPostpone=null}

async function details(id){try{const d=await apiFetch(`/api/orders/${id}`);const o=d.order;document.getElementById("modal-title").textContent=`تفاصيل الطلب ${o.Order_ID}`;document.getElementById("modal-body").innerHTML=`<div class="order-head"><div><b>${esc(o.Customer_Name)}</b><div>${esc(o.Phone)}</div></div>${phoneLinks(o.Phone)}<button class="btn btn-outline btn-sm detail-wa" data-id="${esc(o.Order_ID)}">💬 رسالة جاهزة للعميل</button></div><div class="detail-grid"><div class="detail-item full"><div class="di-label">المنتجات والصور</div><div class="items-detail">${(o.Items||[]).map(i=>`<div class="item-detail-row"><div><span>${esc(i.Product_Name)}</span> <strong>× ${i.Quantity}</strong>${i.Image_Path?'<span class="image-attached">📷 مرفقة</span>':''}${i.Price_Confirmation_Required==='نعم'?'<span class="image-attached">💰 تأكيد السعر</span>':''}</div><div>${imageHtml(i,true)}</div></div>`).join("")||esc(o.Product_Name)}</div></div><div class="detail-item"><div class="di-label">الحالة</div><div class="di-value">${badge(o.Status)}</div></div><div class="detail-item"><div class="di-label">تاريخ الطلب</div><div class="di-value">${fmtDate(o.Order_Date)}</div></div><div class="detail-item"><div class="di-label">تاريخ التوفر</div><div class="di-value">${fmtDate(o.Available_Date)}</div></div><div class="detail-item"><div class="di-label">آخر تواصل</div><div class="di-value">${fmtDate(o.Last_Contact_Date)}</div></div><div class="detail-item"><div class="di-label">موعد المتابعة</div><div class="di-value">${fmtDate(o.Next_Followup_Date)}</div></div><div class="detail-item"><div class="di-label">تاريخ الاستلام</div><div class="di-value">${fmtDate(o.Pickup_Date)}</div></div>${o.Notes?`<div class="detail-item full"><div class="di-label">ملاحظات</div><div class="di-value">${esc(o.Notes)}</div></div>`:""}</div><div class="contact-status-panel"><div><div class="di-label">حالة التواصل</div><div class="di-value">${contactBadge(o.Contact_Status)}</div></div><div class="contact-status-actions"><select id="detail-contact-status"><option value="لم يتم التواصل">لم يتم التواصل</option><option value="بانتظار رد العميل">بانتظار رد العميل</option><option value="العميل موافق">العميل موافق</option><option value="العميل رفض">العميل رفض</option><option value="مؤجل">مؤجل</option></select><input id="detail-contact-note" placeholder="ملاحظة التواصل (اختياري)"><button type="button" class="btn btn-outline btn-sm" id="save-contact-status">حفظ حالة التواصل</button></div></div><div class="detail-actions">${(((o.Items||[]).some(i=>i.Availability_Status==='بانتظار التوفر'))||['بانتظار التوفر','متوفر - يحتاج اتصال','متوفر جزئيًا - يحتاج اتصال','غير متوفر - يحتاج اتصال'].includes(o.Status))?`<button class="btn btn-primary modal-avail">تحديث توفر المنتجات</button>`:""}${['متوفر - يحتاج اتصال','متوفر جزئيًا - يحتاج اتصال','تم التواصل - بانتظار الاستلام'].includes(o.Status)&&o.Contact_Status!=='العميل موافق'&&o.Contact_Status!=='العميل رفض'?`<button class="btn btn-primary modal-contact">💬 تم التواصل</button>`:""}${['متوفر - يحتاج اتصال','متوفر جزئيًا - يحتاج اتصال','تم التواصل - بانتظار الاستلام','لم يستلم'].includes(o.Status)?`<button class="btn btn-primary modal-pickup">تم الاستلام</button><button class="btn btn-outline modal-postpone">تأجيل المتابعة</button>`:""}${o.Status==='تم الاستلام'?'<button class="btn btn-outline modal-not-picked">العميل لم يستلم</button>':''}${!['تم الاستلام','ملغي'].includes(o.Status)?`<button class="btn btn-danger modal-cancel">إلغاء الطلب</button>`:""}${d.undo?.available?`<button class="btn btn-warning modal-undo">↩ التراجع عن: ${esc(d.undo.action)}</button>`:""}</div><div class="activity-log"><h4>سجل المتابعة</h4>${(d.activity_log||[]).map(l=>`<div class="activity-item"><b>${esc(l.Created_At)}</b><span>${esc(l.Action)}${l.Note?` — ${esc(l.Note)}`:""}</span></div>`).join("")||'<div class="empty-state">لا يوجد سجل</div>'}</div>`;const m=document.getElementById("order-modal");m.classList.remove("hidden");const cs=m.querySelector("#detail-contact-status"); if(cs) cs.value=o.Contact_Status||"لم يتم التواصل"; const panel=m.querySelector(".contact-status-panel"); if(panel&&!m.querySelector("#detail-rejected-items-host")){const host=document.createElement("div");host.id="detail-rejected-items-host";panel.appendChild(host)} renderRejectedItemsChooser(o); if(cs)cs.onchange=()=>renderRejectedItemsChooser(o); if(m.querySelector("#detail-contact-note")) m.querySelector("#detail-contact-note").value=""; m.querySelector("#save-contact-status")?.addEventListener("click",()=>saveContactStatus(id,cs.value)); m.querySelector(".detail-wa")?.addEventListener("click",()=>openClientWhatsApp(id));m.querySelector(".modal-avail")?.addEventListener("click",()=>available(id));m.querySelector(".modal-contact")?.addEventListener("click",()=>contact(id));m.querySelector(".modal-pickup")?.addEventListener("click",()=>pickup(id));m.querySelector(".modal-not-picked")?.addEventListener("click",()=>notPicked(id));m.querySelector(".modal-postpone")?.addEventListener("click",()=>{m.classList.add("hidden");openPostpone(id)});m.querySelector(".modal-cancel")?.addEventListener("click",()=>cancelOrder(id));m.querySelector(".modal-undo")?.addEventListener("click",()=>undoOrder(id,d.undo.action))}catch(e){toast(e.message,"error")}}
async function undoOrder(id,action){openConfirm(`هل تريد التراجع عن: ${action}؟`,async()=>{try{await apiFetch(`/api/orders/${id}/undo`,{method:"POST",body:"{}"});toast("تم التراجع عن آخر تغيير");document.getElementById("order-modal").classList.add("hidden");refresh()}catch(e){toast(e.message,"error")}})}
function openPostpone(id){currentPostpone=id;document.getElementById("postpone-custom-date").value="";document.getElementById("postpone-modal").classList.remove("hidden")}
async function doPostpone(days,date=null){if(!currentPostpone)return;try{await apiFetch(`/api/orders/${currentPostpone}/postpone`,{method:"POST",body:JSON.stringify(date?{custom_date:date}:{days})});toast("تم تأجيل المتابعة");closeModals();refresh()}catch(e){toast(e.message,"error")}}
function renderOrders(orders){const b=document.getElementById("orders-table-body");if(!orders.length){b.innerHTML='<tr><td colspan="12" class="empty-state">لا توجد طلبات</td></tr>';return}b.innerHTML=orders.map(o=>`<tr><td>${esc(o.Order_ID)}</td><td>${esc(o.Customer_Name)}</td><td>${esc(o.Phone)}</td><td class="products-cell">${productsSummary(o)}</td><td>${o.Quantity}</td><td>${fmtDate(o.Order_Date)}</td><td>${fmtDate(o.Available_Date)}</td><td>${badge(o.Status)}</td><td>${contactBadge(o.Contact_Status)}</td><td>${fmtDate(o.Last_Contact_Date)}</td><td>${fmtDate(o.Next_Followup_Date)}</td><td><button class="btn btn-secondary btn-sm details-btn" data-id="${o.Order_ID}">التفاصيل</button></td></tr>`).join("");b.querySelectorAll(".details-btn").forEach(x=>x.onclick=()=>details(x.dataset.id))}
function populateStatus(){const s=document.getElementById("orders-status-filter");if(s.dataset.done)return;STATUS_ORDER.forEach(x=>s.insertAdjacentHTML("beforeend",`<option value="${esc(x)}">${esc(x)}</option>`));s.dataset.done=1}
let ordersLoadPromise=null;
let ordersPage=1;
const ORDERS_PAGE_SIZE=20;

function renderOrdersPagination(meta){
  const host=document.getElementById("orders-pagination"); if(!host)return;
  const pages=Math.max(1,Number(meta&&meta.pages)||1), current=Math.min(pages,Math.max(1,Number(meta&&meta.page)||1));
  if(pages<=1){host.innerHTML="";return;}
  host.innerHTML='<button type="button" class="btn btn-secondary btn-sm" data-orders-page="prev" '+(current<=1?'disabled':'')+'>السابق</button><span class="pagination-info">صفحة '+current+' من '+pages+'</span><button type="button" class="btn btn-secondary btn-sm" data-orders-page="next" '+(current>=pages?'disabled':'')+'>التالي</button>';
  const prev=host.querySelector('[data-orders-page="prev"]'), next=host.querySelector('[data-orders-page="next"]');
  prev&&prev.addEventListener('click',()=>{ordersPage=Math.max(1,current-1);loadOrders();});
  next&&next.addEventListener('click',()=>{ordersPage=Math.min(pages,current+1);loadOrders();});
}
function loadOrders(){
  if(ordersLoadPromise)return ordersLoadPromise;
  ordersLoadPromise=(async()=>{
    populateStatus();
    const q=document.getElementById("orders-search").value.trim(), s=document.getElementById("orders-status-filter").value, f=document.getElementById("orders-date-from").value, t=document.getElementById("orders-date-to").value;
    const p=new URLSearchParams(); if(q)p.set("q",q); if(s)p.set("status",s); if(f)p.set("date_from",f); if(t)p.set("date_to",t); p.set("page",String(ordersPage)); p.set("page_size",String(ORDERS_PAGE_SIZE));
    try{
      const d=await apiFetch('/api/orders?'+p.toString());
      renderOrders(d.orders||[]);
      document.getElementById("orders-count").textContent='عدد النتائج: '+d.count+' — صفحة '+d.page+' من '+d.pages;
      renderOrdersPagination(d); return d;
    }catch(e){toast(e.message,"error");throw e;}finally{ordersLoadPromise=null;}
  })(); return ordersLoadPromise;
}

function bindImagePreview(row){
  const input=row.querySelector('.product-image');
  const preview=row.querySelector('.image-preview');
  let objectUrl=null;
  input.onchange=()=>{
    if(objectUrl)URL.revokeObjectURL(objectUrl);
    preview.innerHTML='';
    const file=input.files?.[0];
    if(!file)return;
    objectUrl=URL.createObjectURL(file);
    const img=document.createElement('img');
    img.className='product-thumb';
    img.alt='معاينة';
    img.src=objectUrl;
    preview.appendChild(img);
  };
}
function addProductRow(name="",qty=1){const wrap=document.getElementById("product-items"),idx=wrap.children.length+1,div=document.createElement("div");div.className="product-row";div.innerHTML=`<div class="product-number">${idx}</div><input class="product-name" type="text" placeholder="اسم المنتج" value="${esc(name)}"><input class="product-qty" type="number" min="1" value="${qty}"><div class="product-image-cell"><label class="image-upload-btn">📷 صورة المنتج<input class="product-image" type="file" accept="image/jpeg,image/png,image/webp" hidden></label><div class="image-preview"></div></div><button type="button" class="remove-product" title="حذف المنتج">✕</button>`;div.querySelectorAll("input").forEach(x=>x.addEventListener("input",updateProductTotals));div.querySelector(".remove-product").onclick=()=>{div.remove();renumberProducts();if(!document.querySelectorAll(".product-row").length)addProductRow();updateProductTotals()};wrap.appendChild(div);bindImagePreview(div);updateProductTotals()}
function renumberProducts(){document.querySelectorAll(".product-row").forEach((r,i)=>r.querySelector(".product-number").textContent=i+1)}
function updateProductTotals(){const rows=[...document.querySelectorAll(".product-row")];document.getElementById("products-count").textContent=rows.length;document.getElementById("products-total").textContent=rows.reduce((n,r)=>n+(parseInt(r.querySelector(".product-qty").value)||0),0)}
function productsPayload(){return [...document.querySelectorAll(".product-row")].map(r=>({product_name:r.querySelector(".product-name").value.trim(),quantity:parseInt(r.querySelector(".product-qty").value)||0}))}
async function uploadOrderImages(order,files){let uploaded=0,failed=0;for(let i=0;i<files.length;i++){const file=files[i];if(!file)continue;const item=order.Items?.[i];if(!item?.Item_ID){failed++;continue}const fd=new FormData();fd.append('image',file);try{await apiFetch(`/api/orders/${order.Order_ID}/items/${item.Item_ID}/image`,{method:'POST',body:fd});uploaded++}catch(e){failed++;toast(`تعذر حفظ صورة المنتج رقم ${i+1}: ${e.message}`,'error')}}return {uploaded,failed}}

let shortageOrders=[];
function buildShortageMessage(selected,mode='orders'){
  const orders=selected||[]; const pharmacy='صيدلية عز الصحة';
  let body='';
  if(mode==='grouped'){
    const grouped={}; orders.forEach(o=>(o.Shortage_Items||((o.Items||[]).filter(i=>i.Availability_Status==='بانتظار التوفر'))||[]).forEach(i=>{const k=String(i.Product_Name||'').trim().toLowerCase();const r=grouped[k]||(grouped[k]={name:i.Product_Name,qty:0,orders:0});r.qty+=Number(i.Quantity)||0;r.orders++;}));
    body=Object.values(grouped).sort((a,b)=>b.qty-a.qty).map((x,i)=>`${i+1}. ${x.name} — إجمالي المطلوب: ${x.qty} (${x.orders} طلب)`).join('\n');
  }else{
    body=orders.map(o=>`• ${o.Customer_Name} — ${o.Order_ID}\\n${(o.Shortage_Items||((o.Items||[]).filter(i=>i.Availability_Status==='بانتظار التوفر'))||[]).map(i=>`  - ${i.Product_Name} × ${i.Quantity}`).join('\n')}`).join('\n');
  }
  const template=messageTemplates.Message_Template_Shortage||'📦 نواقص العملاء – {اسم_الصيدلية}\nالتاريخ: {التاريخ}\n\n{النواقص}\n\nفضلاً توفير الكميات أعلاه عند الإمكان.\n{الشعار} 💙';
  return template.replaceAll('{اسم_الصيدلية}',pharmacy).replaceAll('{التاريخ}',todayISO()).replaceAll('{النواقص}',body||'لا توجد نواقص مسجلة حاليًا ✅').replaceAll('{الشعار}','رعاية من القلب');
}
function renderShortageOrders(){const c=document.getElementById('shortages-orders-list');if(!shortageOrders.length){c.innerHTML='<div class="empty-state">لا توجد طلبات ناقصة حاليًا ✅</div>';document.getElementById('shortages-message').value=buildShortageMessage([],document.getElementById('shortages-mode').value);return}c.innerHTML=shortageOrders.map((o,i)=>`<label class="shortage-order"><input type="checkbox" class="shortage-check" data-index="${i}" checked><div><b>${esc(o.Customer_Name)}</b><span>${esc(o.Order_ID)}</span><div class="fi-meta">${(o.Shortage_Items||((o.Items||[]).filter(i=>i.Availability_Status==='بانتظار التوفر'))||[]).map(x=>`${esc(x.Product_Name)} × ${x.Quantity}`).join('<br>')}</div></div></label>`).join('');c.querySelectorAll('.shortage-check').forEach(x=>x.onchange=updateShortageMessage);updateShortageMessage()}
function selectedShortageOrders(){return [...document.querySelectorAll('.shortage-check:checked')].map(x=>shortageOrders[Number(x.dataset.index)]).filter(Boolean)}
function updateShortageMessage(){document.getElementById('shortages-message').value=buildShortageMessage(selectedShortageOrders(),document.getElementById('shortages-mode').value)}
async function loadShortages(){try{if(!Object.keys(messageTemplates).length)await loadMessageTemplates();const d=await apiFetch('/api/whatsapp/shortages');shortageOrders=d.orders||[];document.getElementById('shortages-summary').textContent=d.count?`يوجد ${d.count} طلبات بها نواقص`:'لا توجد نواقص حاليًا ✅';renderShortageOrders()}catch(e){toast(e.message,'error')}}
function selectAllShortages(v){document.querySelectorAll('.shortage-check').forEach(x=>x.checked=v);updateShortageMessage()}
function copyShortages(){const msg=document.getElementById('shortages-message').value;if(!msg)return;navigator.clipboard?.writeText(msg).then(()=>toast('تم نسخ رسالة النواقص')).catch(()=>{document.getElementById('shortages-message').select();document.execCommand('copy');toast('تم نسخ رسالة النواقص')})}
async function openShortagesWhatsApp(){try{const d=await apiFetch('/api/whatsapp/open-shortages',{method:'POST',body:JSON.stringify({})});openWhatsAppOnThisDevice(d.url,d.web_url);toast('تم تجهيز WhatsApp على جهازك')}catch(e){toast(e.message,'error')}}
async function loadWaCustomers(){const c=document.getElementById("wa-customers-list");if(!c)return;try{const d=await apiFetch("/api/followups/today");const available=(d.followups||[]).filter(x=>x._followup_kind==='needs_call');if(!available.length){c.innerHTML='<div class="empty-state">لا توجد طلبات متوفرة تحتاج التواصل حاليًا.</div>';return}c.innerHTML=available.map(o=>`<div class="wa-customer-row"><div><strong>${esc(o.Customer_Name)}</strong><div class="fi-meta">${productsSummary(o)}<br>${esc(o.Phone)}</div></div><div class="wa-row-actions"><button class="btn btn-outline btn-sm wa-client-btn" data-id="${esc(o.Order_ID)}">💬 إرسال الرسالة</button><button class="btn btn-secondary btn-sm wa-copy-client" data-id="${esc(o.Order_ID)}">📋 نسخ</button></div></div>`).join("");c.querySelectorAll('.wa-client-btn').forEach(b=>b.onclick=()=>openClientWhatsApp(b.dataset.id));c.querySelectorAll('.wa-copy-client').forEach(b=>b.onclick=()=>copyClientMessage(b.dataset.id))}catch(e){c.innerHTML='<div class="empty-state">تعذر تحميل العملاء</div>';toast(e.message,"error")}}
async function openClientWhatsApp(id){try{const d=await apiFetch(`/api/whatsapp/open/${id}`,{method:"POST",body:JSON.stringify({})});openWhatsAppOnThisDevice(d.url,d.web_url);toast("تم تجهيز WhatsApp على جهازك")}catch(e){toast(e.message,"error")}}
async function copyClientMessage(id){try{const d=await apiFetch(`/api/whatsapp/order/${id}`);await navigator.clipboard.writeText(d.message);toast("تم نسخ رسالة العميل")}catch(e){toast(e.message,"error")}}
async function importLegacyData(file){
  if(!file)return;
  const confirmed=window.confirm(`سيتم استبدال بيانات النظام الحالية ببيانات الملف:\n\n${file.name}\n\nسيتم أولًا إنشاء نسخة احتياطية تلقائية من الحالة الحالية. هل تريد المتابعة؟`);
  if(!confirmed)return;
  const fd=new FormData(); fd.append("file",file);
  const btn=document.getElementById("import-data-btn");
  btn.disabled=true;
  try{
    const d=await apiFetch("/api/import-data",{method:"POST",body:fd});
    toast(`تم الاستيراد بنجاح — ${d.order_count||0} طلب`);
    document.getElementById("import-data-file").value="";
    refresh(); loadBackups();
  }catch(e){toast(e.message,"error")}finally{btn.disabled=false}
}
function initNewOrder(){const form=document.getElementById("new-order-form");addProductRow();document.getElementById("add-product-btn").onclick=()=>addProductRow();form.addEventListener("reset",()=>setTimeout(()=>{document.getElementById("product-items").innerHTML="";addProductRow();form.querySelector('[name="order_date"]').value=todayISO();document.getElementById("new-order-success").textContent=""},0));form.addEventListener("submit",async e=>{e.preventDefault();const rows=[...document.querySelectorAll('.product-row')];const products=productsPayload();const imageFiles=rows.map(r=>r.querySelector('.product-image')?.files?.[0]||null);if(products.some(p=>!p.product_name||p.quantity<1)){document.querySelector('[data-for="products"]').textContent="أدخل اسم المنتج والكمية لكل منتج";return}document.querySelector('[data-for="products"]').textContent="";const btn=form.querySelector("button[type=submit]");btn.disabled=true;try{const d=await apiFetch("/api/orders",{method:"POST",body:JSON.stringify({customer_name:form.customer_name.value.trim(),phone:form.phone.value.trim(),products,order_date:form.order_date.value,notes:form.notes.value.trim()})});const uploadResult=await uploadOrderImages(d.order,imageFiles);document.getElementById("new-order-success").textContent=`تم حفظ الطلب بنجاح — رقم الطلب: ${d.order.Order_ID}`;toast(uploadResult.failed?`تم حفظ الطلب، لكن تعذر حفظ ${uploadResult.failed} صورة`:"تم إضافة الطلب والصور بنجاح");form.reset();}catch(e){toast(e.message,"error")}finally{btn.disabled=false}})}
async function loadMessageTemplates(){
  try{
    const d=await apiFetch("/api/message-templates");
    const t=d.templates||{}; messageTemplates=t;
    document.getElementById("tpl-price-confirmation").value=t.Message_Template_Price_Confirmation||"";document.getElementById("tpl-available").value=t.Message_Template_Available||"";
    document.getElementById("tpl-partial").value=t.Message_Template_Partial||"";
    document.getElementById("tpl-unavailable").value=t.Message_Template_Unavailable||"";
    document.getElementById("tpl-shortage").value=t.Message_Template_Shortage||"";
    document.getElementById("message-templates-status").textContent="";
  }catch(e){toast(e.message,"error")}
}
async function saveMessageTemplates(){
  const data={Message_Template_Price_Confirmation:document.getElementById("tpl-price-confirmation").value,Message_Template_Available:document.getElementById("tpl-available").value,Message_Template_Partial:document.getElementById("tpl-partial").value,Message_Template_Unavailable:document.getElementById("tpl-unavailable").value,Message_Template_Shortage:document.getElementById("tpl-shortage").value};
  try{await apiFetch("/api/message-templates",{method:"PUT",body:JSON.stringify(data)});document.getElementById("message-templates-status").textContent="تم حفظ قوالب الرسائل بنجاح ✅";toast("تم حفظ قوالب الرسائل");}catch(e){toast(e.message,"error")}
}
async function resetMessageTemplates(){
  if(!confirm("استعادة نصوص الرسائل الأصلية؟"))return;
  try{const d=await apiFetch("/api/message-templates/reset",{method:"POST",body:"{}"});const t=d.templates||{};document.getElementById("tpl-price-confirmation").value=t.Message_Template_Price_Confirmation||"";document.getElementById("tpl-available").value=t.Message_Template_Available||"";document.getElementById("tpl-partial").value=t.Message_Template_Partial||"";document.getElementById("tpl-unavailable").value=t.Message_Template_Unavailable||"";document.getElementById("tpl-shortage").value=t.Message_Template_Shortage||"";toast("تمت استعادة النصوص الأصلية");}catch(e){toast(e.message,"error")}
}
function refresh(){loadDashboard();if(document.getElementById("view-orders").classList.contains("active"))loadOrders()}
function initModals(){
  const availabilityModal=document.getElementById('availability-modal');
  const orderModal=document.getElementById('order-modal');
  document.getElementById('availability-close-btn').onclick=()=>closeAvailability(true);
  document.getElementById('availability-cancel-btn').onclick=()=>closeAvailability(true);
  document.getElementById('availability-save-btn').onclick=saveAvailability;
  document.getElementById("modal-close-btn").onclick=()=>{orderModal.classList.add("hidden");orderModal.setAttribute('aria-hidden','true')};
  document.getElementById("postpone-close-btn").onclick=()=>document.getElementById("postpone-modal").classList.add("hidden");
  document.getElementById("confirm-no-btn").onclick=()=>document.getElementById("confirm-modal").classList.add("hidden");
  document.getElementById("confirm-yes-btn").onclick=async()=>{document.getElementById("confirm-modal").classList.add("hidden");if(confirmCallback){const cb=confirmCallback;confirmCallback=null;await cb()}};
  document.getElementById("postpone-custom-confirm").onclick=()=>{const d=document.getElementById("postpone-custom-date").value;if(!d)return toast("اختر تاريخًا", "error");doPostpone(null,d)};
  document.querySelectorAll(".postpone-quick").forEach(b=>b.onclick=()=>doPostpone(parseInt(b.dataset.days)));
  availabilityModal.onclick=e=>{if(e.target===availabilityModal)closeAvailability(true)};
  document.querySelectorAll(".modal-overlay").forEach(o=>{if(o===availabilityModal)return;o.onclick=e=>{if(e.target===o)o.classList.add("hidden")}});
}
async function loadBackups(){
  const root=document.getElementById("backups-list");
  if(!root){console.error("backups-list element is missing");return;}
  try{
    const d=await apiFetch("/api/backups");
    const rows=Array.isArray(d?.backups)?d.backups:[];
    if(!rows.length){root.innerHTML='<div class="empty-state">لا توجد نسخ احتياطية حاليًا</div>';return;}
    root.innerHTML=rows.map(x=>`<div class="backup-row"><div><strong>${esc(x.filename)}</strong><div class="fi-meta">${esc(x.created_at)} — ${esc(x.reason||"")} — ${esc(x.size_kb??0)} KB</div></div><button type="button" class="btn btn-outline btn-sm restore-btn" data-file="${esc(x.filename)}">استعادة</button></div>`).join("");
    root.querySelectorAll(".restore-btn").forEach(btn=>btn.onclick=()=>openConfirm(`استعادة النسخة ${btn.dataset.file}؟ سيتم حفظ نسخة تلقائية من الحالة الحالية أولًا.`,async()=>{try{await apiFetch("/api/backups/restore",{method:"POST",body:JSON.stringify({filename:btn.dataset.file})});toast("تمت الاستعادة");refresh();loadBackups()}catch(e){toast(e.message,"error")}}));
  }catch(e){console.error("loadBackups failed",e);root.innerHTML='<div class="empty-state">تعذر تحميل النسخ الاحتياطية حاليًا.</div>';toast(e.message,"error");}
}
function initOrders(){let t;document.getElementById("orders-search").oninput=()=>{clearTimeout(t);t=setTimeout(()=>{ordersPage=1;loadOrders()},300)};document.getElementById("orders-status-filter").onchange=()=>{ordersPage=1;loadOrders()};document.getElementById("orders-date-from").onchange=()=>{ordersPage=1;loadOrders()};document.getElementById("orders-date-to").onchange=()=>{ordersPage=1;loadOrders()};document.getElementById("orders-clear-filters").onclick=()=>{document.getElementById("orders-search").value="";document.getElementById("orders-status-filter").value="";document.getElementById("orders-date-from").value="";document.getElementById("orders-date-to").value="";ordersPage=1;loadOrders()}}
async function resetAllData(){
  const first=window.prompt("تحذير: سيُحذف كل الطلبات والصور والنسخ الاحتياطية. اكتب العبارة التالية للتأكيد:\n\nحذف كل البيانات");
  if(first!=="حذف كل البيانات"){ toast("تم إلغاء العملية"); return; }
  const second=window.confirm("تأكيد نهائي: لا يمكن التراجع عن مسح كل البيانات بعد التنفيذ. هل تريد المتابعة؟");
  if(!second) return;
  try{await apiFetch("/api/data/reset",{method:"POST",body:JSON.stringify({confirmation:first})}); dashboardFilterKey=null; toast("تم حذف جميع البيانات وإعادة النظام لحالة نظيفة"); await loadDashboard(); await loadOrders(); loadBackups();}catch(e){toast(e.message,"error")}
}

document.addEventListener("DOMContentLoaded",()=>{initNav();initModals();initOrders();initNewOrder();document.getElementById("create-backup-btn").onclick=async()=>{try{await apiFetch("/api/backups",{method:"POST",body:"{}"});toast("تم إنشاء النسخة الاحتياطية");loadBackups()}catch(e){toast(e.message,"error")}};document.getElementById("reset-all-data-btn")?.addEventListener("click",resetAllData);
 document.getElementById("import-data-btn")?.addEventListener("click",()=>document.getElementById("import-data-file")?.click());
 document.getElementById("import-data-file")?.addEventListener("change",e=>importLegacyData(e.target.files?.[0]));
 
 document.getElementById("dashboard-results-search")?.addEventListener("input",()=>renderDashboardResults());document.getElementById("dashboard-contact-filter")?.addEventListener("change",()=>renderDashboardResults());document.getElementById("dashboard-results-close")?.addEventListener("click",()=>{dashboardFilterKey=null;closeDashboardResults();renderDashboardCards(window.dashboardStats||{})});document.getElementById("dashboard-search").oninput=e=>{clearTimeout(window._s);window._s=setTimeout(()=>loadFollowups(e.target.value.trim()),250)};document.getElementById("refresh-shortages-btn")?.addEventListener("click",loadShortages);document.getElementById("shortages-select-all")?.addEventListener("click",()=>selectAllShortages(true));document.getElementById("shortages-clear-all")?.addEventListener("click",()=>selectAllShortages(false));document.getElementById("shortages-mode")?.addEventListener("change",updateShortageMessage);document.getElementById("copy-shortages-btn")?.addEventListener("click",copyShortages);document.getElementById("open-wa-group-btn")?.addEventListener("click",openShortagesWhatsApp);document.getElementById("refresh-wa-customers-btn")?.addEventListener("click",loadWaCustomers);document.getElementById("message-templates-save")?.addEventListener("click",saveMessageTemplates);document.getElementById("message-templates-reset")?.addEventListener("click",resetMessageTemplates);loadDashboard();});
