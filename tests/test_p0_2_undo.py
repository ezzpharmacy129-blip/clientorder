import copy, json, unittest
from contextlib import contextmanager
import psycopg
from cloud_db import CloudDB
psycopg.Binary=lambda value:value
class Cur:
    def __init__(self,rows=None): self.rows=rows or []
    def fetchone(self): return self.rows[0] if self.rows else None
    def fetchall(self): return self.rows
class Conn:
    def __init__(self):
        self.orders={'O':{'order_id':'O','customer_name':'C','phone':'P','product_name':'A × 2، B × 1','quantity':3,'order_date':'D','available_date':'','status':'متوفر - يحتاج اتصال','contact_status':'لم يتم التواصل','last_contact_date':'','next_followup_date':'','pickup_date':'','notes':'N','created_at':'T','updated_at':'T'}}
        self.items={'A':{'item_id':'A','order_id':'O','product_name':'A','quantity':2,'image_path':'O/A.png','availability_status':'متوفر','available_price':'20','discounted_price':'18','unavailable_reason':'','availability_note':'note','price_confirmation_required':'','available_at':'D','created_at':'T','customer_decision':'accepted'},'B':{'item_id':'B','order_id':'O','product_name':'B','quantity':1,'image_path':'O/B.png','availability_status':'غير متوفر','available_price':'','discounted_price':'','unavailable_reason':'no','availability_note':'','price_confirmation_required':'','available_at':'','created_at':'T2','customer_decision':'rejected'}}
        self.images={'O/A.png':{'image_path':'O/A.png','order_id':'O','item_id':'A','filename':'A.png','content_type':'image/png','data':b'AAA','created_at':'T'},'O/B.png':{'image_path':'O/B.png','order_id':'O','item_id':'B','filename':'B.png','content_type':'image/png','data':b'BBB','created_at':'T2'}}
        self.undo=[]; self.undo_images=[]
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def execute(self,sql,params=()):
        s=' '.join(sql.strip().split()).lower(); p=list(params)
        if s.startswith('select * from orders where order_id='):
            r=self.orders.get(str(p[0])); return Cur([copy.deepcopy(r)] if r else [])
        if s.startswith('select * from order_items where order_id='):
            return Cur([copy.deepcopy(x) for x in self.items.values() if x['order_id']==str(p[0])])
        if s.startswith('select item_id,image_path,filename,content_type,data,created_at from item_images where order_id='):
            oid=str(p[0]); wanted={str(x) for x in p[1:]}; return Cur([copy.deepcopy(x) for x in self.images.values() if x['order_id']==oid and x['item_id'] in wanted])
        if s.startswith('select item_id,image_path,filename,content_type,data,created_at from undo_item_images where undo_id='):
            return Cur([copy.deepcopy(x) for x in self.undo_images if x['undo_id']==str(p[0])])
        if s.startswith('select * from undo_history where order_id='):
            rows=[copy.deepcopy(x) for x in self.undo if x['order_id']==str(p[0]) and not x['undone_at']]; return Cur(sorted(rows,key=lambda x:x['created_at'],reverse=True)[:1])
        if s.startswith('update order_items set product_name=%s,quantity=%s,image_path='):
            iid=str(p[-2]); keys=['product_name','quantity','image_path','availability_status','available_price','discounted_price','unavailable_reason','availability_note','price_confirmation_required','available_at','created_at','customer_decision']
            for k,v in zip(keys,p[:-2]): self.items[iid][k]=v
            return Cur([])
        if s.startswith('insert into order_items'):
            keys=['item_id','order_id','product_name','quantity','image_path','availability_status','available_price','discounted_price','unavailable_reason','availability_note','price_confirmation_required','available_at','created_at','customer_decision']; self.items[str(p[0])]=dict(zip(keys,p)); return Cur([])
        if s.startswith('delete from order_items where item_id='):
            iid=str(p[0]); self.items.pop(iid,None); self.images={k:v for k,v in self.images.items() if v['item_id']!=iid}; return Cur([])
        if s.startswith('delete from item_images where order_id='):
            oid,iid=str(p[0]),str(p[1]); self.images={k:v for k,v in self.images.items() if not (v['order_id']==oid and v['item_id']==iid)}; return Cur([])
        if s.startswith('insert into item_images'):
            keys=['image_path','order_id','item_id','filename','content_type','data','created_at']; self.images[str(p[0])]=dict(zip(keys,p)); return Cur([])
        if s.startswith('update undo_history set undone_at='):
            for x in self.undo:
                if x['undo_id']==str(p[1]): x['undone_at']=str(p[0])
            return Cur([])
        if s.startswith('update orders set') or s.startswith('insert into activity_log') or s.startswith('insert into undo_history') or s.startswith('insert into undo_item_images'): return Cur([])
        return Cur([])
