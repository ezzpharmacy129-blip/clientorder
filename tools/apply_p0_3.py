from pathlib import Path
import re

p = Path('cloud_db.py')
text = p.read_text(encoding='utf-8')

if 'def _validate_import_payload(self, orders, items, logs, undos, settings, images=None):' not in text:
    pattern = r"    def _replace_from_xlsx\(self, xlsx_bytes, images=None\):\n.*?(?=    def import_legacy_data\(self, source_path\):)"
    match = re.search(pattern, text, flags=re.S)
    if not match:
        raise SystemExit('P0.3 replacement boundary not found')
    new_block = '''    def _validate_import_payload(self, orders, items, logs, undos, settings, images=None):
        order_ids = set()
        for row in orders:
            oid = str(row.get('Order_ID') or '').strip()
            if not oid:
                raise ValueError('بيانات الاستيراد تحتوي طلبًا بدون Order_ID')
            if oid in order_ids:
                raise ValueError(f'تكرار Order_ID في ملف الاستيراد: {oid}')
            order_ids.add(oid)
            customer = str(row.get('Customer_Name') or '').strip()
            phone = str(row.get('Phone') or '').strip()
            if not customer:
                raise ValueError(f'الطلب {oid} بدون اسم عميل')
            if not phone:
                raise ValueError(f'الطلب {oid} بدون رقم هاتف')
            status = str(row.get('Status') or '').strip() or STATUS_PENDING
            contact = str(row.get('Contact_Status') or '').strip() or (
                CONTACT_AWAITING if status in (STATUS_CONTACTED, STATUS_NOT_PICKED) else CONTACT_NOT_CONTACTED
            )
            if status not in ALL_STATUSES:
                raise ValueError(f'حالة الطلب غير صحيحة للطلب {oid}: {status}')
            if contact not in ALL_CONTACT_STATUSES:
                raise ValueError(f'حالة التواصل غير صحيحة للطلب {oid}: {contact}')
            raw_quantity = row.get('Quantity')
            if raw_quantity not in ('', None):
                try:
                    quantity = int(raw_quantity)
                except (TypeError, ValueError):
                    raise ValueError(f'كمية الطلب غير صحيحة للطلب {oid}')
                if quantity < 0:
                    raise ValueError(f'كمية الطلب لا يمكن أن تكون سالبة للطلب {oid}')

        item_ids = set()
        item_by_id = {}
        referenced_images = set()
        valid_item_statuses = {'بانتظار التوفر', 'متوفر', 'غير متوفر'}
        for row in items:
            iid = str(row.get('Item_ID') or '').strip()
            oid = str(row.get('Order_ID') or '').strip()
            if not iid:
                raise ValueError('بيانات الاستيراد تحتوي عنصرًا بدون Item_ID')
            if iid in item_ids:
                raise ValueError(f'تكرار Item_ID في ملف الاستيراد: {iid}')
            if not oid or oid not in order_ids:
                raise ValueError(f'العنصر {iid} يشير إلى Order_ID غير موجود: {oid}')
            product = str(row.get('Product_Name') or '').strip()
            if not product:
                raise ValueError(f'العنصر {iid} بدون اسم منتج')
            try:
                quantity = int(row.get('Quantity'))
            except (TypeError, ValueError):
                raise ValueError(f'كمية العنصر غير صحيحة: {iid}')
            if quantity <= 0:
                raise ValueError(f'كمية العنصر يجب أن تكون أكبر من صفر: {iid}')
            availability = str(row.get('Availability_Status') or '').strip() or 'بانتظار التوفر'
            if availability not in valid_item_statuses:
                raise ValueError(f'حالة توفر غير صحيحة للعنصر {iid}: {availability}')
            image_path = str(row.get('Image_Path') or '').replace('\\\\', '/').lstrip('/')
            if image_path:
                referenced_images.add(image_path)
            item_ids.add(iid)
            item_by_id[iid] = (oid, image_path)

        log_ids = set()
        for row in logs:
            lid = str(row.get('Log_ID') or '').strip()
            oid = str(row.get('Order_ID') or '').strip()
            if not lid:
                raise ValueError('سجل Activity_Log بدون Log_ID')
            if lid in log_ids:
                raise ValueError(f'تكرار Log_ID في ملف الاستيراد: {lid}')
            if oid not in order_ids:
                raise ValueError(f'سجل Activity_Log يشير إلى طلب غير موجود: {oid}')
            log_ids.add(lid)

        undo_ids = set()
        for row in undos:
            uid = str(row.get('Undo_ID') or '').strip()
            oid = str(row.get('Order_ID') or '').strip()
            if not uid:
                raise ValueError('سجل Undo_History بدون Undo_ID')
            if uid in undo_ids:
                raise ValueError(f'تكرار Undo_ID في ملف الاستيراد: {uid}')
            if oid not in order_ids:
                raise ValueError(f'سجل Undo_History يشير إلى طلب غير موجود: {oid}')
            raw_snapshot = str(row.get('Snapshot_JSON') or '').strip()
            try:
                snapshot = json.loads(raw_snapshot)
            except (TypeError, ValueError, json.JSONDecodeError):
                raise ValueError(f'Snapshot_JSON غير صالح لسجل Undo: {uid}')
            if not isinstance(snapshot, dict) or not isinstance(snapshot.get('order'), dict) or not isinstance(snapshot.get('items'), list):
                raise ValueError(f'Snapshot_JSON غير مكتمل لسجل Undo: {uid}')
            snap_oid = str(snapshot['order'].get('Order_ID') or snapshot['order'].get('order_id') or '').strip()
            if snap_oid and snap_oid != oid:
                raise ValueError(f'Snapshot_JSON لا يطابق Order_ID لسجل Undo: {uid}')
            undo_ids.add(uid)

        setting_keys = set()
        for row in settings:
            key = str(row.get('Key') or '').strip()
            if not key:
                continue
            if key in setting_keys:
                raise ValueError(f'تكرار مفتاح Settings في ملف الاستيراد: {key}')
            setting_keys.add(key)

        if images is None:
            if referenced_images:
                raise ValueError('ملف Excel يحتوي Image_Path بدون ملف صور مرفق')
            return

        normalized_images = {}
        for raw_path, data in images.items():
            path = str(raw_path or '').replace('\\\\', '/').lstrip('/')
            if not path or path in normalized_images:
                raise ValueError('مسار صورة مكرر أو فارغ في ملف الاستيراد')
            if not isinstance(data, (bytes, bytearray)) or not data:
                raise ValueError(f'ملف الصورة فارغ: {path}')
            if len(data) > MAX_IMAGE_SIZE:
                raise ValueError(f'حجم الصورة أكبر من 10 ميجابايت: {path}')
            parts = path.split('/')
            if len(parts) != 2 or not parts[0] or not parts[1] or parts[0] not in order_ids:
                raise ValueError(f'مسار الصورة غير مرتبط بطلب صالح: {path}')
            filename = os.path.basename(path)
            stem = os.path.splitext(filename)[0]
            iid = stem.split('_', 1)[0]
            if iid not in item_by_id or item_by_id[iid][0] != parts[0]:
                raise ValueError(f'الصورة لا ترتبط بعنصر صالح: {path}')
            normalized_images[path] = data

        image_paths = set(normalized_images)
        if image_paths != referenced_images:
            missing = sorted(referenced_images - image_paths)
            extra = sorted(image_paths - referenced_images)
            details = []
            if missing:
                details.append('صور مفقودة: ' + ', '.join(missing))
            if extra:
                details.append('صور غير مرتبطة: ' + ', '.join(extra))
            raise ValueError('حزمة الصور غير متطابقة مع بيانات Order_Items: ' + ' | '.join(details))

    def _replace_from_xlsx(self, xlsx_bytes, images=None):
        wb = load_workbook(io.BytesIO(xlsx_bytes), read_only=True, data_only=False)
        if 'Orders' not in wb.sheetnames:
            wb.close()
            raise ValueError('ملف البيانات لا يحتوي ورقة Orders المطلوبة')
        orders = self._read_sheet_dicts(wb['Orders'])
        required = {'Order_ID', 'Customer_Name', 'Phone'}
        if not orders or not required.issubset(set(orders[0].keys())):
            wb.close()
            raise ValueError('ملف البيانات لا يبدو كملف طلبات صالح')
        items = self._read_sheet_dicts(wb['Order_Items']) if 'Order_Items' in wb.sheetnames else []
        logs = self._read_sheet_dicts(wb['Activity_Log']) if 'Activity_Log' in wb.sheetnames else []
        undos = self._read_sheet_dicts(wb['Undo_History']) if 'Undo_History' in wb.sheetnames else []
        settings = self._read_sheet_dicts(wb['Settings']) if 'Settings' in wb.sheetnames else []
        wb.close()

        self._validate_import_payload(orders, items, logs, undos, settings, images)

        with self._connect() as conn:
            conn.execute('TRUNCATE activity_log, undo_item_images, undo_history, item_images, order_items, orders')
            for r in orders:
                oid = str(r.get('Order_ID') or '').strip()
                status = r.get('Status') or STATUS_PENDING
                contact = r.get('Contact_Status') or (CONTACT_AWAITING if status in (STATUS_CONTACTED, STATUS_NOT_PICKED) else CONTACT_NOT_CONTACTED)
                conn.execute('INSERT INTO orders(order_id,customer_name,phone,product_name,quantity,order_date,available_date,status,contact_status,last_contact_date,next_followup_date,pickup_date,notes,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                             (oid,str(r.get('Customer_Name') or ''),str(r.get('Phone') or ''),str(r.get('Product_Name') or ''),int(r.get('Quantity') or 0),str(r.get('Order_Date') or ''),str(r.get('Available_Date') or ''),status,contact,str(r.get('Last_Contact_Date') or ''),str(r.get('Next_Followup_Date') or ''),str(r.get('Pickup_Date') or ''),str(r.get('Notes') or ''),str(r.get('Created_At') or now_str()),str(r.get('Updated_At') or now_str())))
            for r in items:
                iid = str(r.get('Item_ID') or '').strip()
                oid = str(r.get('Order_ID') or '').strip()
                conn.execute('INSERT INTO order_items(item_id,order_id,product_name,quantity,image_path,availability_status,available_price,discounted_price,unavailable_reason,availability_note,price_confirmation_required,available_at,created_at,customer_decision) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                             (iid,oid,str(r.get('Product_Name') or ''),int(r.get('Quantity') or 1),str(r.get('Image_Path') or ''),str(r.get('Availability_Status') or 'بانتظار التوفر'),str(r.get('Available_Price') or ''),str(r.get('Discounted_Price') or ''),str(r.get('Unavailable_Reason') or ''),str(r.get('Availability_Note') or ''),str(r.get('Price_Confirmation_Required') or ''),str(r.get('Available_At') or ''),str(r.get('Created_At') or now_str()),str(r.get('Customer_Decision') or '')))
            for r in logs:
                conn.execute('INSERT INTO activity_log(log_id,order_id,action,old_status,new_status,note,created_at,user_name) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                             (str(r.get('Log_ID') or uuid.uuid4().hex),str(r.get('Order_ID') or ''),str(r.get('Action') or ''),str(r.get('Old_Status') or ''),str(r.get('New_Status') or ''),str(r.get('Note') or ''),str(r.get('Created_At') or now_str()),str(r.get('User') or 'موظف')))
            for r in undos:
                conn.execute('INSERT INTO undo_history(undo_id,order_id,action,snapshot_json,created_at,undone_at,user_name) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                             (str(r.get('Undo_ID') or uuid.uuid4().hex),str(r.get('Order_ID') or ''),str(r.get('Action') or ''),str(r.get('Snapshot_JSON') or '{}'),str(r.get('Created_At') or now_str()),str(r.get('Undone_At') or ''),str(r.get('User') or 'موظف')))
            for r in settings:
                k = str(r.get('Key') or '').strip()
                if k:
                    conn.execute('INSERT INTO settings(key,value) VALUES (%s,%s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value',(k,str(r.get('Value') or '')))
            if images:
                for path, data in images.items():
                    path = path.replace('\\\\','/').lstrip('/')
                    oid, filename = path.split('/', 1)
                    iid = os.path.splitext(filename)[0].split('_', 1)[0]
                    ext = os.path.splitext(filename)[1].lower()
                    ctype = {'jpg':'image/jpeg','jpeg':'image/jpeg','png':'image/png','webp':'image/webp'}.get(ext.lstrip('.'),'application/octet-stream')
                    conn.execute('INSERT INTO item_images(image_path,order_id,item_id,filename,content_type,data,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                                 (path,oid,iid,filename,ctype,psycopg.Binary(data),now_str()))

'''
    text = text[:match.start()] + new_block + text[match.end():]

old = "backup=self.create_manual_backup(reason='auto') if self.list_backups() else None"
if old in text:
    text = text.replace(old, "backup=self.create_manual_backup(reason='auto')", 1)

p.write_text(text, encoding='utf-8')
print('P0.3 cloud_db.py implementation applied')
