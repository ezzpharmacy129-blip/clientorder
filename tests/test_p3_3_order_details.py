import unittest
from pathlib import Path


class P33OrderDetailsTests(unittest.TestCase):
    def test_order_details_style_exists_and_targets_existing_modal_parts(self):
        css = Path("static/p3_3_order_details.css").read_text(encoding="utf-8")
        for token in (
            "#order-modal .order-head",
            "#order-modal .detail-grid",
            "#order-modal .items-detail",
            "#order-modal .contact-status-panel",
            "#order-modal .detail-actions",
            "#order-modal .activity-log",
            "@media(max-width:720px)",
        ):
            self.assertIn(token, css)

    def test_core_loads_p33_stylesheet_once(self):
        source = Path("static/core.js").read_text(encoding="utf-8")
        self.assertIn('data-ezz-style="p3-3-order-details"', source)
        self.assertIn("/static/p3_3_order_details.css?v=20260907-p33", source)

    def test_order_details_behavior_stays_in_app_js(self):
        source = Path("static/app.js").read_text(encoding="utf-8")
        self.assertIn("async function details(id)", source)
        self.assertIn("saveContactStatus", source)
        self.assertIn("openAvailability", source)
        self.assertIn("cancelOrder", source)
        self.assertIn("modal-undo", source)


if __name__ == "__main__":
    unittest.main()
