import unittest
from pathlib import Path

class P22DuplicateRequestTests(unittest.TestCase):
    def test_same_view_navigation_returns_without_reloading(self):
        s=Path("static/app.js").read_text(encoding="utf-8")
        self.assertIn("if(current===v)return;",s)
    def test_dashboard_still_loads_when_entering_view(self):
        s=Path("static/app.js").read_text(encoding="utf-8")
        self.assertIn('if(v==="dashboard")loadDashboard();',s)
    def test_orders_still_loads_when_entering_view(self):
        s=Path("static/app.js").read_text(encoding="utf-8")
        self.assertIn('if(v==="orders")loadOrders();',s)
if __name__=="__main__": unittest.main()
