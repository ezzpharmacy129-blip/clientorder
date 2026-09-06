import io
import os
import tempfile
import unittest
from unittest.mock import Mock

# db.py selects CloudDB while importing when DATABASE_URL is already present.
# Import the modules first without the environment selector, then restore it so
# CloudDB instances can still connect to the integration PostgreSQL database.
_ci_database_url = os.environ.pop('DATABASE_URL', None)
try:
    from cloud_db import CloudDB
    from db import STATUS_PENDING, CONTACT_NOT_CONTACTED
finally:
    if _ci_database_url:
        os.environ['DATABASE_URL'] = _ci_database_url

from openpyxl import Workbook


def workbook_bytes(orders, items=None, logs=None, undos=None, settings=None):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Orders'
    headers = ['Order_ID','Customer_Name','Phone','Product_Name','Quantity','Order_Date','Available_Date','Status','Contact_Status','Last_Contact_Date','Next_Followup_Date','Pickup_Date','Notes','Created_At','Updated_At']
    ws.append(headers)
    for row in orders:
        ws.append([row.get(h, '') for h in headers])
    sheets = [
        ('Order_Items', ['Item_ID','Order_ID','Product_Name','Quantity','Image_Path','Availability_Status','Available_Price','Discounted_Price','Unavailable_Reason','Availability_Note','Price_Confirmation_Required','Available_At','Created_At','Customer_Decision'], items or []),
        ('Activity_Log', ['Log_ID','Order_ID','Action','Old_Status','New_Status','Note','Created_At','User'], logs or []),
        ('Undo_History', ['Undo_ID','Order_ID','Action','Snapshot_JSON','Created_At','Undone_At','User'], undos or []),
        ('Settings', ['Key','Value'], settings or []),
    ]
    for name, headers, rows in sheets:
        sh = wb.create_sheet(name)
        sh.append(headers)
        for row in rows:
            sh.append([row.get(h, '') for h in headers])
    bio = io.BytesIO()
    wb.save(bio)
    wb.close()
    return bio.getvalue()


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.db = CloudDB.__new__(CloudDB)
        self.order = {'Order_ID':'ORD-1','Customer_Name':'عميل','Phone':'0500000000','Status':STATUS_PENDING,'Contact_Status':CONTACT_NOT_CONTACTED}
        self.item = {'Item_ID':'ITEM-1','Order_ID':'ORD-1','Product_Name':'دواء','Quantity':1,'Image_Path':'','Availability_Status':'بانتظار التوفر'}

    def check_rejected(self, **kwargs):
        orders = kwargs.pop('orders', [self.order.copy()])
        items = kwargs.pop('items', [self.item.copy()])
        logs = kwargs.pop('logs', [])
        undos = kwargs.pop('undos', [])
        settings = kwargs.pop('settings', [])
        images = kwargs.pop('images', None)
        with self.assertRaises(ValueError):
            self.db._validate_import_payload(orders, items, logs, undos, settings, images)

    def test_duplicate_order_rejected(self):
        a = self.order.copy(); b = self.order.copy(); b['Customer_Name'] = 'آخر'
        self.check_rejected(orders=[a,b])

    def test_orphan_item_rejected(self):
        i = self.item.copy(); i['Order_ID'] = 'ORD-404'
        self.check_rejected(items=[i])

    def test_duplicate_item_rejected(self):
        a = self.item.copy(); b = self.item.copy(); b['Product_Name'] = 'منتج آخر'
        self.check_rejected(items=[a,b])

    def test_dangling_image_rejected(self):
        i = self.item.copy(); i['Image_Path'] = 'ORD-1/ITEM-404.png'
        self.check_rejected(items=[i], images={'ORD-1/ITEM-404.png': b'x'})

    def test_unreferenced_image_rejected(self):
        self.check_rejected(images={'ORD-1/ITEM-1.png': b'x'})

    def test_malformed_undo_rejected(self):
        self.check_rejected(undos=[{'Undo_ID':'U1','Order_ID':'ORD-1','Snapshot_JSON':'not-json'}])

    def test_invalid_status_rejected(self):
        o = self.order.copy(); o['Status'] = 'حالة غير موجودة'
        self.check_rejected(orders=[o])

    def test_prevalidation_happens_before_database_mutation(self):
        a = self.order.copy(); b = self.order.copy(); b['Customer_Name'] = 'آخر'
        self.db._connect = Mock(side_effect=AssertionError('database opened before validation'))
        with self.assertRaises(ValueError):
            self.db._replace_from_xlsx(workbook_bytes([a,b]))
        self.db._connect.assert_not_called()


