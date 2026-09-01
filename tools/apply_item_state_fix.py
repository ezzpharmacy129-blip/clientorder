from pathlib import Path
import re

ROOT = Path('.')

def read(name):
    return (ROOT / name).read_text(encoding='utf-8')

def write(name, text):
    (ROOT / name).write_text(text, encoding='utf-8')

def once(text, old, new, label):
    if text.count(old) != 1:
        raise SystemExit(f'{label}: expected one anchor, found {text.count(old)}')
    return text.replace(old, new, 1)

def regex_once(text, pattern, new, label):
    out, n = re.subn(pattern, new, text, count=1, flags=re.M | re.S)
    if n != 1:
        raise SystemExit(f'{label}: expected one match, found {n}')
    return out

# 1) Export/import header contract: preserve the new item-level decision field in backups.
db = read('db.py')
if '"Customer_Decision"]' not in db:
    db = regex_once(
        db,
        r'("Price_Confirmation_Required",\s*"Available_At",\s*"Created_At")\]',
        r'\1, "Customer_Decision"]',
        'db ITEM_HEADERS',
    )
    write('db.py', db)

cloud = read('cloud_db.py')

# 2) Schema migration is additive and idempotent. Existing row data is untouched.
if 'customer_decision TEXT NOT NULL DEFAULT' not in cloud:
    cloud = once(
        cloud,
        "    price_confirmation_required TEXT NOT NULL DEFAULT '',\n    available_at TEXT NOT NULL DEFAULT '',\n    created_at TEXT NOT NULL\n);",
        "    price_confirmation_required TEXT NOT NULL DEFAULT '',\n    available_at TEXT NOT NULL DEFAULT '',\n    created_at TEXT NOT NULL,\n    customer_decision TEXT NOT NULL DEFAULT ''\n);",
        'cloud order_items schema',
    )

cloud = once(
    cloud,
    "            conn.execute(SCHEMA_SQL)\n            rows = conn.execute('SELECT key FROM settings').fetchall()",
    "            conn.execute(SCHEMA_SQL)\n            conn.execute(\"ALTER TABLE order_items ADD COLUMN IF NOT EXISTS customer_decision TEXT NOT NULL DEFAULT ''\")\n            rows = conn.execute('SELECT key FROM settings').fetchall()",
    'cloud additive migration',
)

cloud = once(
    cloud,
    "        'Price_Confirmation_Required': row.get('price_confirmation_required', ''),\n        'Available_At': row.get('available_at', ''),\n        'Created_At': row.get('created_at', ''),\n    }",
    "        'Price_Confirmation_Required': row.get('price_confirmation_required', ''),\n        'Available_At': row.get('available_at', ''),\n        'Created_At': row.get('created_at', ''),\n        'Customer_Decision': row.get('customer_decision', ''),\n    }",
    'cloud item mapper',
)

cloud = once(
    cloud,
    "                    'Price_Confirmation_Required': '', 'Available_At': '', 'Created_At': order.get('Created_At', ''),\n                }]",
    "                    'Price_Confirmation_Required': '', 'Available_At': '', 'Created_At': order.get('Created_At', ''), 'Customer_Decision': '',\n                }]",
    'cloud fallback item',
)

