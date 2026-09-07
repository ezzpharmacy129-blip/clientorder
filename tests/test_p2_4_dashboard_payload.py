import unittest
from pathlib import Path

class P24DashboardPayloadTests(unittest.TestCase):
    def test_dashboard_builds_each_order_payload_once(self):
        s=Path("app.py").read_text(encoding="utf-8")
        start=s.index('@app.get("/api/dashboard")')
        end=s.index('\ndef active_followups(orders):', start)
        route=s[start:end]
        self.assertEqual(route.count('_dashboard_order_payload(order)'), 1)
        self.assertNotIn('_dashboard_order_payload(o) for o in orders', route)
        self.assertIn('dashboard_entries = [(order, _dashboard_order_payload(order)) for order in orders]', route)

    def test_dashboard_filter_contract_is_preserved(self):
        s=Path("app.py").read_text(encoding="utf-8")
        start=s.index('@app.get("/api/dashboard")')
        end=s.index('\ndef active_followups(orders):', start)
        route=s[start:end]
        for key in ('"all"', '"pending"', '"available"', '"awaiting_reply"', '"pickup_pending"', '"picked_up"', '"today_followup"', '"overdue"'):
            self.assertIn(key, route)
        self.assertIn('"dashboard_filters": dashboard_filters', route)

if __name__=="__main__":
    unittest.main()
