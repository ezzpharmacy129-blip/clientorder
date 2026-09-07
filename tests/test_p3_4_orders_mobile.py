import unittest
from pathlib import Path


class P34OrdersMobileTests(unittest.TestCase):
    def setUp(self):
        self.css = Path("static/p3_4_orders_mobile.css").read_text(encoding="utf-8")
        self.core = Path("static/core.js").read_text(encoding="utf-8")
        self.index = Path("templates/index.html").read_text(encoding="utf-8")
        self.app = Path("static/app.js").read_text(encoding="utf-8")

    def test_mobile_layer_targets_all_orders_only(self):
        self.assertIn("@media (max-width: 720px)", self.css)
        self.assertIn('#view-orders .orders-table thead', self.css)
        self.assertIn('#view-orders .orders-table tbody tr', self.css)
        self.assertIn('#view-orders .orders-table tbody td:nth-child(1)::before', self.css)
        self.assertIn('content: "رقم الطلب"', self.css)
        self.assertIn('content: "العميل"', self.css)
        self.assertIn('content: "الجوال"', self.css)
        self.assertIn('content: "الإجراء"', self.css)
        self.assertIn('@media (max-width: 420px)', self.css)

    def test_orders_table_has_expected_twelve_columns(self):
        marker = '<table class="orders-table"><thead><tr><th>رقم الطلب</th>'
        self.assertIn(marker, self.index)
        expected = [
            "رقم الطلب", "العميل", "الجوال", "المنتجات", "إجمالي الكمية",
            "تاريخ الطلب", "التوفر", "الحالة", "التواصل", "آخر متابعة",
            "موعد المتابعة", "الإجراء",
        ]
        for label in expected:
            self.assertIn(f"<th>{label}</th>", self.index)

    def test_core_loader_is_dedicated_to_p34(self):
        self.assertIn("P3.4", self.core)
        self.assertIn('data-ezz-style="p3-4-orders-mobile"', self.core)
        self.assertIn('/static/p3_4_orders_mobile.css?v=20260907-p34', self.core)

    def test_application_logic_is_not_replaced_by_mobile_css(self):
        self.assertIn("async function details(id)", self.app)
        self.assertIn("function loadOrders", self.app)
        self.assertIn("orders-table-body", self.app)


if __name__ == "__main__":
    unittest.main()
