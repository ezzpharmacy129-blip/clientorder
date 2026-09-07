import unittest
from unittest.mock import patch
from flask import Flask

import production_bootstrap


class ProductionBootstrapTests(unittest.TestCase):
    def test_non_cloud_backend_is_not_modified(self):
        app = Flask(__name__)

        class LocalDb:
            __module__ = "db"

        self.assertFalse(production_bootstrap.install_production_security(app, LocalDb()))
        self.assertNotIn("ezz_production_security", app.extensions)

    def test_cloud_backend_installs_each_security_layer_once(self):
        app = Flask(__name__)

        class CloudDb:
            __module__ = "cloud_db"

        calls = []
        with patch("auth_pg.install_auth", side_effect=lambda a, d: calls.append("auth")), \
             patch("authorization_policy.install_authorization", side_effect=lambda a: calls.append("authorization")), \
             patch("auth_security_extensions.install_security_extensions", side_effect=lambda a, d: calls.append("extensions")):
            self.assertTrue(production_bootstrap.install_production_security(app, CloudDb()))
            self.assertTrue(production_bootstrap.install_production_security(app, CloudDb()))

        self.assertEqual(calls, ["auth", "authorization", "extensions"])
        self.assertEqual(app.extensions["ezz_production_security"], {"installed": True, "cloud": True})
        self.assertTrue(getattr(app, "_ezz_production_security_bootstrapped", False))


if __name__ == "__main__":
    unittest.main()
