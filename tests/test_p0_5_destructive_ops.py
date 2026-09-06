import unittest
from flask import Flask

from authorization_policy import install_authorization, is_admin_required


class P05DestructiveOpsTests(unittest.TestCase):
    def _app(self, role):
        app = Flask(__name__)
        app.secret_key = "test"
        app.extensions["ezz_auth"] = {
            "current_user": lambda: {"user_id": "u1", "role": role, "name": "اختبار"}
        }
        install_authorization(app)
        app.config["delete_called"] = False

        @app.delete("/api/orders/ORD-1")
        def delete_order():
            app.config["delete_called"] = True
            return {"ok": True}

        return app

    def test_delete_requires_server_confirmation(self):
        app = self._app("admin")
        response = app.test_client().delete("/api/orders/ORD-1")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "للتأكيد اكتب: حذف الطلب")
        self.assertFalse(app.config["delete_called"])

    def test_delete_rejects_wrong_confirmation(self):
        app = self._app("admin")
        response = app.test_client().delete("/api/orders/ORD-1", json={"confirmation": "حذف كل البيانات"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(app.config["delete_called"])

    def test_delete_allows_admin_after_confirmation(self):
        app = self._app("admin")
        response = app.test_client().delete("/api/orders/ORD-1", json={"confirmation": "حذف الطلب"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(app.config["delete_called"])

    def test_employee_cannot_delete_even_with_confirmation(self):
        app = self._app("employee")
        response = app.test_client().delete("/api/orders/ORD-1", json={"confirmation": "حذف الطلب"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(app.config["delete_called"])

    def test_destructive_admin_policy_surface(self):
        self.assertTrue(is_admin_required("/api/data/reset", "POST"))
        self.assertTrue(is_admin_required("/api/backups/restore", "POST"))
        self.assertTrue(is_admin_required("/api/import-data", "POST"))
        self.assertTrue(is_admin_required("/api/orders/ORD-1", "DELETE"))


if __name__ == "__main__":
    unittest.main()
