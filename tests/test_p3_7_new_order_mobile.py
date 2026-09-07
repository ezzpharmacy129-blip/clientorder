import unittest
from pathlib import Path


class P37NewOrderMobileTests(unittest.TestCase):
    def setUp(self):
        self.css = Path("static/p3_7_new_order_mobile.css").read_text(encoding="utf-8")
        self.core = Path("static/core.js").read_text(encoding="utf-8")
        self.base_css = Path("static/style.min.css").read_text(encoding="utf-8")
        self.app = Path("static/app.js").read_text(encoding="utf-8")

    def test_mobile_layer_targets_new_order_only(self):
        self.assertIn("@media (max-width: 720px)", self.css)
        self.assertIn("@media (max-width: 420px)", self.css)
        self.assertIn("#view-new-order .order-form", self.css)
        self.assertIn("#view-new-order .product-row", self.css)
        self.assertIn("#view-new-order .form-actions", self.css)

    def test_existing_selectors_are_preserved(self):
        for selector in (".order-form", ".products-section", ".products-title", ".product-row", ".product-number", ".remove-product", ".form-actions", ".order-total-preview"):
            self.assertIn(selector, self.base_css)

    def test_new_order_application_logic_is_not_reimplemented(self):
        self.assertNotIn("fetch(", self.css)
        self.assertNotIn("apiFetch", self.css)
        self.assertIn("function switchView(v)", self.app)

    def test_core_loader_is_dedicated_to_p37(self):
        self.assertIn("P3.7", self.core)
        self.assertIn('data-ezz-style="p3-7-new-order-mobile"', self.core)
        self.assertIn('/static/p3_7_new_order_mobile.css?v=20260907-p37', self.core)


if __name__ == "__main__":
    unittest.main()
