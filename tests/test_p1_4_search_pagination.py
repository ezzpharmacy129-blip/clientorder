import unittest
from pathlib import Path

class P14SearchPaginationTests(unittest.TestCase):
    def test_cloud_search_is_server_side_and_parameterized(self):
        s=Path("cloud_db.py").read_text(encoding="utf-8")
        self.assertIn("def search_orders_page",s)
        self.assertIn("LIMIT %s OFFSET %s",s)
        self.assertIn("EXISTS (SELECT 1 FROM order_items",s)
    def test_orders_route_delegates_to_data_layer(self):
        s=Path("app.py").read_text(encoding="utf-8")
        self.assertIn("db.search_orders_page(q,status,date_from,date_to,page,page_size)",s)
        self.assertNotIn('orders=db.get_all_orders(); q=(request.args.get("q")',s)
    def test_frontend_sends_page_and_page_size(self):
        s=Path("static/app.js").read_text(encoding="utf-8")
        self.assertIn('p.set("page",String(ordersPage))',s)
        self.assertIn('p.set("page_size",String(ORDERS_PAGE_SIZE))',s)
        self.assertIn("renderOrdersPagination(d)",s)
if __name__=="__main__": unittest.main()
