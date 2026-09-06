import unittest
from pathlib import Path

class P12ShortagesContractTests(unittest.TestCase):
    def test_unified_api_exists(self):
        source=Path("app.py").read_text(encoding="utf-8")
        self.assertIn('@app.get("/api/shortages")',source)
        self.assertIn('"customer":customer_rows',source)
        self.assertIn('"pharmacy":pending_pharmacy',source)
        self.assertIn('"pharmacy_available":available_pharmacy',source)

    def test_all_shortages_excludes_provided_pharmacy_rows(self):
        source=Path("app.py").read_text(encoding="utf-8")
        self.assertIn('"all":customer_rows+pending_pharmacy',source)

    def test_ui_load_uses_one_shortages_request(self):
        source=Path("static/daily_shortages.js").read_text(encoding="utf-8")
        self.assertIn('api("/api/shortages")',source)
        self.assertNotIn('api("/api/pharmacy-shortages"),\n        api("/api/customer-shortages")',source)
        self.assertIn('state.pharmacyRows.filter(row => row.statusKey === "pending")',source)

if __name__=="__main__":unittest.main()
