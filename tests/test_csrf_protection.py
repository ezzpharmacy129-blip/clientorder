import unittest
from flask import Flask, jsonify

from csrf_protection import install_csrf


def make_app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    install_csrf(app)

    @app.get("/api/read")
    def read():
        return jsonify({"ok": True})

    @app.post("/api/write")
    def write():
        return jsonify({"ok": True})

    @app.post("/api/form-write")
    def form_write():
        return jsonify({"ok": True})

    return app


class CSRFProtectionTests(unittest.TestCase):
    def test_safe_get_does_not_require_csrf(self):
        client = make_app().test_client()
        response = client.get("/api/read")
        self.assertEqual(response.status_code, 200)

    def test_post_without_csrf_is_rejected(self):
        client = make_app().test_client()
        response = client.post("/api/write", json={"value": 1})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["code"], "csrf_failed")

    def test_post_with_session_csrf_header_is_allowed(self):
        app = make_app()
        client = app.test_client()
        with client.session_transaction() as session:
            token = "test-token"
            session["_csrf_token"] = token

        response = client.post(
            "/api/write",
            json={"value": 1},
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(response.status_code, 200)

    def test_form_csrf_token_is_allowed(self):
        app = make_app()
        client = app.test_client()
        with client.session_transaction() as session:
            token = "form-token"
            session["_csrf_token"] = token

        response = client.post("/api/form-write", data={"csrf_token": token})
        self.assertEqual(response.status_code, 200)

    def test_invalid_csrf_is_rejected(self):
        app = make_app()
        client = app.test_client()
        with client.session_transaction() as session:
            session["_csrf_token"] = "expected"

        response = client.post(
            "/api/write",
            json={"value": 1},
            headers={"X-CSRF-Token": "wrong"},
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
