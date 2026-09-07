import unittest
from pathlib import Path

class P24DashboardPayloadTests(unittest.TestCase):
    def test_dashboard_reuses_prebuilt_payloads_for_filters(self):
        source=Path("app.py").read_text(encoding="utf-8")
        start=source.index('@app.get("/api/dashboard")')
        end=source.index('\ndef active_followups(orders):', start)
        route=source[start:end]
        self.assertIn("dashboard_entries = [(order, _dashboard_order_payload(order)) for order in orders]", route)
        self.assertIn('"all": dashboard_orders', route)
        self.assertIn('"pending": [payload for order, payload in dashboard_entries if _order_has_pending_item(order)]', route)
        self.assertIn('"overdue": [payload for order, payload in dashboard_entries if (', route)
        self.assertNotIn("_dashboard_order_payload(o) for o in orders", route)

    def test_dashboard_filter_contract_is_preserved(self):
        source=Path("app.py").read_text(encoding="utf-8")
        start=source.index('@app.get("/api/dashboard")')
        end=source.index('\ndef active_followups(orders):', start)
        route=source[start:end]
        for key in ('"all"', '"pending"', '"available"', '"awaiting_reply"', '"pickup_pending"', '"picked_up"', '"today_followup"', '"overdue"'):
            self.assertIn(key, route)
        self.assertIn('"dashboard_filters": dashboard_filters', route)

if __name__=="__main__":
    unittest.main()
