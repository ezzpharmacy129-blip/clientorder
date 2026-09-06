from pathlib import Path

p = Path('cloud_db.py')
text = p.read_text(encoding='utf-8')

if 'def _validate_xlsx_source(self, xlsx_bytes, images=None):' not in text:
    marker = '    def import_legacy_data(self, source_path):\n'
    method = '''    def _validate_xlsx_source(self, xlsx_bytes, images=None):\n        wb = load_workbook(io.BytesIO(xlsx_bytes), read_only=True, data_only=False)\n        try:\n            if 'Orders' not in wb.sheetnames:\n                raise ValueError('ملف البيانات لا يحتوي ورقة Orders المطلوبة')\n            orders = self._read_sheet_dicts(wb['Orders'])\n            required = {'Order_ID', 'Customer_Name', 'Phone'}\n            if not orders or not required.issubset(set(orders[0].keys())):\n                raise ValueError('ملف البيانات لا يبدو كملف طلبات صالح')\n            items = self._read_sheet_dicts(wb['Order_Items']) if 'Order_Items' in wb.sheetnames else []\n            logs = self._read_sheet_dicts(wb['Activity_Log']) if 'Activity_Log' in wb.sheetnames else []\n            undos = self._read_sheet_dicts(wb['Undo_History']) if 'Undo_History' in wb.sheetnames else []\n            settings = self._read_sheet_dicts(wb['Settings']) if 'Settings' in wb.sheetnames else []\n        finally:\n            wb.close()\n        self._validate_import_payload(orders, items, logs, undos, settings, images)\n\n'''
    if marker not in text:
        raise SystemExit('import_legacy_data boundary not found')
    text = text.replace(marker, method + marker, 1)

old = "        backup=self.create_manual_backup(reason='auto')\n        self._replace_from_xlsx(xlsx, images)"
new = "        self._validate_xlsx_source(xlsx, images)\n        backup=self.create_manual_backup(reason='auto')\n        self._replace_from_xlsx(xlsx, images)"
if old not in text:
    raise SystemExit('backup ordering boundary not found')
text = text.replace(old, new, 1)

p.write_text(text, encoding='utf-8')
print('P0.3 validation-before-backup ordering applied')

# Trigger-only edit: preserve logic above while forcing a fresh workflow run.
print('P0.3 verification trigger refreshed')