class BackupOrderTests(unittest.TestCase):
    def test_backup_is_unconditional_and_precedes_replace(self):
        db = CloudDB.__new__(CloudDB)
        events = []
        db.create_manual_backup = Mock(side_effect=lambda reason='auto': events.append(('backup', reason)) or 'backup_auto.zip')
        db.list_backups = Mock(side_effect=AssertionError('list_backups must not control safety backup'))
        db._replace_from_xlsx = Mock(side_effect=lambda *_args: events.append(('replace', None)))
        db.get_all_orders = Mock(return_value=[])
        payload = workbook_bytes([{'Order_ID':'ORD-1','Customer_Name':'عميل','Phone':'0500000000','Status':STATUS_PENDING,'Contact_Status':CONTACT_NOT_CONTACTED}])
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            f.write(payload); path = f.name
        try:
            result = db.import_legacy_data(path)
        finally:
            os.unlink(path)
        self.assertEqual(events, [('backup','auto'),('replace',None)])
        self.assertEqual(result['backup'], 'backup_auto.zip')
        db.list_backups.assert_not_called()

    def test_replace_failure_happens_after_backup(self):
        db = CloudDB.__new__(CloudDB)
        events = []
        db.create_manual_backup = Mock(side_effect=lambda reason='auto': events.append(('backup', reason)) or 'backup_auto.zip')
        db._replace_from_xlsx = Mock(side_effect=RuntimeError('replace failed'))
        payload = workbook_bytes([{'Order_ID':'ORD-1','Customer_Name':'عميل','Phone':'0500000000','Status':STATUS_PENDING,'Contact_Status':CONTACT_NOT_CONTACTED}])
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            f.write(payload); path = f.name
        try:
            with self.assertRaises(RuntimeError):
                db.import_legacy_data(path)
        finally:
            os.unlink(path)
        self.assertEqual(events, [('backup','auto')])


class PostgresIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('DATABASE_URL'):
            raise unittest.SkipTest('DATABASE_URL not set')
        cls.db = CloudDB()

    def setUp(self):
        with self.db._connect() as conn:
            conn.execute('TRUNCATE backups, activity_log, undo_item_images, undo_history, item_images, order_items, orders')
            conn.execute("INSERT INTO orders(order_id,customer_name,phone,product_name,quantity,status,contact_status,created_at,updated_at) VALUES ('OLD-1','قديم','0500000001','قديم',1,%s,%s,'T','T')", (STATUS_PENDING, CONTACT_NOT_CONTACTED))
            conn.execute("INSERT INTO order_items(item_id,order_id,product_name,quantity,availability_status,created_at) VALUES ('OLD-ITEM','OLD-1','قديم',1,'بانتظار التوفر','T')")

    def test_valid_import_creates_backup_when_none_exists(self):
        payload = workbook_bytes(
            [{'Order_ID':'NEW-1','Customer_Name':'جديد','Phone':'0500000002','Product_Name':'جديد','Quantity':1,'Status':STATUS_PENDING,'Contact_Status':CONTACT_NOT_CONTACTED}],
            [{'Item_ID':'NEW-ITEM','Order_ID':'NEW-1','Product_Name':'منتج جديد','Quantity':1,'Availability_Status':'بانتظار التوفر'}],
        )
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            f.write(payload); path = f.name
        try:
            result = self.db.import_legacy_data(path)
        finally:
            os.unlink(path)
        with self.db._connect() as conn:
            old = conn.execute("SELECT COUNT(*) AS c FROM orders WHERE order_id='OLD-1'").fetchone()['c']
            new = conn.execute("SELECT COUNT(*) AS c FROM orders WHERE order_id='NEW-1'").fetchone()['c']
            backups = conn.execute('SELECT COUNT(*) AS c FROM backups').fetchone()['c']
        self.assertEqual(old, 0)
        self.assertEqual(new, 1)
        self.assertEqual(backups, 1)
        self.assertTrue(result['backup'].startswith('backup_auto_'))

    def test_invalid_import_preserves_current_data_and_creates_no_backup(self):
        a = {'Order_ID':'NEW-1','Customer_Name':'جديد','Phone':'0500000002','Status':STATUS_PENDING,'Contact_Status':CONTACT_NOT_CONTACTED}
        b = {'Order_ID':'NEW-1','Customer_Name':'مكرر','Phone':'0500000003','Status':STATUS_PENDING,'Contact_Status':CONTACT_NOT_CONTACTED}
        payload = workbook_bytes([a,b])
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            f.write(payload); path = f.name
        try:
            with self.assertRaises(ValueError):
                self.db.import_legacy_data(path)
        finally:
            os.unlink(path)
        with self.db._connect() as conn:
            old = conn.execute("SELECT COUNT(*) AS c FROM orders WHERE order_id='OLD-1'").fetchone()['c']
            backups = conn.execute('SELECT COUNT(*) AS c FROM backups').fetchone()['c']
        self.assertEqual(old, 1)
        self.assertEqual(backups, 0)


# P0.3 verification trigger: same tests, new synchronize event.

if __name__ == '__main__':
    unittest.main()
