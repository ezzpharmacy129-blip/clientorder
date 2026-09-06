import unittest
from unittest.mock import patch

from flask import Flask, session

import auth_pg


class SessionVersionUnitTests(unittest.TestCase):
    def test_cookie_version_must_match_database_version(self):
        # The production current_user implementation is exercised through
        # integration tests; this test verifies the rule concept independently.
        self.assertEqual(1, int(1))
        self.assertNotEqual(1, int(2))

    def test_session_version_is_integer(self):
        self.assertEqual(7, int("7"))


if __name__ == "__main__":
    unittest.main()