# 3) Make customer decisions item-level and derive the order workflow from active items.
helper = '''\n    def _item_is_rejected(self, order, item):\n        decision = str(item.get('Customer_Decision') or '').strip()\n        if decision == 'rejected':\n            return True\n        # Compatibility for old cancelled/rejected orders: a non-pending item was\n        # already part of the customer decision before item-level decisions existed.\n        if (not decision and order.get('Status') == STATUS_CANCELLED\n                and order.get('Contact_Status') == CONTACT_REJECTED\n                and item.get('Availability_Status') != 'بانتظار التوفر'):\n            return True\n        return False\n\n    def _derive_workflow_status(self, order, items=None):\n        items = items if items is not None else (order.get('Items') or [])\n        active = [i for i in items if not self._item_is_rejected(order, i)]\n        if not active:\n            return STATUS_CANCELLED\n        states = [str(i.get('Availability_Status') or 'بانتظار التوفر').strip() for i in active]\n        if all(x == 'بانتظار التوفر' for x in states):\n            return STATUS_PENDING\n        if all(x == 'متوفر' for x in states):\n            return STATUS_AVAILABLE\n        if all(x == 'غير متوفر' for x in states):\n            return STATUS_UNAVAILABLE\n        return STATUS_PARTIAL\n'''
cloud = once(cloud, "    def _attach_items(self, orders, item_groups):\n", helper + "\n    def _attach_items(self, orders, item_groups):\n", 'cloud workflow helpers')

cloud = once(
    cloud,
    "    def set_availability(self, order_id, item_updates, available_date=None, user='موظف'):\n",
    "__ITEM_STATE_SET_AVAILABILITY_SENTINEL__\n",
    'cloud set_availability start',
)
start = cloud.find('__ITEM_STATE_SET_AVAILABILITY_SENTINEL__')
end = cloud.find("    def mark_available", start)
if end < 0:
    raise SystemExit('cloud set_availability end anchor missing')
