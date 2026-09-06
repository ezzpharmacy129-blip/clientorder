import unittest
from flask import Flask

from authorization_policy import install_authorization

class P06AuditTraceabilityTests(unittest.TestCase):
    def setUp(self):
        self.app=Flask(__name__)
        self.app.secret_key="test"
        self.events=[]
        self.app.extensions["ezz_auth"]={
            "current_user": lambda: {"user_id":"u1","username":"pharmacist","name":"صيدلي الاختبار","role":"employee"},
            "audit": lambda **kw: self.events.append(kw),
        }
        install_authorization(self.app)

    def test_employee_identity_is_the_audit_actor(self):
        actor=self.app.extensions["ezz_auth"]["current_user"]()
        self.assertEqual(actor["name"],"صيدلي الاختبار")
        self.assertEqual(actor["username"],"pharmacist")

    def test_critical_operation_audit_events_have_action_and_note(self):
        audit=self.app.extensions["ezz_auth"]["audit"]
        audit(action="Import Data", note="استيراد test.xlsx")
        audit(action="Restore Backup", note="استعادة backup_auto.zip")
        audit(action="Create Backup", note="إنشاء backup_manual.zip")
        audit(action="Reset Data", note="مسح بيانات النظام بالكامل")
        self.assertEqual(len(self.events),4)
        for event in self.events:
            self.assertTrue(event["action"])
            self.assertTrue(event["note"])

    def test_destructive_routes_remain_admin_only(self):
        self.assertTrue(self.app.extensions["ezz_authorization"]["is_admin_required"]("/api/data/reset","POST"))
        self.assertTrue(self.app.extensions["ezz_authorization"]["is_admin_required"]("/api/backups/restore","POST"))
        self.assertTrue(self.app.extensions["ezz_authorization"]["is_admin_required"]("/api/import-data","POST"))
        self.assertTrue(self.app.extensions["ezz_authorization"]["is_admin_required"]("/api/orders/ORD-1","DELETE"))

if __name__=="__main__": unittest.main()
