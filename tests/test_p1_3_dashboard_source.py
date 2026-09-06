import unittest
from pathlib import Path

class P13DashboardSourceTests(unittest.TestCase):
    def test_server_exposes_filter_results(self):
        source=Path("app.py").read_text(encoding="utf-8")
        self.assertIn('"dashboard_filters": dashboard_filters',source)
        self.assertIn('"pending": [_dashboard_order_payload(o) for o in orders if _order_has_pending_item(o)]',source)
        self.assertIn('"overdue": [_dashboard_order_payload(o) for o in orders if (',source)
    def test_frontend_uses_server_filter_source(self):
        source=Path("static/app.js").read_text(encoding="utf-8")
        self.assertIn('window.dashboardStats?.dashboard_filters',source)
        self.assertNotIn("orders.filter(o=>o.Status==='بانتظار التوفر')",source)
if __name__ == "__main__": unittest.main()