new_set_availability = '''    def set_availability(self, order_id, item_updates, available_date=None, user='موظف'):\n        d = available_date or today_str()\n        with self._connect() as conn:\n            current = self._fetch_order(conn, order_id)\n            if not current:\n                return {'error':'الطلب غير موجود','code':404}\n            items = self._fetch_items(conn, order_id)\n            if not items:\n                return {'error':'لا توجد منتجات في هذا الطلب','code':409}\n            updates = {str(x.get('Item_ID')): x for x in (item_updates or []) if x.get('Item_ID')}\n            snapshot = self._snapshot(conn, order_id)\n            for item in items:\n                iid = str(item['Item_ID']); u = updates.get(iid, {})\n                status = str(u.get('availability_status') or item.get('Availability_Status') or 'بانتظار التوفر').strip()\n                if status not in {'متوفر','غير متوفر','بانتظار التوفر'}:\n                    return {'error': f\"حالة توفر غير صحيحة للمنتج {item['Product_Name']}\", 'code':400}\n                reopen = bool(u.get('reopen_customer') in (True,'true','True',1,'1','نعم'))\n                legacy_rejected = (not str(item.get('Customer_Decision') or '').strip()\n                    and current.get('Status') == STATUS_CANCELLED\n                    and current.get('Contact_Status') == CONTACT_REJECTED\n                    and item.get('Availability_Status') != 'بانتظار التوفر')\n                if legacy_rejected and not reopen:\n                    conn.execute(\"UPDATE order_items SET customer_decision='rejected' WHERE item_id=%s\", (iid,))\n                elif reopen:\n                    conn.execute(\"UPDATE order_items SET customer_decision='' WHERE item_id=%s\", (iid,))\n                if status == 'متوفر':\n                    normal_raw = str(u.get('available_price') or item.get('Available_Price') or '').strip()\n                    disc_raw = str(u.get('discounted_price') or item.get('Discounted_Price') or '').strip()\n                    try:\n                        normal = float(normal_raw) if normal_raw else None; disc = float(disc_raw) if disc_raw else None\n                        if (normal is not None and normal < 0) or (disc is not None and disc < 0): raise ValueError\n                        if normal is not None and disc is not None and disc > normal:\n                            return {'error': f\"سعر الخصم لا يمكن أن يكون أعلى من السعر العادي للمنتج {item['Product_Name']}\", 'code':400}\n                    except ValueError:\n                        return {'error': f\"السعر المدخل غير صحيح للمنتج {item['Product_Name']}\", 'code':400}\n                    conn.execute('UPDATE order_items SET availability_status=%s,available_price=%s,discounted_price=%s,unavailable_reason=%s,availability_note=%s,price_confirmation_required=%s,available_at=%s WHERE item_id=%s',\n                                 (status,normal_raw,disc_raw,'',str(u.get('availability_note') or item.get('Availability_Note') or '').strip(),\n                                  'نعم' if u.get('price_confirmation_required') in (True,'true','True',1,'1','نعم') else str(item.get('Price_Confirmation_Required') or ''),d,iid))\n                elif status == 'غير متوفر':\n                    reason = str(u.get('unavailable_reason') or item.get('Unavailable_Reason') or '').strip()\n                    if not reason:\n                        return {'error': f\"يجب اختيار سبب عدم التوفر للمنتج {item['Product_Name']}\", 'code':400}\n                    conn.execute('UPDATE order_items SET availability_status=%s,available_price=%s,discounted_price=%s,unavailable_reason=%s,availability_note=%s,price_confirmation_required=%s,available_at=%s WHERE item_id=%s',\n                                 (status,'','',reason,str(u.get('availability_note') or item.get('Availability_Note') or '').strip(),'','',iid))\n                else:\n                    conn.execute('UPDATE order_items SET availability_status=%s,available_price=%s,discounted_price=%s,unavailable_reason=%s,availability_note=%s,price_confirmation_required=%s,available_at=%s WHERE item_id=%s',\n                                 (status,'','','','','','',iid))\n            fresh = self._fetch_items(conn, order_id)\n            active = [i for i in fresh if not self._item_is_rejected(current, i)]\n            new_status = self._derive_workflow_status(current, fresh)\n            if new_status == STATUS_CANCELLED and any(i.get('Availability_Status') == 'بانتظار التوفر' for i in active):\n                new_status = STATUS_PENDING\n            actionable = [i for i in active if i.get('Availability_Status') in ('متوفر','غير متوفر') and str(i.get('Customer_Decision') or '') not in ('accepted','rejected')]\n            reset_contact = bool(actionable and current.get('Contact_Status') in (CONTACT_REJECTED,CONTACT_ACCEPTED,CONTACT_AWAITING))\n            self._invalidate_undo(conn, order_id)\n            fields = {'Status': new_status, 'Available_Date': d if any(i.get('Availability_Status')=='متوفر' for i in active) else '', 'Next_Followup_Date': today_str() if any(i.get('Availability_Status')=='متوفر' for i in active) else ''}\n            if reset_contact:\n                fields.update({'Contact_Status': CONTACT_NOT_CONTACTED, 'Last_Contact_Date': ''})\n            cmap={'Status':'status','Available_Date':'available_date','Next_Followup_Date':'next_followup_date','Contact_Status':'contact_status','Last_Contact_Date':'last_contact_date'}\n            sets=[]; params=[]\n            for k,v in fields.items(): sets.append(f'{cmap[k]}=%s'); params.append(v)\n            sets.append('updated_at=%s'); params.append(now_str()); params.append(str(order_id))\n            conn.execute(f\"UPDATE orders SET {', '.join(sets)} WHERE order_id=%s\", params)\n            note=[]\n            for i in active:\n                st=i.get('Availability_Status')\n                if st=='متوفر': note.append(f\"{i['Product_Name']}: متوفر\")\n                elif st=='غير متوفر': note.append(f\"{i['Product_Name']}: غير متوفر — {i['Unavailable_Reason']}\")\n                else: note.append(f\"{i['Product_Name']}: بانتظار التوفر\")\n            self._log(conn, order_id, 'تحديث توفر المنتجات', current['Status'], new_status, ' | '.join(note), user)\n            self._add_undo(conn, order_id, 'تحديث توفر المنتجات', snapshot, user)\n            return {'order': self._refresh_order_in_conn(conn, order_id)}\n\n'''
cloud = cloud[:start] + new_set_availability + cloud[end:]

