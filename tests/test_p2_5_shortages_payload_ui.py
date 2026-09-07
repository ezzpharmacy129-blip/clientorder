import unittest
from pathlib import Path

class P25ShortagesPayloadUITests(unittest.TestCase):
    def test_whatsapp_shortages_returns_minimal_customer_shape(self):
        s=Path("app.py").read_text(encoding="utf-8")
        start=s.index('@app.get("/api/whatsapp/shortages")')
        end=s.index('\n@app.get("/api/whatsapp/shortages/grouped")', start)
        route=s[start:end]
        for key in ('"Order_ID"', '"Customer_Name"', '"Phone"', '"Order_Date"', '"Shortage_Items"'):
            self.assertIn(key, route)
        self.assertIn('_customer_shortage_items(order)', route)
        self.assertNotIn('"Items": order.get("Items")', route)

    def test_shortage_card_shows_required_customer_fields(self):
        s=Path("static/app.js").read_text(encoding="utf-8")
        self.assertIn("طلب #", s)
        self.assertIn("رقم الهاتف غير مسجل", s)
        self.assertIn("shortage-products", s)

if __name__=="__main__":
    unittest.main()
