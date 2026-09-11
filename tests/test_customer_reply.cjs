const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.join(__dirname,'..');
const context=vm.createContext({});
for(const name of ['core.js','customer_reply.js'])vm.runInContext(fs.readFileSync(path.join(root,'static',name),'utf8'),context);
const order={Order_ID:'ORD-1',Status:'تم التواصل - بانتظار الاستلام',Contact_Status:'بانتظار رد العميل',Items:[
  {Item_ID:'I1',Product_Name:'<img onerror=bad>',Availability_Status:'متوفر'},
  {Item_ID:'I2',Product_Name:'Pending',Availability_Status:'بانتظار التوفر'},
  {Item_ID:'I3',Product_Name:'Unavailable',Availability_Status:'غير متوفر'},
  {Item_ID:'I4',Product_Name:'Rejected',Availability_Status:'متوفر',Customer_Decision:'rejected'}]};
const html=context.customerReplyPanel(order);
assert.ok(html.includes('تسجيل رد العميل'));
assert.ok(html.includes('&lt;img'));
assert.ok(!html.includes('<img'));
assert.ok(!html.includes('value="I2"')&&!html.includes('value="I4"'));
const payload=context.customerReplyPayload(order,'العميل رفض',' reason ',['I1']);
assert.equal(payload.note,'reason');assert.equal(payload.rejected_item_ids[0],'I1');
assert.throws(()=>context.customerReplyPayload(order,'العميل رفض','',[]));
assert.throws(()=>context.customerReplyPayload(order,'العميل رفض','',['I2']));
assert.throws(()=>context.customerReplyPayload(order,'العميل رفض','',['OTHER']));
assert.throws(()=>context.customerReplyPayload(order,'','',[]));
assert.equal(context.customerReplyPayload(order,'العميل موافق','',[]).rejected_item_ids.length,0);
const unavailable={...order,Items:[order.Items[2]]};
assert.throws(()=>context.customerReplyPayload(unavailable,'العميل موافق','',[]));
for(const status of ['تم الاستلام','ملغي']){
  assert.equal(context.customerReplyPanel({...order,Status:status}),'');
  assert.throws(()=>context.customerReplyPayload({...order,Status:status},'العميل موافق','',[]));
}
// Exercise the real save handler, including CSRF-aware apiFetch delegation and refresh.
(async()=>{
  const handlers={},button={disabled:false},error={textContent:''};
  const choice={value:'العميل موافق',addEventListener:(event,fn)=>handlers.change=fn};
  const rejected={hidden:true,querySelectorAll:()=>[]};
  button.addEventListener=(event,fn)=>handlers.save=fn;
  const elements={'#customer-reply-choice':choice,'#customer-reply-rejected':rejected,
    '#save-customer-reply':button,'#customer-reply-error':error,'#customer-reply-note':{value:'Test'}};
  context.document={querySelector:()=>({querySelector:key=>elements[key]})};
  let calls=[],refreshed=0,opened=[];
  context.setButtonLoading=(b,v)=>b.disabled=v;
  context.apiFetch=async(url,options)=>calls.push([url,JSON.parse(options.body)]);
  context.toast=()=>{};context.refresh=()=>refreshed++;context.details=async id=>opened.push(id);
  context.bindCustomerReply(order);await handlers.save();
  assert.equal(calls[0][0],'/api/orders/ORD-1/contact-status');
  assert.equal(calls[0][1].contact_status,'العميل موافق');
  assert.equal(refreshed,1);assert.equal(opened[0],'ORD-1');assert.equal(button.disabled,false);
  context.apiFetch=async()=>{throw Error('Rejected by server');};await handlers.save();
  assert.equal(error.textContent,'Rejected by server');assert.equal(refreshed,1);assert.equal(button.disabled,false);
  console.log('Customer reply UI, payload and request regression checks passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
