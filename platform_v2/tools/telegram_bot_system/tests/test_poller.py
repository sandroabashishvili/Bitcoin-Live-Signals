from __future__ import annotations

import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from platform_v2.tools.telegram_bot_system import poller


class TelegramPollerBackoffTests(unittest.TestCase):
    def test_progressive_network_backoff_is_capped(self) -> None:
        values = [
            poller._progressive_backoff_seconds(failure_count)
            for failure_count in range(1, 9)
        ]
        self.assertEqual(values, [2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 60.0, 60.0])

    def test_retry_after_header_wins_for_rate_limit(self) -> None:
        error = urllib.error.HTTPError(
            url="https://api.telegram.org",
            code=429,
            msg="Too Many Requests",
            hdrs={"Retry-After": "42"},
            fp=None,
        )
        self.assertEqual(
            poller._retry_after_seconds(error, consecutive_failures=3),
            42.0,
        )

    def test_permanent_auth_error_uses_long_backoff(self) -> None:
        error = urllib.error.HTTPError(
            url="https://api.telegram.org",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None,
        )
        self.assertEqual(
            poller._retry_after_seconds(error, consecutive_failures=1),
            300.0,
        )


class TelegramPollerLockTests(unittest.TestCase):
    def test_second_listener_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "listener.lock"
            with patch.object(poller, "_LISTENER_LOCK_PATH", lock_path):
                with poller._listener_lock():
                    with self.assertRaises(poller.ListenerAlreadyRunningError):
                        with poller._listener_lock():
                            self.fail("The second listener lock must not be acquired.")


if __name__ == "__main__":
    unittest.main()