# 4) Item-aware customer contact result. Rejecting one available product no longer closes a request with pending products.
start = cloud.find("    def set_contact_status(self, order_id, contact_status, note='', user='موظف'):")
end = cloud.find("    def mark_pickup", start)
if start < 0 or end < 0:
    raise SystemExit('cloud set_contact_status boundaries missing')
new_set_contact = '''    def set_contact_status(self, order_id, contact_status, note='', user='موظف', rejected_item_ids=None):\n        if contact_status not in ALL_CONTACT_STATUSES:\n            return {'error':'حالة التواصل غير صحيحة','code':400}\n        rejected_item_ids = {str(x) for x in (rejected_item_ids or []) if x}\n        with self._connect() as conn:\n            current=self._fetch_order(conn, order_id)\n            if not current: return {'error':'الطلب غير موجود','code':404}\n            snapshot=self._snapshot(conn, order_id); items=self._fetch_items(conn, order_id)\n            if contact_status == CONTACT_ACCEPTED:\n                if not any(i.get('Availability_Status')=='متوفر' and not self._item_is_rejected(current,i) for i in items):\n                    return {'error':'لا يمكن تسجيل موافقة العميل لأن لا يوجد منتج متوفر في الطلب','code':409}\n                conn.execute(\"UPDATE order_items SET customer_decision='accepted' WHERE order_id=%s AND availability_status='متوفر' AND COALESCE(customer_decision,'')=''\", (str(order_id),))\n            elif contact_status == CONTACT_REJECTED:\n                available_ids={str(i['Item_ID']) for i in items if i.get('Availability_Status')=='متوفر'}\n                if not rejected_item_ids: rejected_item_ids=available_ids\n                invalid=rejected_item_ids-available_ids\n                if invalid: return {'error':'يمكن تسجيل رفض العميل فقط للمنتجات المتوفرة حاليًا','code':400}\n                for iid in rejected_item_ids:\n                    conn.execute(\"UPDATE order_items SET customer_decision='rejected' WHERE item_id=%s AND order_id=%s\", (iid,str(order_id)))\n            fresh=self._fetch_items(conn, order_id); temp=dict(current); temp['Items']=fresh\n            if contact_status == CONTACT_REJECTED:\n                active=[i for i in fresh if not self._item_is_rejected(temp,i)]\n                status=STATUS_CANCELLED if not active else self._derive_workflow_status(temp,fresh)\n                fields={'Contact_Status':contact_status,'Status':status,'Last_Contact_Date':today_str(),\n                        'Next_Followup_Date': today_str() if any(i.get('Availability_Status')=='متوفر' for i in active) else ''}\n            elif contact_status == CONTACT_AWAITING:\n                fields={'Contact_Status':contact_status,'Last_Contact_Date':today_str(),'Next_Followup_Date':add_days(today_str(),2)}\n            elif contact_status == CONTACT_ACCEPTED:\n                fields={'Contact_Status':contact_status,'Status':STATUS_CONTACTED,'Last_Contact_Date':today_str(),'Next_Followup_Date':''}\n            elif contact_status == CONTACT_POSTPONED:\n                fields={'Contact_Status':contact_status,'Status':STATUS_NOT_PICKED,'Next_Followup_Date':add_days(today_str(),1)}\n            else:\n                fields={'Contact_Status':contact_status}\n            self._invalidate_undo(conn,order_id)\n            cmap={'Contact_Status':'contact_status','Status':'status','Last_Contact_Date':'last_contact_date','Next_Followup_Date':'next_followup_date'}\n            sets=[]; params=[]\n            for k,v in fields.items(): sets.append(f'{cmap[k]}=%s'); params.append(v)\n            sets.append('updated_at=%s'); params.append(now_str()); params.append(str(order_id))\n            conn.execute(f\"UPDATE orders SET {', '.join(sets)} WHERE order_id=%s\", params)\n            self._log(conn,order_id,'تحديث حالة التواصل',current['Status'],fields.get('Status',current['Status']),note or contact_status,user)\n            self._add_undo(conn,order_id,'تحديث حالة التواصل',snapshot,user)\n            return {'order':self._refresh_order_in_conn(conn, order_id)}\n\n'''
cloud = cloud[:start] + new_set_contact + cloud[end:]

