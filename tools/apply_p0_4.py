from pathlib import Path

p = Path('cloud_db.py')
text = p.read_text(encoding='utf-8')

if 'import base64\n' not in text:
    text = text.replace('import io\n', 'import base64\nimport io\n', 1)

old = "        wu=wb.create_sheet('Undo_History'); wu.append(UNDO_HEADERS)\n        wsset=wb.create_sheet('Settings'); wsset.append(SETTINGS_HEADERS)\n"
new = "        wu=wb.create_sheet('Undo_History'); wu.append(UNDO_HEADERS)\n        wui=wb.create_sheet('Undo_Item_Images'); wui.append(['Undo_ID','Item_ID','Image_Path','Filename','Content_Type','Data_Base64','Created_At'])\n        wsset=wb.create_sheet('Settings'); wsset.append(SETTINGS_HEADERS)\n"
if old in text and 'Undo_Item_Images' not in text:
    text = text.replace(old, new, 1)

old = "            undo_rows=conn.execute('SELECT * FROM undo_history ORDER BY created_at').fetchall()\n            settings=conn.execute('SELECT key,value FROM settings ORDER BY key').fetchall()\n"
new = "            undo_rows=conn.execute('SELECT * FROM undo_history ORDER BY created_at').fetchall()\n            undo_image_rows=conn.execute('SELECT undo_id,item_id,image_path,filename,content_type,data,created_at FROM undo_item_images ORDER BY undo_id,item_id,image_path').fetchall()\n            settings=conn.execute('SELECT key,value FROM settings ORDER BY key').fetchall()\n"
if old in text and 'undo_image_rows=' not in text:
    text = text.replace(old, new, 1)

old = "        for r in undo_rows:\n            wu.append([r['undo_id'],r['order_id'],r['action'],r['snapshot_json'],r['created_at'],r['undone_at'],r['user_name']])\n        for r in settings:\n"
new = "        for r in undo_rows:\n            wu.append([r['undo_id'],r['order_id'],r['action'],r['snapshot_json'],r['created_at'],r['undone_at'],r['user_name']])\n        for r in undo_image_rows:\n            wui.append([r['undo_id'],r['item_id'],r['image_path'],r['filename'],r['content_type'],base64.b64encode(bytes(r['data'])).decode('ascii'),r['created_at']])\n        for r in settings:\n"
if old in text and 'base64.b64encode(bytes(r[\'data\']))' not in text:
    text = text.replace(old, new, 1)

old = "    def _validate_import_payload(self, orders, items, logs, undos, settings, images=None):\n"
new = "    def _validate_import_payload(self, orders, items, logs, undos, settings, images=None, undo_images=None):\n"
if old in text and 'undo_images=None):' not in text:
    text = text.replace(old, new, 1)

marker = "        if images is None:\n"
validation = "        if undo_images:\n            seen_undo_images = set()\n            undo_id_set = undo_ids\n            item_id_set = item_ids\n            for row in undo_images:\n                uid = str(row.get('Undo_ID') or '').strip()\n                iid = str(row.get('Item_ID') or '').strip()\n                path = str(row.get('Image_Path') or '').replace('\\\\', '/').lstrip('/')\n                filename = str(row.get('Filename') or '').strip()\n                content_type = str(row.get('Content_Type') or '').strip()\n                token = (uid, iid, path)\n                if token in seen_undo_images:\n                    raise ValueError(f'تكرار صورة Undo: {uid}/{iid}/{path}')\n                if uid not in undo_id_set:\n                    raise ValueError(f'صورة Undo تشير إلى Undo_ID غير موجود: {uid}')\n                if iid not in item_id_set:\n                    raise ValueError(f'صورة Undo تشير إلى Item_ID غير موجود: {iid}')\n                if not path or not filename or not content_type:\n                    raise ValueError(f'بيانات صورة Undo ناقصة: {uid}/{iid}')\n                raw = str(row.get('Data_Base64') or '').strip()\n                try:\n                    data = base64.b64decode(raw, validate=True)\n                except Exception:\n                    raise ValueError(f'Data_Base64 غير صالح لصورة Undo: {uid}/{iid}')\n                if not data:\n                    raise ValueError(f'بيانات صورة Undo فارغة: {uid}/{iid}')\n                if len(data) > MAX_IMAGE_SIZE:\n                    raise ValueError(f'حجم صورة Undo أكبر من 10 ميجابايت: {uid}/{iid}')\n                seen_undo_images.add(token)\n\n"
if validation not in text:
    if marker not in text:
        raise SystemExit('images validation marker not found')
    text = text.replace(marker, validation + marker, 1)

old = "        settings = self._read_sheet_dicts(wb['Settings']) if 'Settings' in wb.sheetnames else []\n        wb.close()\n\n        self._validate_import_payload(orders, items, logs, undos, settings, images)\n"
new = "        settings = self._read_sheet_dicts(wb['Settings']) if 'Settings' in wb.sheetnames else []\n        undo_images = self._read_sheet_dicts(wb['Undo_Item_Images']) if 'Undo_Item_Images' in wb.sheetnames else []\n        wb.close()\n\n        self._validate_import_payload(orders, items, logs, undos, settings, images, undo_images)\n"
if old in text and "wb['Undo_Item_Images']" not in text:
    text = text.replace(old, new, 1)

old = "            for r in undos:\n                conn.execute('INSERT INTO undo_history(undo_id,order_id,action,snapshot_json,created_at,undone_at,user_name) VALUES (%s,%s,%s,%s,%s,%s,%s)',\n                             (str(r.get('Undo_ID') or uuid.uuid4().hex),str(r.get('Order_ID') or ''),str(r.get('Action') or ''),str(r.get('Snapshot_JSON') or '{}'),str(r.get('Created_At') or now_str()),str(r.get('Undone_At') or ''),str(r.get('User') or 'موظف')))\n            for r in settings:\n"
new = "            for r in undos:\n                conn.execute('INSERT INTO undo_history(undo_id,order_id,action,snapshot_json,created_at,undone_at,user_name) VALUES (%s,%s,%s,%s,%s,%s,%s)',\n                             (str(r.get('Undo_ID') or uuid.uuid4().hex),str(r.get('Order_ID') or ''),str(r.get('Action') or ''),str(r.get('Snapshot_JSON') or '{}'),str(r.get('Created_At') or now_str()),str(r.get('Undone_At') or ''),str(r.get('User') or 'موظف')))\n            for r in undo_images:\n                raw = base64.b64decode(str(r.get('Data_Base64') or '').strip(), validate=True)\n                conn.execute('INSERT INTO undo_item_images(undo_id,item_id,image_path,filename,content_type,data,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)',\n                             (str(r.get('Undo_ID') or ''),str(r.get('Item_ID') or ''),str(r.get('Image_Path') or ''),str(r.get('Filename') or ''),str(r.get('Content_Type') or ''),psycopg.Binary(raw),str(r.get('Created_At') or now_str())))\n            for r in settings:\n"
if old in text and 'for r in undo_images:' not in text:
    text = text.replace(old, new, 1)

p.write_text(text, encoding='utf-8')
print('P0.4 implementation applied')
