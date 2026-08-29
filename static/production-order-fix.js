/* Production hardening for the new-order form.
   Loaded by sitecustomize so no manual template edits are required. */
(function(){
  const FORM_ID = "new-order-form";
  let failedUploads = [];
  let createdOrderId = "";
  let originalFiles = [];

  function api(url, options){
    const opts = Object.assign({}, options || {});
    opts.headers = Object.assign({}, opts.headers || {});
    if (!(opts.body instanceof FormData)) opts.headers["Content-Type"] = "application/json";
    return fetch(url, opts).then(async r=>{
      let data = null; try { data = await r.json(); } catch(_e) {}
      if(!r.ok){
        const msg = data?.error || (data?.errors ? Object.values(data.errors).join("، ") : "حدث خطأ");
        const err = new Error(msg); err.status = r.status; err.data = data; throw err;
      }
      return data;
    });
  }

  function toastSafe(msg, type){
    if(typeof window.toast === "function") return window.toast(msg, type || "success");
    const el = document.getElementById("toast-container");
    if(el){ const x=document.createElement("div"); x.className=`toast ${type||"success"}`; x.textContent=msg; el.appendChild(x); setTimeout(()=>x.remove(),3500); }
  }

  async function uploadOne(orderId, item, file){
    if(!file || !item?.Item_ID) throw new Error("بيانات الصورة غير مكتملة");
    let last = null;
    for(let attempt=1; attempt<=3; attempt++){
      try{
        const fd = new FormData(); fd.append("image", file);
        await api(`/api/orders/${encodeURIComponent(orderId)}/items/${encodeURIComponent(item.Item_ID)}/image`, {method:"POST", body:fd});
        return true;
      }catch(e){
        last = e;
        if(attempt<3) await new Promise(r=>setTimeout(r, 500*attempt));
      }
    }
    throw last || new Error("تعذر حفظ الصورة");
  }

  function setRetryButton(form){
    let old = document.getElementById("retry-failed-images");
    if(old) old.remove();
    if(!failedUploads.length) return;
    const button = document.createElement("button");
    button.type="button"; button.id="retry-failed-images"; button.className="btn btn-outline";
    button.textContent=`🔄 إعادة محاولة حفظ ${failedUploads.length} صورة`;
    button.onclick=async()=>{
      button.disabled=true;
      const still=[];
      for(const entry of failedUploads){
        try{ await uploadOne(createdOrderId, entry.item, entry.file); }
        catch(e){ still.push(entry); }
      }
      failedUploads=still;
      if(!failedUploads.length){
        toastSafe("تم حفظ جميع صور الطلب بنجاح");
        button.remove();
        form.reset();
        createdOrderId=""; originalFiles=[];
      }else{
        toastSafe(`تعذر حفظ ${failedUploads.length} صورة. يمكنك المحاولة مرة أخرى.`, "error");
        button.disabled=false;
      }
    };
    form.querySelector(".form-actions")?.appendChild(button);
  }

  function install(){
    const form=document.getElementById(FORM_ID);
    if(!form || form.dataset.productionOrderFixInstalled) return;
    form.dataset.productionOrderFixInstalled="1";
    form.addEventListener("submit", async function(e){
      // Capture the submit before the legacy submit handler to avoid duplicate orders.
      e.preventDefault(); e.stopImmediatePropagation();
      const rows=[...form.querySelectorAll(".product-row")];
      const products=rows.map(r=>({product_name:(r.querySelector(".product-name")?.value||"").trim(),quantity:parseInt(r.querySelector(".product-qty")?.value)||0}));
      if(products.some(p=>!p.product_name || p.quantity<1)){
        const er=form.querySelector('[data-for="products"]'); if(er) er.textContent="أدخل اسم المنتج والكمية لكل منتج";
        toastSafe("أكمل بيانات المنتجات قبل الحفظ", "error"); return;
      }
      const imageFiles=rows.map(r=>r.querySelector(".product-image")?.files?.[0]||null);
      const btn=form.querySelector('button[type="submit"]'); if(btn) btn.disabled=true;
      failedUploads=[]; createdOrderId=""; originalFiles=imageFiles.slice();
      try{
        const d=await api("/api/orders",{method:"POST",body:JSON.stringify({
          customer_name:(form.customer_name?.value||"").trim(),
          phone:(form.phone?.value||"").trim(),
          products,
          order_date:form.order_date?.value||"",
          notes:(form.notes?.value||"").trim()
        })});
        createdOrderId=d.order.Order_ID;
        let ok=0;
        for(let i=0;i<imageFiles.length;i++){
          const file=imageFiles[i]; if(!file) continue;
          try{ await uploadOne(createdOrderId, d.order.Items?.[i], file); ok++; }
          catch(e){ failedUploads.push({index:i+1,item:d.order.Items?.[i],file}); }
        }
        if(failedUploads.length){
          document.getElementById("new-order-success").textContent=`تم حفظ الطلب رقم ${createdOrderId}، لكن تعذر حفظ ${failedUploads.length} صورة. الطلب محفوظ ولن يتم إنشاء طلب آخر عند إعادة المحاولة.`;
          toastSafe(`تم حفظ الطلب، وتعذر حفظ ${failedUploads.length} صورة`, "error");
          setRetryButton(form);
          return;
        }
        document.getElementById("new-order-success").textContent=`تم حفظ الطلب بنجاح — رقم الطلب: ${createdOrderId}`;
        toastSafe(imageFiles.some(Boolean)?"تم إضافة الطلب والصور بنجاح":"تم إضافة الطلب بنجاح");
        form.reset(); createdOrderId=""; originalFiles=[];
      }catch(e){
        toastSafe(e.message || "تعذر حفظ الطلب", "error");
      }finally{ if(btn) btn.disabled=false; }
    }, true);
  }

  if(document.readyState === "loading") document.addEventListener("DOMContentLoaded",install);
  else install();
})();