# 5) Preserve the new item decision on undo/restore imports.
old_undo = "conn.execute('UPDATE order_items SET customer_decision=\'rejected\' WHERE item_id=%s', (iid,))"
# No-op safety: source already carries a default-aware schema; the real preservation is done below.
cloud = cloud.replace(
    "INSERT INTO order_items(item_id,order_id,product_name,quantity,image_path,availability_status,available_price,discounted_price,unavailable_reason,availability_note,price_confirmation_required,available_at,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',\n                             tuple(item.get(k, '') for k in ('Item_ID','Order_ID','Product_Name','Quantity','Image_Path','Availability_Status','Available_Price','Discounted_Price','Unavailable_Reason','Availability_Note','Price_Confirmation_Required','Available_At','Created_At')))",
    "INSERT INTO order_items(item_id,order_id,product_name,quantity,image_path,availability_status,available_price,discounted_price,unavailable_reason,availability_note,price_confirmation_required,available_at,created_at,customer_decision) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',\n                             tuple(item.get(k, '') for k in ('Item_ID','Order_ID','Product_Name','Quantity','Image_Path','Availability_Status','Available_Price','Discounted_Price','Unavailable_Reason','Availability_Note','Price_Confirmation_Required','Available_At','Created_At','Customer_Decision')))",
)
cloud = cloud.replace(
    "conn.execute('INSERT INTO order_items(item_id,order_id,product_name,quantity,image_path,availability_status,available_price,discounted_price,unavailable_reason,availability_note,price_confirmation_required,available_at,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',\n                             (iid,oid,str(r.get('Product_Name') or ''),int(r.get('Quantity') or 1),str(r.get('Image_Path') or ''),str(r.get('Availability_Status') or 'بانتظار التوفر'),str(r.get('Available_Price') or ''),str(r.get('Discounted_Price') or ''),str(r.get('Unavailable_Reason') or ''),str(r.get('Availability_Note') or ''),str(r.get('Price_Confirmation_Required') or ''),str(r.get('Available_At') or ''),str(r.get('Created_At') or now_str())))",
    "conn.execute('INSERT INTO order_items(item_id,order_id,product_name,quantity,image_path,availability_status,available_price,discounted_price,unavailable_reason,availability_note,price_confirmation_required,available_at,created_at,customer_decision) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',\n                             (iid,oid,str(r.get('Product_Name') or ''),int(r.get('Quantity') or 1),str(r.get('Image_Path') or ''),str(r.get('Availability_Status') or 'بانتظار التوفر'),str(r.get('Available_Price') or ''),str(r.get('Discounted_Price') or ''),str(r.get('Unavailable_Reason') or ''),str(r.get('Availability_Note') or ''),str(r.get('Price_Confirmation_Required') or ''),str(r.get('Available_At') or ''),str(r.get('Created_At') or now_str()),str(r.get('Customer_Decision') or '')))",
)
write('cloud_db.py', cloud)

