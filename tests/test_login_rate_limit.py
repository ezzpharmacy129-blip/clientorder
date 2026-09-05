import unittest

from login_rate_limit import (
    MAX_FAILURES,
    WINDOW_SECONDS,
    _attempts,
    _lock,
    clear,
    is_limited,
    record_failure,
)


class LoginRateLimitTests(unittest.TestCase):
    def setUp(self):
        with _lock:
            _attempts.clear()

    def test_blocks_after_five_failures(self):
        ip = "203.0.113.10"
        username = "alice"

        for i in range(MAX_FAILURES):
            count, _ = record_failure(ip, username, now=1000 + i)
            self.assertEqual(count, i + 1)
            limited, _ = is_limited(ip, username, now=1000 + i)
            self.assertEqual(limited, i + 1 >= MAX_FAILURES)

        limited, retry_after = is_limited(ip, username, now=1005)
        self.assertTrue(limited)
        self.assertGreater(retry_after, 0)

    def test_success_clear_allows_login_again(self):
        ip = "203.0.113.20"
        username = "alice"

        for i in range(MAX_FAILURES):
            record_failure(ip, username, now=2000 + i)

        limited, _ = is_limited(ip, username, now=2005)
        self.assertTrue(limited)

        clear(ip, username)

        limited, retry_after = is_limited(ip, username, now=2005)
        self.assertFalse(limited)
        self.assertEqual(retry_after, 0)

    def test_window_expires(self):
        ip = "203.0.113.30"
        username = "alice"

        for i in range(MAX_FAILURES):
            record_failure(ip, username, now=3000 + i)

        limited, _ = is_limited(ip, username, now=3000 + MAX_FAILURES + WINDOW_SECONDS)
        self.assertFalse(limited)

    def test_keys_are_separated_by_ip_and_username(self):
        record_failure("203.0.113.40", "alice", now=4000)
        record_failure("203.0.113.41", "alice", now=4000)
        record_failure("203.0.113.40", "bob", now=4000)

        self.assertEqual(len(_attempts), 3)


if __name__ == "__main__":
    unittest.main()
