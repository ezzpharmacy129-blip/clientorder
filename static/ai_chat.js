(function(){
  const root=document.getElementById("ezz-ai-side-chat"); if(!root) return;
  const panel=root.querySelector(".ezz-ai-panel"), toggle=root.querySelector(".ezz-ai-toggle"), close=root.querySelector(".ezz-ai-close");
  const box=root.querySelector(".ezz-ai-messages"), form=root.querySelector(".ezz-ai-form"), input=root.querySelector(".ezz-ai-input"), send=root.querySelector(".ezz-ai-send");
  const history=[];
  function add(text,kind){const d=document.createElement("div");d.className="ezz-ai-msg "+kind;d.textContent=text;box.appendChild(d);box.scrollTop=box.scrollHeight;return d}
  function addConfirmation(d){
    const wrap=document.createElement("div"); wrap.className="ezz-ai-confirm";
    const text=document.createElement("div"); text.className="ezz-ai-confirm-text"; text.textContent="هل أنت متأكد من العملية التالية؟\n\n"+d.action_label;
    const yes=document.createElement("button"); yes.type="button"; yes.className="ezz-ai-confirm-yes"; yes.textContent="✅ نعم، نفّذ العملية";
    const no=document.createElement("button"); no.type="button"; no.className="ezz-ai-confirm-no"; no.textContent="❌ إلغاء";
    wrap.append(text,yes,no);box.appendChild(wrap);box.scrollTop=box.scrollHeight;
    yes.onclick=async()=>{
      yes.disabled=true;no.disabled=true;text.textContent="جاري تنفيذ العملية...";
      try{
        const x=await window.apiFetch("/api/ai/execute",{method:"POST",body:JSON.stringify({confirmation_token:d.confirmation_token})});
        text.textContent=x.answer||"تم تنفيذ العملية بنجاح ✅";
      }catch(e){text.textContent=e.message}
    };
    no.onclick=()=>{yes.disabled=true;no.disabled=true;text.textContent="تم إلغاء العملية ✅"};
  }
  function remember(role,content){history.push({role,content});if(history.length>12)history.splice(0,history.length-12)}
  async function ask(q){q=(q||"").trim();if(!q)return;add(q,"user");remember("user",q);input.value="";send.disabled=true;const wait=add("جاري قراءة النظام...","bot");
    try{
      const d=await window.apiFetch("/api/ai/chat",{method:"POST",body:JSON.stringify({message:q,history:history.slice(0,-1),page:location.pathname})});
      if(d.confirmation_required){wait.remove();add(d.answer||"قبل تنفيذ العملية التالية، يرجى تأكيدها.","bot");addConfirmation(d);remember("assistant",d.answer||"");}
      else {wait.textContent=d.answer||"لم تصل نتيجة.";remember("assistant",d.answer||"");}
    }catch(e){wait.textContent=e.message}
    finally{send.disabled=false;input.focus()}
  }
  toggle.onclick=()=>{panel.classList.toggle("open");if(panel.classList.contains("open"))setTimeout(()=>input.focus(),100)};
  close.onclick=()=>panel.classList.remove("open");
  form.addEventListener("submit",e=>{e.preventDefault();ask(input.value)});
  root.querySelectorAll("[data-ai-q]").forEach(b=>b.onclick=()=>ask(b.dataset.aiQ));
  input.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();form.requestSubmit()}});
})();