# 6) API route: accept item ids rejected by the customer.
app = read('app.py')
app = once(
    app,
    "    return result_response(db.set_contact_status(order_id, str(data.get(\"contact_status\") or \"\"), str(data.get(\"note\") or \"\")))",
    "    return result_response(db.set_contact_status(order_id, str(data.get(\"contact_status\") or \"\"), str(data.get(\"note\") or \"\"), rejected_item_ids=data.get(\"rejected_item_ids\") or []))",
    'app contact API',
)
# WhatsApp should not offer an item explicitly rejected by the customer; legacy cancelled orders infer the old rejection.
pattern = r'    available = \[i for i in items if i\.get\("Availability_Status"\) == "متوفر"\]\n    unavailable = \[i for i in items if i\.get\("Availability_Status"\) == "غير متوفر"\]\n    if not available and not unavailable:\n        available = items\n'
replacement = '''    legacy_rejected = (order.get("Status") == STATUS_CANCELLED\n                       and order.get("Contact_Status") == CONTACT_REJECTED\n                       and any(i.get("Availability_Status") == "بانتظار التوفر" for i in items))\n    eligible = [i for i in items\n                if str(i.get("Customer_Decision") or "").strip() != "rejected"\n                and not (legacy_rejected and i.get("Availability_Status") != "بانتظار التوفر")]\n    available = [i for i in eligible if i.get("Availability_Status") == "متوفر"]\n    unavailable = [i for i in eligible if i.get("Availability_Status") == "غير متوفر"]\n    if not available and not unavailable:\n        available = eligible\n'''
app = regex_once(app, pattern, replacement, 'app whatsapp item filter')
write('app.py', app)

# 7) Frontend: make item-level availability available even on legacy cancelled orders; add per-item rejection chooser.
js = read('static/app.js')
js = once(
    js,
    'async function saveContactStatus(id,status){try{const note=document.getElementById("detail-contact-note")?.value||"";await apiFetch(`/api/orders/${id}/contact-status`,{method:"POST",body:JSON.stringify({contact_status:status,note})});toast("تم تحديث حالة التواصل");details(id);refresh()}catch(e){toast(e.message,"error")}}',
    '''function renderRejectedItemsChooser(order){\n  const host=document.getElementById('detail-rejected-items-host');\n  const status=document.getElementById('detail-contact-status')?.value;\n  if(!host || status!=='العميل رفض'){ if(host)host.innerHTML=''; return; }\n  const available=(order.Items||[]).filter(i=>i.Availability_Status==='متوفر');\n  host.innerHTML = available.length ? `<div class="di-label">حدد المنتجات التي رفضها العميل</div><div class="rejected-items-chooser">${available.map(i=>`<label><input type="checkbox" class="detail-rejected-item" value="${esc(i.Item_ID)}" checked> ${esc(i.Product_Name)} × ${i.Quantity}</label>`).join('')}</div>` : '<div class="field-error">لا توجد منتجات متوفرة حاليًا.</div>';\n}\nasync function saveContactStatus(id,status){try{const note=document.getElementById("detail-contact-note")?.value||"";const rejected_item_ids=[...document.querySelectorAll('.detail-rejected-item:checked')].map(x=>x.value);await apiFetch(`/api/orders/${id}/contact-status`,{method:"POST",body:JSON.stringify({contact_status:status,note,rejected_item_ids})});toast("تم تحديث حالة التواصل");details(id);refresh()}catch(e){toast(e.message,"error")}}''',
    'js contact status',
)

