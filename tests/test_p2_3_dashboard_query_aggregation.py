import unittest
from pathlib import Path

class P23DashboardQueryTests(unittest.TestCase):
    def test_cloud_action_summary_uses_sql_aggregation(self):
        s=Path("cloud_db.py").read_text(encoding="utf-8")
        self.assertIn("def dashboard_action_summary",s)
        self.assertIn("COUNT(*) FILTER",s)
        self.assertIn("awaiting_reply",s)

    def test_dashboard_route_uses_action_center_source_of_truth(self):
        s=Path("app.py").read_text(encoding="utf-8")
        self.assertIn("action_center = _build_action_center_payload(orders, today)",s)
        self.assertIn('"action_center": action_center',s)

    def test_dashboard_projection_module_is_present(self):
        s=Path("dashboard_source.py").read_text(encoding="utf-8")
        self.assertIn("def classify_action",s)
        self.assertIn("def build_action_center",s)
        self.assertIn("def install_dashboard_source_of_truth",s)

    def test_local_backend_has_compatible_summary(self):
        s=Path("db.py").read_text(encoding="utf-8")
        self.assertIn("def dashboard_action_summary",s)

if __name__=="__main__": unittest.main()
