(function(){
  "use strict";
  async function getCsrfToken(){
    const meta=document.querySelector('meta[name="csrf-token"]');
    if(meta?.content) return meta.content;
    const r=await fetch('/api/auth/csrf',{method:'GET',credentials:'same-origin',cache:'no-store'});
    if(!r.ok) throw new Error('تعذر الحصول على رمز الحماية');
    const d=await r.json();
    if(!d.csrf_token) throw new Error('رمز الحماية غير متاح');
    return d.csrf_token;
  }

  async function csrfFetch(url, options){
    const opts={...(options||{}),credentials:(options&&options.credentials)||'same-origin'};
    const method=String(opts.method||'GET').toUpperCase();
    if(["GET","HEAD","OPTIONS"].includes(method)) return fetch(url,opts);

    let token=await getCsrfToken();
    const headers={...(opts.headers||{}),"X-CSRF-Token":token};
    let response=await fetch(url,{...opts,headers});

    if(response.status===403){
      let payload=null;
      try{payload=await response.clone().json()}catch(_e){}
      if(payload?.code==="csrf_failed"){
        const meta=document.querySelector('meta[name="csrf-token"]');
        if(meta) meta.content="";
        token=await getCsrfToken();
        response=await fetch(url,{...opts,headers:{...(opts.headers||{}),"X-CSRF-Token":token}});
      }
    }
    return response;
  }

  window.ezzCsrf={getToken:getCsrfToken,fetch:csrfFetch};
})();