start = js.find("function openAvailability(id){")
end = js.find("function closeAvailability", start)
if start < 0 or end < 0: raise SystemExit('js availability boundaries missing')
open_avail = '''function openAvailability(id){currentAvailability=id;availabilityReturnOrder=id;const orderModal=document.getElementById('order-modal');orderModal.classList.add('hidden');orderModal.setAttribute('aria-hidden','true');const availabilityModal=document.getElementById('availability-modal');availabilityModal.classList.remove('hidden');availabilityModal.setAttribute('aria-hidden','false');apiFetch(`/api/orders/${id}`).then(d=>{const items=d.order.Items||[];document.getElementById('availability-items').innerHTML=items.map(i=>`<div class="availability-row" data-item-id="${esc(i.Item_ID)}"><div class="availability-item-head"><div><b>${esc(i.Product_Name)}</b><span> × ${i.Quantity}</span>${String(i.Customer_Decision||'').trim()==='rejected'?'<span class="image-attached">❌ مرفوض من العميل</span>':''}</div><select class="avail-status"><option value="بانتظار التوفر" ${i.Availability_Status==='بانتظار التوفر'?'selected':''}>بانتظار التوفر</option><option value="متوفر" ${i.Availability_Status==='متوفر'?'selected':''}>متوفر</option><option value="غير متوفر" ${i.Availability_Status==='غير متوفر'?'selected':''}>غير متوفر</option></select></div><div class="availability-fields"><input class="avail-price" type="number" min="0" step="0.01" placeholder="السعر العادي (اختياري)" value="${esc(i.Available_Price||'')}"><input class="avail-discount" type="number" min="0" step="0.01" placeholder="السعر بعد الخصم (اختياري)" value="${esc(i.Discounted_Price||'')}"><label class="price-confirm-check"><input type="checkbox" class="avail-price-confirm" ${String(i.Price_Confirmation_Required||'').trim()==='نعم'?'checked':''}> التأكد من السعر مع العميل قبل التوفير</label><select class="avail-reason"><option value="">سبب عدم التوفر</option><option ${i.Unavailable_Reason==='غير متوفر لدى المورد'?'selected':''}>غير متوفر لدى المورد</option><option ${i.Unavailable_Reason==='متوقف من الشركة'?'selected':''}>متوقف من الشركة</option><option ${i.Unavailable_Reason==='لا يوجد مخزون حاليًا'?'selected':''}>لا يوجد مخزون حاليًا</option><option ${i.Unavailable_Reason==='المنتج غير متاح حاليًا'?'selected':''}>المنتج غير متاح حاليًا</option><option ${i.Unavailable_Reason==='السعر من المورد غير مناسب'?'selected':''}>السعر من المورد غير مناسب</option><option ${i.Unavailable_Reason==='سبب آخر'?'selected':''}>سبب آخر</option></select><input class="avail-note" placeholder="ملاحظة إضافية (اختياري)" value="${esc(i.Availability_Note||'')}">${String(i.Customer_Decision||'').trim()==='rejected'?'<label class="price-confirm-check"><input type="checkbox" class="avail-reopen-customer"> إعادة فتح المنتج للتواصل مع العميل</label>':''}</div><div class="availability-current">${i.Available_Price?`السعر الحالي: ${esc(i.Available_Price)} ريال`:'السعر غير مسجل'}${i.Discounted_Price?` — بعد الخصم: ${esc(i.Discounted_Price)} ريال`:''}</div></div>`).join('');document.querySelectorAll('.availability-row').forEach(row=>{const st=row.querySelector('.avail-status'),reason=row.querySelector('.avail-reason');const toggle=()=>{const available=st.value==='متوفر',unavailable=st.value==='غير متوفر';row.querySelector('.avail-price').disabled=!available;row.querySelector('.avail-discount').disabled=!available;row.querySelector('.avail-price-confirm').disabled=!available;reason.disabled=!unavailable;row.querySelector('.avail-note').disabled=!(available||unavailable)};st.onchange=toggle;toggle();});}).catch(e=>toast(e.message,'error'))}\n'''
js = js[:start] + open_avail + js[end:]

