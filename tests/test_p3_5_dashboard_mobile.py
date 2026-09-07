import unittest
from pathlib import Path


class P35DashboardMobileTests(unittest.TestCase):
    def setUp(self):
        self.css = Path("static/p3_5_dashboard_mobile.css").read_text(encoding="utf-8")
        self.core = Path("static/core.js").read_text(encoding="utf-8")
        self.index = Path("templates/index.html").read_text(encoding="utf-8")
        self.app = Path("static/app.js").read_text(encoding="utf-8")

    def test_mobile_layer_targets_dashboard_only(self):
        self.assertIn("@media (max-width: 720px)", self.css)
        self.assertIn("#view-dashboard .dashboard-results-panel", self.css)
        self.assertIn("#view-dashboard .dashboard-orders-table tbody tr", self.css)
        self.assertIn("#view-dashboard .followup-card", self.css)
        self.assertIn("#view-dashboard .followup-actions", self.css)
        self.assertIn("@media (max-width: 420px)", self.css)

    def test_dashboard_results_have_eight_columns(self):
        labels = ["رقم الطلب", "العميل", "المنتجات", "تاريخ الطلب", "الحالة", "التواصل", "المتابعة", "الإجراء"]
        for label in labels:
            self.assertIn(f"<th>{label}</th>", self.index)
        self.assertIn('class="orders-table dashboard-orders-table"', self.index)

    def test_core_loader_is_dedicated_to_p35(self):
        self.assertIn("P3.5", self.core)
        self.assertIn('data-ezz-style="p3-5-dashboard-mobile"', self.core)
        self.assertIn('/static/p3_5_dashboard_mobile.css?v=20260907-p35', self.core)

    def test_dashboard_application_logic_is_preserved(self):
        self.assertIn("async function loadDashboard()", self.app)
        self.assertIn("function renderDashboardResults()", self.app)
        self.assertIn("function renderFollowupsList(followups)", self.app)


if __name__ == "__main__":
    unittest.main()
