import unittest
from unittest.mock import MagicMock, Mock
import ast
from pathlib import Path

def extracted_function(filename,name,namespace):
    tree=ast.parse((Path(__file__).resolve().parents[1]/filename).read_text(encoding="utf-8"))
    node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name)
    node.decorator_list=[]
    exec(compile(ast.Module(body=[node],type_ignores=[]),filename,"exec"),namespace)
    return namespace[name]


class ClosedReplyTests(unittest.TestCase):
    def test_closed_orders_reject_reply_without_writes(self):
        method=extracted_function('cloud_db.py','set_contact_status',{
            'ALL_CONTACT_STATUSES':['العميل موافق','العميل رفض'],
            'STATUS_PICKED_UP':'تم الاستلام','STATUS_CANCELLED':'ملغي'})
        for status in ['تم الاستلام','ملغي']:
            for reply in ['العميل موافق','العميل رفض']:
                db=Mock(); connection=MagicMock()
                connection.__enter__.return_value=connection
                db._connect.return_value=connection
                db._fetch_order.return_value={'Status':status}
                result=method(db,'ORD-1',reply)
                self.assertEqual(result['code'],409)
                connection.execute.assert_not_called()
                db._snapshot.assert_not_called()


if __name__=='__main__': unittest.main()
