import unittest
from pathlib import Path

class P13DashboardSourceTests(unittest.TestCase):
    def test_server_exposes_filter_results(self):
        source=Path("app.py").read_text(encoding="utf-8")
        start=source.index('@app.get("/api/dashboard")')
        end=source.index('\ndef active_followups(orders):', start)
        route=source[start:end]
        self.assertIn('"dashboard_filters": dashboard_filters',route)
        self.assertIn('"pending": [payload for order, payload in dashboard_entries if _order_has_pending_item(order)]',route)
        self.assertIn('"overdue": [payload for order, payload in dashboard_entries if (',route)
    def test_frontend_uses_server_filter_source(self):
        source=Path("static/app.js").read_text(encoding="utf-8")
        self.assertIn('window.dashboardStats?.dashboard_filters',source)
        self.assertNotIn("orders.filter(o=>o.Status==='بانتظار التوفر')",source)
if __name__ == "__main__":
    unittest.main()
