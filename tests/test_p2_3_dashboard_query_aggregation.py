import unittest
from pathlib import Path

class P23DashboardQueryTests(unittest.TestCase):
    def test_cloud_action_summary_uses_sql_aggregation(self):
        s=Path("cloud_db.py").read_text(encoding="utf-8")
        self.assertIn("def dashboard_action_summary",s)
        self.assertIn("COUNT(*) FILTER",s)
        self.assertIn("awaiting_reply",s)
    def test_dashboard_route_consumes_action_summary(self):
        s=Path("app.py").read_text(encoding="utf-8")
        self.assertIn("action_summary = db.dashboard_action_summary(today)",s)
        self.assertIn('action_center["summary"] = {**action_center.get("summary", {}), **action_summary}',s)
    def test_local_backend_has_compatible_summary(self):
        s=Path("db.py").read_text(encoding="utf-8")
        self.assertIn("def dashboard_action_summary",s)
if __name__=="__main__": unittest.main()
