"""Offline edit/undo contracts: real methods, transactional in-memory SQL and temporary Excel.

The SQL adapter only translates placeholders and ID allocation; no production connection.
PostgreSQL-specific integration (locks/types) remains outside this offline suite.
"""
import ast
import itertools
import os
import re
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

if os.environ.get('DATABASE_URL'):
    raise RuntimeError('Run regression tests without a production DATABASE_URL')
_storage = tempfile.TemporaryDirectory(prefix='ezz-edit-tests-')
with patch.dict(os.environ, {'EZZ_PHARMACY_DATA_DIR': _storage.name}):
    import db as local
    import cloud_db
    import daily_shortages as shortages

ROOT = Path(__file__).resolve().parents[1]


class SQL:
    def __init__(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = lambda c, r: dict(zip([x[0] for x in c.description], r))
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript(cloud_db.SCHEMA_SQL + shortages.SCHEMA_SQL)

    def execute(self, sql, params=()):
        return self.db.execute(sql.replace('%s', '?'), params)

    def __enter__(self):
        self.db.__enter__()
        return self

    def __exit__(self, *args):
        return self.db.__exit__(*args)


class OrderContract:
    def create(self):
        self.order = self.backend.create_order('عميل', '966500000001', [
            {'product_name': 'A', 'quantity': 2}, {'product_name': 'B', 'quantity': 1}],
            'old', '2026-10-01', 'موظف حقيقي')
        self.oid = self.order['Order_ID']
        self.a, self.b = [i['Item_ID'] for i in self.order['Items']]

    def update(self, fields=None, products=None, deleted=None):
        return self.backend.update_order(self.oid, fields or {}, products, 'موظف حقيقي', deleted_item_ids=deleted)

    def test_1_customer_fields_preserve_items(self):
        result = self.update({'Customer_Name':'معدل', 'Phone':'966500000002', 'Order_Date':'2026-10-06', 'Notes':'new'})
        self.assertEqual(result['Items'], self.order['Items'])
        self.assertEqual([result[k] for k in ('Customer_Name','Phone','Order_Date','Notes')], ['معدل','966500000002','2026-10-06','new'])

    def test_2_item_identity_and_all_metadata(self):
        self.seed_metadata()
        before = self.backend.get_order(self.oid)['Items'][0]
        after = self.update(products=[{'item_id':self.a,'product_name':'changed','quantity':3}])['Items'][0]
        for key in before:
            self.assertEqual(after[key], {'Product_Name':'changed','Quantity':3}.get(key, before[key]), key)

    def test_3_add_preserves_old_items(self):
        result = self.update(products=[{'product_name':'new','quantity':1}])
        self.assertEqual(result['Items'][:2], self.order['Items'])
        self.assertEqual(len({i['Item_ID'] for i in result['Items']}), 3)

    def test_4_delete_only_selected(self):
        result = self.update(products=[], deleted=[self.a])
        self.assertEqual([i['Item_ID'] for i in result['Items']], [self.b])

    def test_5_delete_all_rolls_back_and_keeps_undo(self):
        self.update({'Notes':'prior edit'})
        before = self.backend.get_order(self.oid)
        undo = self.backend.get_undo_info(self.oid)
        for products in ([], None):
            with self.assertRaises(ValueError):
                self.update({'Notes':'must not persist'}, products=products, deleted=[self.a,self.b])
            self.assertEqual(self.backend.get_order(self.oid), before)
            self.assertEqual(self.backend.get_undo_info(self.oid), undo)

    def test_6_workflow_preserved_and_override_rejected(self):
        self.seed_metadata()
        before = self.backend.get_order(self.oid)
        after = self.update({'Notes':'correction'}, [{'item_id':self.a,'product_name':'changed','quantity':3}])
        for key in ('Status','Contact_Status','Available_Date','Last_Contact_Date','Next_Followup_Date','Pickup_Date'):
            self.assertEqual(after[key], before[key])
        for key in ('Status','Contact_Status'):
            with self.assertRaises(ValueError): self.update({key:'تم الاستلام'})

    def test_7_undo_restores_fields_items_images_and_actor(self):
        self.seed_metadata()
        before = self.backend.get_order(self.oid)
        self.update({'Notes':'changed'}, [{'item_id':self.a,'product_name':'changed','quantity':7},{'product_name':'new','quantity':1}], [self.b])
        restored = self.backend.undo_last(self.oid, 'موظف حقيقي')['order']
        for key in before:
            if key != 'Updated_At': self.assertEqual(restored[key], before[key], key)
        self.assertTrue(any(row['User']=='موظف حقيقي' and row['Action']=='تعديل بيانات الطلب' for row in self.backend.get_activity_log(self.oid)))
        self.assert_image_bytes()

    def test_invalid_ids_do_not_mutate(self):
        for products, deleted in [([{'item_id':'foreign','product_name':'x','quantity':1}], []),
                                  ([{'item_id':self.a,'product_name':'x','quantity':1}]*2, []),
                                  ([{'item_id':self.a,'product_name':'x','quantity':1}], [self.a]), ([], ['foreign'])]:
            with self.assertRaises(ValueError): self.update(products=products, deleted=deleted)
            self.assertEqual(self.backend.get_order(self.oid), self.order)


class CloudEditTests(OrderContract, unittest.TestCase):
    def setUp(self):
        self.sql = SQL()
        self.addCleanup(self.sql.db.close)
        self.backend = cloud_db.CloudDB.__new__(cloud_db.CloudDB)
        self.backend._connect = lambda: self.sql
        self.backend._next_order_id = lambda c: 'ORD-1'
        counter = itertools.count(1)
        self.backend._next_item_id = lambda c: f'ITEM-{next(counter):06d}'
        self.binary = patch.object(cloud_db.psycopg, 'Binary', lambda b: b)
        self.binary.start(); self.addCleanup(self.binary.stop)
        self.create()

    def seed_metadata(self):
        with self.sql as c:
            c.execute("UPDATE order_items SET image_path=item_id,availability_status='متوفر',available_price='20',discounted_price='18',customer_decision='accepted',availability_note='note',available_at='2026-10-02',price_confirmation_required='نعم'")
            for iid in (self.a,self.b):
                c.execute('INSERT INTO item_images VALUES (%s,%s,%s,%s,%s,%s,%s)', (iid,self.oid,iid,'a.png','image/png',b'IMAGE','2026-10-02'))
            c.execute("UPDATE orders SET status='تم التواصل - بانتظار الاستلام',contact_status='العميل موافق',available_date='2026-10-02',last_contact_date='2026-10-03',next_followup_date='2026-10-07'")

    def assert_image_bytes(self):
        self.assertEqual([r['data'] for r in self.sql.execute('SELECT data FROM item_images ORDER BY item_id').fetchall()], [b'IMAGE', b'IMAGE'])

    def test_http_edit_actor_authorization_csrf_and_validation(self):
        from flask import Flask, jsonify, request, session
        from authorization_policy import install_authorization
        from csrf_protection import install_csrf
        app = Flask(__name__); app.secret_key = 'offline-test'
        actor = {'role':'employee','name':'موظف حقيقي','username':'staff'}
        self.backend._auth_user_provider = lambda: actor
        app.extensions['ezz_auth'] = {'current_user':lambda:actor}
        install_authorization(app); install_csrf(app)
        # Execute the real route and validators without production startup hooks.
        names = {'clean_phone','validate_products','validate_order_payload','_current_actor_name','api_update_order'}
        tree = ast.parse((ROOT/'app.py').read_text(encoding='utf-8'))
        tree.body = [node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
        scope = dict(app=app,db=self.backend,re=re,jsonify=jsonify,request=request,session=session,ALL_STATUSES=local.ALL_STATUSES)
        exec(compile(tree,'app.py','exec'),scope)
        client = app.test_client()
        with client.session_transaction() as s: s['_csrf_token']='token'
        url = '/api/orders/'+self.oid
        payload = {'customer_name':'معدل','products':[{'item_id':self.a,'product_name':'changed','quantity':4}]}
        self.assertEqual(client.put(url,json=payload).status_code,403)
        headers = {'X-CSRF-Token':'token'}
        response = client.put(url,json=payload,headers=headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['order']['Items'][0]['Item_ID'],self.a)
        self.assertEqual(self.backend.get_activity_log(self.oid)[-1]['User'],'موظف حقيقي')
        before = self.backend.get_order(self.oid)
        for invalid in ({'products':[],'deleted_item_ids':[self.a,self.b]}, {'deleted_item_ids':[self.a,self.b]}, {'status':local.STATUS_PICKED_UP}):
            self.assertEqual(client.put(url,json=invalid,headers=headers).status_code,400)
            self.assertEqual(self.backend.get_order(self.oid),before)


class LocalEditTests(OrderContract, unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ezz-local-edit-')
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        paths = {'SHARED_ROOT':str(root),'DATA_DIR':str(root/'data'),'BACKUP_DIR':str(root/'backups'),'UPLOAD_DIR':str(root/'uploads'),
                 'DB_PATH':str(root/'data/orders.xlsx'),'TMP_PATH':str(root/'data/orders.tmp.xlsx'),'STORAGE_MARKER':str(root/'storage.json')}
        for key, value in paths.items():
            p = patch.object(local,key,value); p.start(); self.addCleanup(p.stop)
        self.backend = local.ExcelDB()
        self.create()

    def seed_metadata(self):
        wb = self.backend._load()
        for row in wb['Order_Items'].iter_rows(min_row=2):
            for key, value in {'Image_Path':str(row[0].value)+'.png','Availability_Status':'متوفر','Available_Price':'20','Discounted_Price':'18','Customer_Decision':'accepted','Availability_Note':'note','Available_At':'2026-10-02','Price_Confirmation_Required':'نعم'}.items():
                row[local.ITEM_HEADERS.index(key)].value = value
            (Path(local.UPLOAD_DIR)/(str(row[0].value)+'.png')).write_bytes(b'IMAGE')
        self.backend._update_fields(wb['Orders'],self.oid,{'Status':'تم التواصل - بانتظار الاستلام','Contact_Status':'العميل موافق','Available_Date':'2026-10-02','Last_Contact_Date':'2026-10-03','Next_Followup_Date':'2026-10-07'})
        local._atomic_save(wb)

    def assert_image_bytes(self):
        for iid in (self.a,self.b): self.assertEqual((Path(local.UPLOAD_DIR)/(iid+'.png')).read_bytes(), b'IMAGE')


class ShortageEditTests(unittest.TestCase):
    def setUp(self):
        self.sql = SQL(); self.addCleanup(self.sql.db.close)
        p = patch.object(shortages,'_connect',lambda:self.sql); p.start(); self.addCleanup(p.stop)

    def test_8_edit_preserves_each_status(self):
        for available in (False,True):
            row = shortages.create_shortage('old',1,'old','موظف حقيقي')
            if available: row = shortages.set_available(row['shortage_id'])
            result = shortages.update_shortage(row['shortage_id'],'new',3,'new note','موظف حقيقي')
            self.assertEqual([result[k] for k in ('product_name','quantity','note')], ['new',3,'new note'])
            for k in ('status','created_at','created_by','resolved_at'): self.assertEqual(result[k],row[k])

    def test_9_undo_shortage_edit(self):
        row = shortages.create_shortage('old',1,'old','موظف حقيقي')
        row = shortages.set_available(row['shortage_id'])
        shortages.update_shortage(row['shortage_id'],'new',3,'new','موظف حقيقي')
        restored = shortages.undo_last(row['shortage_id'],'موظف حقيقي')['shortage']
        for k in row:
            if k != 'updated_at': self.assertEqual(restored[k],row[k])
        self.assertEqual(self.sql.execute("SELECT user_name FROM activity_log WHERE action='تعديل نقص صيدلية'").fetchone()['user_name'],'موظف حقيقي')

    def test_10_frontend_edit_entry_points(self):
        app = (ROOT/'static/app.js').read_text(encoding='utf-8')
        ui = (ROOT/'static/daily_shortages.js').read_text(encoding='utf-8')
        self.assertIn('تعديل الطلب',app)
        self.assertIn('edit-order-btn',app)
        self.assertIn('product.item_id = row.dataset.itemId',app)
        self.assertIn('deleted_item_ids: [...state.deletedItemIds]',app)
        self.assertIn('ps-edit',ui)
        self.assertIn('تعديل نقص الصيدلية',ui)
        self.assertIn('window.openOrderEdit(button.dataset.id)',ui)


if __name__ == '__main__': unittest.main()
