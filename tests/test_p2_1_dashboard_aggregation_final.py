import unittest
from pathlib import Path

class P21DashboardAggregationTests(unittest.TestCase):
    def test_cloud_dashboard_summary_uses_postgresql_aggregation(self):
        s=Path("cloud_db.py").read_text(encoding="utf-8")
        self.assertIn("def dashboard_summary",s)
        self.assertIn("COUNT(*) FILTER",s)
        self.assertIn("FROM orders o",s)

    def test_dashboard_route_uses_summary_facade(self):
        s=Path("app.py").read_text(encoding="utf-8")
        self.assertIn("stats = db.dashboard_summary(today)",s)
        self.assertIn('"dashboard_filters": dashboard_filters',s)

    def test_local_backend_keeps_compatible_summary(self):
        s=Path("db.py").read_text(encoding="utf-8")
        self.assertIn("def dashboard_summary",s)

if __name__=="__main__":
    unittest.main()