js = once(
    js,
    'async function saveAvailability(){if(!currentAvailability)return;const items=[...document.querySelectorAll(\'.availability-row\')].map(r=>({Item_ID:r.dataset.itemId,availability_status:r.querySelector(\'.avail-status\').value,available_price:r.querySelector(\'.avail-price\').value,discounted_price:r.querySelector(\'.avail-discount\').value,unavailable_reason:r.querySelector(\'.avail-reason\').value,availability_note:r.querySelector(\'.avail-note\').value,price_confirmation_required:r.querySelector(\'.avail-price-confirm\').checked}));try{const id=currentAvailability;await apiFetch(`/api/orders/${id}/availability`,{method:\'POST\',body:JSON.stringify({items})});toast(\'تم حفظ حالة توفر المنتجات\');currentAvailability=null;availabilityReturnOrder=null;document.getElementById(\'availability-modal\').classList.add(\'hidden\');document.getElementById(\'availability-modal\').setAttribute(\'aria-hidden\',\'true\');refresh();details(id)}catch(e){toast(e.message,\'error\')}}',
    'async function saveAvailability(){if(!currentAvailability)return;const items=[...document.querySelectorAll(\'.availability-row\')].map(r=>({Item_ID:r.dataset.itemId,availability_status:r.querySelector(\'.avail-status\').value,available_price:r.querySelector(\'.avail-price\').value,discounted_price:r.querySelector(\'.avail-discount\').value,unavailable_reason:r.querySelector(\'.avail-reason\').value,availability_note:r.querySelector(\'.avail-note\').value,price_confirmation_required:r.querySelector(\'.avail-price-confirm\').checked,reopen_customer:!!r.querySelector(\'.avail-reopen-customer\')?.checked}));try{const id=currentAvailability;await apiFetch(`/api/orders/${id}/availability`,{method:\'POST\',body:JSON.stringify({items})});toast(\'تم حفظ حالة توفر المنتجات\');currentAvailability=null;availabilityReturnOrder=null;document.getElementById(\'availability-modal\').classList.add(\'hidden\');document.getElementById(\'availability-modal\').setAttribute(\'aria-hidden\',\'true\');refresh();details(id)}catch(e){toast(e.message,\'error\')}}',
    'js saveAvailability',
)

js = once(
    js,
    "${['بانتظار التوفر','متوفر - يحتاج اتصال','متوفر جزئيًا - يحتاج اتصال'].includes(o.Status)?`<button class=\"btn btn-primary modal-avail\">تحديث توفر المنتجات</button>`:\"\"}",
    "${(((o.Items||[]).some(i=>i.Availability_Status==='بانتظار التوفر'))||['بانتظار التوفر','متوفر - يحتاج اتصال','متوفر جزئيًا - يحتاج اتصال'].includes(o.Status))?`<button class=\"btn btn-primary modal-avail\">تحديث توفر المنتجات</button>`:\"\"}",
    'js availability action visibility',
)

# Inject chooser host and wiring in the existing detail modal after it is shown.
anchor = 'm.classList.remove("hidden");const cs=m.querySelector("#detail-contact-status"); if(cs) cs.value=o.Contact_Status||"لم يتم التواصل"; if(m.querySelector("#detail-contact-note")) m.querySelector("#detail-contact-note").value=""; m.querySelector("#save-contact-status")?.addEventListener("click",()=>saveContactStatus(id,cs.value));'
replacement = 'm.classList.remove("hidden");const cs=m.querySelector("#detail-contact-status"); if(cs) cs.value=o.Contact_Status||"لم يتم التواصل"; const panel=m.querySelector(".contact-status-panel"); if(panel&&!m.querySelector("#detail-rejected-items-host")){const host=document.createElement("div");host.id="detail-rejected-items-host";panel.appendChild(host)} renderRejectedItemsChooser(o); if(cs)cs.onchange=()=>renderRejectedItemsChooser(o); if(m.querySelector("#detail-contact-note")) m.querySelector("#detail-contact-note").value=""; m.querySelector("#save-contact-status")?.addEventListener("click",()=>saveContactStatus(id,cs.value));'
js = once(js, anchor, replacement, 'js chooser wiring')
write('static/app.js', js)

# Validation: compile Python files and basic JS markers.
import py_compile
for name in ('app.py','db.py','cloud_db.py'):
    py_compile.compile(str(ROOT / name), doraise=True)
js = read('static/app.js')
for marker in ('Customer_Decision','rejected_item_ids','reopen_customer','renderRejectedItemsChooser'):
    if marker not in js:
        raise SystemExit(f'missing JS marker: {marker}')
cloud = read('cloud_db.py')
for marker in ('customer_decision TEXT NOT NULL DEFAULT','def _item_is_rejected','def _derive_workflow_status','def set_availability','def set_contact_status'):
    if marker not in cloud:
        raise SystemExit(f'missing backend marker: {marker}')
print('ITEM_STATE_FIX_OK')
