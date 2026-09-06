import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class P0ItemUpdateSourceTests(unittest.TestCase):
    def test_update_order_no_longer_deletes_all_items(self):
        source = (ROOT / 'cloud_db.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'update_order')
        sql_literals = []
        for call in ast.walk(method):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute) or call.func.attr != 'execute' or not call.args:
                continue
            arg = call.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                sql_literals.append(arg.value.upper())
        self.assertNotIn('DELETE FROM ORDER_ITEMS WHERE ORDER_ID=%S', sql_literals)
        self.assertTrue(any(sql.startswith('UPDATE ORDER_ITEMS SET PRODUCT_NAME=%S,QUANTITY=%S') for sql in sql_literals))
        self.assertTrue(any(sql.startswith('INSERT INTO ORDER_ITEMS') for sql in sql_literals))
        self.assertTrue(any(sql.startswith('DELETE FROM ORDER_ITEMS WHERE ITEM_ID=%S AND ORDER_ID=%S') for sql in sql_literals))

    def test_update_order_accepts_explicit_deleted_item_ids(self):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        self.assertIn('deleted_item_ids = data.get("deleted_item_ids") or []', source)
        self.assertIn('deleted_item_ids=deleted_item_ids', source)

    def test_runtime_update_order_signature_has_delete_channel(self):
        source = (ROOT / 'cloud_db.py').read_text(encoding='utf-8')
        self.assertIn("def update_order(self, order_id, fields, products=None, user='موظف', deleted_item_ids=None):", source)

if __name__ == '__main__':
    unittest.main()
