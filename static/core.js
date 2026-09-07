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

/* P3.3: load the order-details visual layer without changing application logic. */
(function loadP33OrderDetailsStyles(){
  if(typeof document==="undefined") return;
  const install=()=>{
    if(document.querySelector('link[data-ezz-style="p3-3-order-details"]')) return;
    const link=document.createElement("link");
    link.rel="stylesheet";
    link.href="/static/p3_3_order_details.css?v=20260907-p33";
    link.dataset.ezzStyle="p3-3-order-details";
    document.head.appendChild(link);
  };
  if(document.head) install();
  else document.addEventListener("DOMContentLoaded",install,{once:true});
})();

/* P3.4: load the mobile orders presentation layer without changing application logic. */
(function loadP34OrdersMobileStyles(){
  if(typeof document==="undefined") return;
  const install=()=>{
    if(document.querySelector('link[data-ezz-style="p3-4-orders-mobile"]')) return;
    const link=document.createElement("link");
    link.rel="stylesheet";
    link.href="/static/p3_4_orders_mobile.css?v=20260907-p34";
    link.dataset.ezzStyle="p3-4-orders-mobile";
    document.head.appendChild(link);
  };
  if(document.head) install();
  else document.addEventListener("DOMContentLoaded",install,{once:true});
})();

/* P3.5: load the dashboard mobile presentation layer without changing application logic. */
(function loadP35DashboardMobileStyles(){
  if(typeof document==="undefined") return;
  const install=()=>{
    if(document.querySelector('link[data-ezz-style="p3-5-dashboard-mobile"]')) return;
    const link=document.createElement("link");
    link.rel="stylesheet";
    link.href="/static/p3_5_dashboard_mobile.css?v=20260907-p35";
    link.dataset.ezzStyle="p3-5-dashboard-mobile";
    document.head.appendChild(link);
  };
  if(document.head) install();
  else document.addEventListener("DOMContentLoaded",install,{once:true});
})();

/* P3.6: load the mobile header/navigation presentation layer without changing application logic. */
(function loadP36MobileHeaderStyles(){
  if(typeof document==="undefined") return;
  const install=()=>{
    if(document.querySelector('link[data-ezz-style="p3-6-mobile-header"]')) return;
    const link=document.createElement("link");
    link.rel="stylesheet";
    link.href="/static/p3_6_mobile_header.css?v=20260907-p36";
    link.dataset.ezzStyle="p3-6-mobile-header";
    document.head.appendChild(link);
  };
  if(document.head) install();
  else document.addEventListener("DOMContentLoaded",install,{once:true});
})();

/* P3.7: load the new-order mobile presentation layer without changing application logic. */
(function loadP37NewOrderMobileStyles(){
  if(typeof document==="undefined") return;
  const install=()=>{
    if(document.querySelector('link[data-ezz-style="p3-7-new-order-mobile"]')) return;
    const link=document.createElement("link");
    link.rel="stylesheet";
    link.href="/static/p3_7_new_order_mobile.css?v=20260907-p37";
    link.dataset.ezzStyle="p3-7-new-order-mobile";
    document.head.appendChild(link);
  };
  if(document.head) install();
  else document.addEventListener("DOMContentLoaded",install,{once:true});
})();