@contextmanager
def ctx(c): yield c
class TestUndo(unittest.TestCase):
    def setUp(self):
        self.c=Conn(); self.db=CloudDB.__new__(CloudDB); self.db._connect=lambda:ctx(self.c); self.db._next_undo_id=lambda c:'U1'; self.db._next_log_id=lambda c:'L1'; self.db._log=lambda *a,**k:None; self.db._refresh_order_in_conn=lambda c,o:{'Items':[copy.deepcopy(x) for x in c.items.values() if x['order_id']==o]}
    def test_deleted_item_and_image_restore(self):
        snap={'order':copy.deepcopy(self.c.orders['O']),'items':[{'Item_ID':'A','Order_ID':'O','Product_Name':'A','Quantity':2,'Image_Path':'O/A.png','Availability_Status':'متوفر','Available_Price':'20','Discounted_Price':'18','Unavailable_Reason':'','Availability_Note':'note','Price_Confirmation_Required':'','Available_At':'D','Created_At':'T','Customer_Decision':'accepted'},{'Item_ID':'B','Order_ID':'O','Product_Name':'B','Quantity':1,'Image_Path':'O/B.png','Availability_Status':'غير متوفر','Available_Price':'','Discounted_Price':'','Unavailable_Reason':'no','Availability_Note':'','Price_Confirmation_Required':'','Available_At':'','Created_At':'T2','Customer_Decision':'rejected'}]}
        self.c.undo=[{'undo_id':'U1','order_id':'O','action':'تعديل','snapshot_json':json.dumps(snap,ensure_ascii=False),'created_at':'T4','undone_at':'','user_name':'tester'}]; self.c.undo_images=[{'undo_id':'U1','item_id':'B','image_path':'O/B.png','filename':'B.png','content_type':'image/png','data':b'BBB','created_at':'T2'}]
        self.c.items.pop('B'); self.c.images.pop('O/B.png'); self.db.undo_last('O','tester'); self.assertIn('B',self.c.items); self.assertEqual(self.c.images['O/B.png']['data'],b'BBB')
    def test_new_image_removed_when_snapshot_had_none(self):
        snap={'order':copy.deepcopy(self.c.orders['O']),'items':[{'Item_ID':'A','Order_ID':'O','Product_Name':'A','Quantity':2,'Image_Path':'','Availability_Status':'متوفر','Available_Price':'20','Discounted_Price':'18','Unavailable_Reason':'','Availability_Note':'note','Price_Confirmation_Required':'','Available_At':'D','Created_At':'T','Customer_Decision':'accepted'},{'Item_ID':'B','Order_ID':'O','Product_Name':'B','Quantity':1,'Image_Path':'O/B.png','Availability_Status':'غير متوفر','Available_Price':'','Discounted_Price':'','Unavailable_Reason':'no','Availability_Note':'','Price_Confirmation_Required':'','Available_At':'','Created_At':'T2','Customer_Decision':'rejected'}]}
        self.c.items['A']['image_path']='O/A-new.png'; self.c.images['O/A-new.png']={'image_path':'O/A-new.png','order_id':'O','item_id':'A','filename':'A-new.png','content_type':'image/png','data':b'NEW','created_at':'T3'}; self.c.undo=[{'undo_id':'U1','order_id':'O','action':'إضافة صورة','snapshot_json':json.dumps(snap,ensure_ascii=False),'created_at':'T4','undone_at':'','user_name':'tester'}]
        self.db.undo_last('O','tester'); self.assertEqual(self.c.items['A']['image_path'],''); self.assertNotIn('O/A-new.png',self.c.images)
if __name__=='__main__': unittest.main()
