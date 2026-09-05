(function(){
  const root=document.getElementById("ezz-ai-side-chat"); if(!root) return;
  const panel=root.querySelector(".ezz-ai-panel"), toggle=root.querySelector(".ezz-ai-toggle"), close=root.querySelector(".ezz-ai-close");
  const box=root.querySelector(".ezz-ai-messages"), form=root.querySelector(".ezz-ai-form"), input=root.querySelector(".ezz-ai-input"), send=root.querySelector(".ezz-ai-send");
  const history=[];
  function add(text,kind){const d=document.createElement("div");d.className="ezz-ai-msg "+kind;d.textContent=text;box.appendChild(d);box.scrollTop=box.scrollHeight;return d}
  function remember(role,content){history.push({role,content});if(history.length>12)history.splice(0,history.length-12)}
  async function ask(q){q=(q||"").trim();if(!q)return;add(q,"user");remember("user",q);input.value="";send.disabled=true;const wait=add("جاري قراءة النظام...","bot");
    try{
      const r=await fetch("/api/ai/chat",{method:"POST",headers:{"Content-Type":"application/json"},credentials:"same-origin",body:JSON.stringify({message:q,history:history.slice(0,-1),page:location.pathname})});
      const d=await r.json();if(!r.ok)throw new Error(d.error||"تعذر الاتصال بالمساعد");
      wait.textContent=d.answer||"لم تصل نتيجة.";remember("assistant",d.answer||"");
    }catch(e){wait.textContent=e.message}
    finally{send.disabled=false;input.focus()}
  }
  toggle.onclick=()=>{panel.classList.toggle("open");if(panel.classList.contains("open"))setTimeout(()=>input.focus(),100)};
  close.onclick=()=>panel.classList.remove("open");
  form.addEventListener("submit",e=>{e.preventDefault();ask(input.value)});
  root.querySelectorAll("[data-ai-q]").forEach(b=>b.onclick=()=>ask(b.dataset.aiQ));
  input.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();form.requestSubmit()}});
})();