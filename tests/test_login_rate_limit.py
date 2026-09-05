import unittest

from flask import Flask

from login_rate_limit import install, _attempts, _lock


class LoginRateLimitTests(unittest.TestCase):
    def setUp(self):
        with _lock:
            _attempts.clear()

    def make_app(self):
        app = Flask(__name__)
        app.secret_key = "test"

        @app.post("/login")
        def login():
            if request_form(app) != "good":
                return "bad", 401
            return "ok", 302, {"Location": "/"}

        install(app)
        return app

    def test_blocks_after_five_failures(self):
        app = self.make_app()
        client = app.test_client()

        for _ in range(5):
            response = client.post("/login", data={"username": "alice", "password": "bad"})
            self.assertEqual(response.status_code, 401)

        response = client.post("/login", data={"username": "alice", "password": "bad"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.get_json()["code"], "login_rate_limited")
        self.assertTrue(response.headers.get("Retry-After"))

    def test_success_clears_failures(self):
        app = self.make_app()
        client = app.test_client()

        for _ in range(4):
            response = client.post("/login", data={"username": "alice", "password": "bad"})
            self.assertEqual(response.status_code, 401)

        response = client.post("/login", data={"username": "alice", "password": "good"})
        self.assertEqual(response.status_code, 302)

        response = client.post("/login", data={"username": "alice", "password": "bad"})
        self.assertEqual(response.status_code, 401)


def request_form(app):
    from flask import request
    return request.form.get("password")


if __name__ == "__main__":
    unittest.main()
