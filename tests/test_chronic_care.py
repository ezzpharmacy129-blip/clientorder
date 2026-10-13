import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask


APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

_database_url = os.environ.pop("DATABASE_URL", None)
try:
    import chronic_care
finally:
    if _database_url is not None:
        os.environ["DATABASE_URL"] = _database_url


class ChronicCareUnitTests(unittest.TestCase):
    def test_saudi_phone_normalization(self):
        self.assertEqual(chronic_care._normalize_phone("05 1234 5678"), "966512345678")
        self.assertEqual(chronic_care._normalize_phone("+966 51 234 5678"), "966512345678")

    def test_refill_and_reminder_calculation(self):
        dispensed = datetime(2026, 10, 13, 9, 30, tzinfo=ZoneInfo("Asia/Riyadh"))
        refill, reminder = chronic_care.calculate_schedule(dispensed, 30)
        self.assertEqual(refill.isoformat(), "2026-11-12T09:30:00+03:00")
        self.assertEqual(reminder.isoformat(), "2026-11-09T09:30:00+03:00")

    def test_schema_is_additive_and_history_has_no_cascade_delete(self):
        sql = chronic_care.SCHEMA_SQL.upper()
        self.assertIn("CREATE TABLE IF NOT EXISTS CHRONIC_CUSTOMERS", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS CHRONIC_MEDICATIONS", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS CHRONIC_DISPENSES", sql)
        self.assertNotIn("DROP TABLE", sql)
        self.assertNotIn("ON DELETE CASCADE", sql)
        self.assertIn("ENABLE ROW LEVEL SECURITY", sql)

    def test_only_supported_statuses_are_available(self):
        expected = {"active", "postponed", "stopped", "needs_review"}
        self.assertEqual(chronic_care.CUSTOMER_STATUSES, expected)
        self.assertEqual(chronic_care.MEDICATION_STATUSES, expected)


@unittest.skipUnless(os.environ.get("CHRONIC_TEST_DATABASE_URL"), "integration database is not configured")
class ChronicCareIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = os.environ["CHRONIC_TEST_DATABASE_URL"]
        chronic_care._schema_ready = False
        chronic_care.ensure_schema(force=True)

    @classmethod
    def tearDownClass(cls):
        if cls.previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = cls.previous_url
        chronic_care._schema_ready = False

    def test_full_customer_medication_dispense_and_forecast_flow(self):
        customer = chronic_care.create_customer({
            "name": "عميل اختبار العلاج المزمن",
            "phone": "0500000099",
            "followup_status": "active",
            "reminder_consent": True,
        })
        medication = chronic_care.create_medication(customer["id"], {
            "name": "دواء اختبار",
            "strength": "10 mg",
            "status": "active",
        })
        dispensed_at = chronic_care._now().replace(hour=9, minute=0, second=0, microsecond=0)
        dispense = chronic_care.create_dispense(medication["id"], {
            "quantity": 30,
            "days_supply": 7,
            "dispensed_at": dispensed_at.isoformat(),
        }, {"id": "TEST", "name": "مختبر"})

        self.assertEqual(dispense["quantity"], 30)
        self.assertEqual(len(chronic_care.dispense_history(medication["id"])), 1)
        self.assertEqual(len(chronic_care.list_medications(search="دواء اختبار")), 1)
        self.assertEqual(len(chronic_care.list_medications(search="غير موجود")), 0)
        self.assertEqual(len(chronic_care.list_customers(search="عميل اختبار")), 1)
        self.assertEqual(chronic_care.dashboard_summary()["active_customers"], 1)
        report = chronic_care.forecast_report()
        self.assertEqual(report[0]["customer_count"], 1)
        self.assertEqual(report[0]["refill_operations"], 1)
        self.assertEqual(report[0]["expected_quantity"], 30)

    def test_pages_and_read_apis_render_for_authenticated_user(self):
        app = Flask(
            "chronic_care_test",
            template_folder=str(APP_DIR / "templates"),
            static_folder=str(APP_DIR / "static"),
        )
        app.secret_key = "chronic-care-test-only"
        app.jinja_env.globals["csrf_token"] = lambda: "test-token"
        app.extensions["ezz_auth"] = {"current_user": lambda: {"id": "TEST", "name": "مختبر"}}
        chronic_care.install_chronic_care(app)
        client = app.test_client()
        with client.session_transaction() as current_session:
            current_session["authenticated"] = True
            current_session["user_id"] = "TEST"
        self.assertEqual(client.get("/chronic-care").status_code, 200)
        self.assertEqual(client.get("/chronic-care/forecasts").status_code, 200)
        self.assertEqual(client.get("/api/chronic-care/dashboard").status_code, 200)
        self.assertEqual(client.get("/api/chronic-care/medications").status_code, 200)
        self.assertEqual(client.get("/api/chronic-care/forecasts").status_code, 200)


if __name__ == "__main__":
    unittest.main()


