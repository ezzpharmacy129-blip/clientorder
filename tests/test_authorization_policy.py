import unittest
from flask import Flask

from authorization_policy import ADMIN_EXACT, ADMIN_PREFIXES, is_admin_required, install_authorization


class AuthorizationPolicyTests(unittest.TestCase):
    def test_admin_routes_are_admin_only(self):
        self.assertTrue(is_admin_required("/api/admin/users", "GET"))
        self.assertTrue(is_admin_required("/api/admin/users/u1/toggle", "POST"))

    def test_destructive_routes_are_admin_only(self):
        for method, path in [
            ("POST", "/api/data/reset"),
            ("POST", "/api/backups/restore"),
            ("POST", "/api/import-data"),
            ("PUT", "/api/message-templates"),
            ("DELETE", "/api/orders/ORD-1"),
        ]:
            self.assertTrue(is_admin_required(path, method))

    def test_message_templates_remain_available_to_employees(self):
        self.assertFalse(is_admin_required("/api/message-templates", "PUT"))
        self.assertFalse(is_admin_required("/api/message-templates/reset", "POST"))

    def test_normal_employee_operations_are_not_admin_only(self):
        for method, path in [
            ("GET", "/api/orders"),
            ("POST", "/api/orders"),
            ("PUT", "/api/orders/ORD-1"),
            ("POST", "/api/orders/ORD-1/availability"),
            ("POST", "/api/orders/ORD-1/contact"),
            ("POST", "/api/orders/ORD-1/pickup"),
            ("POST", "/api/orders/ORD-1/cancel"),
            ("POST", "/api/whatsapp/open/ORD-1"),
            ("POST", "/api/pharmacy-shortages"),
            ("PUT", "/api/pharmacy-shortages/S1"),
        ]:
            self.assertFalse(is_admin_required(path, method))

    def test_route_guard_rejects_non_admin(self):
        app = Flask(__name__)
        app.secret_key = "test"

        current = {"user": {"user_id": "u1", "role": "employee"}}
        app.extensions["ezz_auth"] = {"current_user": lambda: current["user"]}
        install_authorization(app)

        @app.delete("/api/orders/ORD-1")
        def delete_order():
            return {"ok": True}

        response = app.test_client().delete("/api/orders/ORD-1")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "غير مصرح لك بهذا الإجراء")

    def test_route_guard_allows_admin(self):
        app = Flask(__name__)
        app.secret_key = "test"

        current = {"user": {"user_id": "u1", "role": "admin"}}
        app.extensions["ezz_auth"] = {"current_user": lambda: current["user"]}
        install_authorization(app)

        @app.delete("/api/orders/ORD-1")
        def delete_order():
            return {"ok": True}

        response = app.test_client().delete("/api/orders/ORD-1")
        self.assertEqual(response.status_code, 200)

if __name__ == "__main__":
    unittest.main()
