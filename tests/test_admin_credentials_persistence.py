from pathlib import Path
import unittest


class AdminCredentialsPersistenceTests(unittest.TestCase):
    def test_admin_env_credentials_are_seed_only(self):
        source = Path(__file__).resolve().parents[1].joinpath("auth_pg.py").read_text(encoding="utf-8")
        marker = "def ensure_pg_users():"
        start = source.index(marker)
        end = source.index("def migrate_legacy_sqlite():", start)
        block = source[start:end]

        self.assertIn("ON CONFLICT(username) DO NOTHING", block)
        self.assertNotIn("password_hash=EXCLUDED.password_hash", block)
        self.assertNotIn("role='admin',\n                        active=TRUE", block)


if __name__ == "__main__":
    unittest.main()
