import unittest
from pathlib import Path


class P36MobileHeaderTests(unittest.TestCase):
    def setUp(self):
        self.css = Path("static/p3_6_mobile_header.css").read_text(encoding="utf-8")
        self.core = Path("static/core.js").read_text(encoding="utf-8")
        self.index = Path("templates/index.html").read_text(encoding="utf-8")

    def test_mobile_header_has_dedicated_breakpoints(self):
        self.assertIn("@media (max-width: 720px)", self.css)
        self.assertIn("@media (max-width: 420px)", self.css)
        self.assertIn(".header-inner", self.css)
        self.assertIn(".main-nav", self.css)
        self.assertIn("overflow-x: auto", self.css)

    def test_navigation_contract_is_preserved(self):
        expected_views = (
            "dashboard", "orders", "shortages", "message-templates",
            "backups", "users", "vip-customers", "new-order",
        )
        for view in expected_views:
            self.assertIn(f'data-view="{view}"', self.index)
        self.assertIn('href="/logout"', self.index)

    def test_core_loader_is_dedicated_to_p36(self):
        self.assertIn("P3.6", self.core)
        self.assertIn('data-ezz-style="p3-6-mobile-header"', self.core)
        self.assertIn('/static/p3_6_mobile_header.css?v=20260907-p36', self.core)

    def test_no_application_logic_in_header_layer(self):
        self.assertNotIn("fetch(", self.css)
        self.assertNotIn("apiFetch", self.css)
        self.assertNotIn("data-action-category", self.css)


if __name__ == "__main__":
    unittest.main()
