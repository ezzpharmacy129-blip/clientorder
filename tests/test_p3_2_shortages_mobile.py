import unittest
from pathlib import Path


class P32ShortagesMobileTests(unittest.TestCase):
    def test_shortages_stylesheet_owns_mobile_card_layout(self):
        css = Path("static/daily_shortages.css").read_text(encoding="utf-8")
        self.assertIn("P3.2 — mobile cards for customer shortages", css)
        self.assertIn(".daily-shortages-table thead{display:none}", css)
        self.assertIn(".daily-shortages-table tr{display:block", css)
        self.assertIn("content:\"رقم الطلب\"", css)
        self.assertIn("content:\"العميل\"", css)
        self.assertIn("content:\"الهاتف\"", css)

    def test_shortages_desktop_contract_remains_present(self):
        css = Path("static/daily_shortages.css").read_text(encoding="utf-8")
        self.assertIn("min-width:960px", css)
        self.assertIn("position:sticky", css)
        self.assertIn("data-shortages-view", Path("templates/index.html").read_text(encoding="utf-8"))

    def test_existing_independent_send_actions_remain_in_markup(self):
        source = Path("templates/index.html").read_text(encoding="utf-8")
        for category in ("pharmacy", "customer", "all"):
            self.assertIn(f'data-send-shortages="{category}"', source)


if __name__ == "__main__":
    unittest.main()
