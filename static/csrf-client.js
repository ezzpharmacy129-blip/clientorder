(function(){
  "use strict";

  async function fetchCurrentCsrfToken(){
    const r=await fetch('/api/auth/csrf',{
      method:'GET',
      credentials:'same-origin',
      cache:'no-store',
      headers:{'Accept':'application/json'}
    });
    if(!r.ok) throw new Error('تعذر الحصول على رمز الحماية');
    const d=await r.json();
    if(!d.csrf_token) throw new Error('رمز الحماية غير متاح');
    const meta=document.querySelector('meta[name="csrf-token"]');
    if(meta) meta.content=d.csrf_token;
    return d.csrf_token;
  }

  async function getCsrfToken(){
    return fetchCurrentCsrfToken();
  }

  async function csrfFetch(url, options){
    const opts={...(options||{}),credentials:(options&&options.credentials)||'same-origin'};
    const method=String(opts.method||'GET').toUpperCase();
    if(["GET","HEAD","OPTIONS"].includes(method)) return fetch(url,opts);

    let token=await fetchCurrentCsrfToken();
    let headers={...(opts.headers||{}),"X-CSRF-Token":token};
    let response=await fetch(url,{...opts,headers});

    if(response.status===403){
      let payload=null;
      try{payload=await response.clone().json()}catch(_e){}
      if(payload?.code==="csrf_failed"){
        token=await fetchCurrentCsrfToken();
        response=await fetch(url,{
          ...opts,
          headers:{...(opts.headers||{}),"X-CSRF-Token":token}
        });
      }
    }
    return response;
  }

  window.ezzCsrf={getToken:getCsrfToken,fetch:csrfFetch};
})();