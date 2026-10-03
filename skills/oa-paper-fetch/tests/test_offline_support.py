"""The harness must reject live access even when a backend swallows errors."""
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest import mock
import urllib.request

from offline_support import ROOT, offline_environment, run_cli
import config
import institutional_fetch
import oa_fetch


class OfflineSupportTests(unittest.TestCase):
    def test_unmocked_access_is_blocked_even_if_caught(self):
        actions = (
            lambda: urllib.request.urlopen("https://example.org"),
            lambda: urllib.request.build_opener().open("https://example.org"),
            lambda: institutional_fetch._load_playwright(),
            lambda: institutional_fetch._launch(None, "unused", False),
            lambda: config.load_config(config.DEFAULT_CONFIG_PATH),
        )
        for action in actions:
            with self.subTest(action=action), self.assertRaises(AssertionError):
                with offline_environment():
                    try:
                        action()
                    except AssertionError:
                        pass
        with self.assertRaises(AssertionError), offline_environment(), socket.socket() as sock:
            sock.connect(("127.0.0.1", 9))

    def test_real_config_is_rejected_before_reading_preferences(self):
        with TemporaryDirectory() as tmp:
            forbidden_config = Path(tmp) / "user-config.json"
            with (
                mock.patch.object(config, "DEFAULT_CONFIG_PATH", forbidden_config),
                mock.patch.object(sys, "argv", ["oa_fetch.py", "--config", str(forbidden_config),
                                               "--out", tmp, "--doi", "10.1000/test", "--oa-only"]),
                self.assertRaises(AssertionError), offline_environment(),
            ):
                oa_fetch.main()

    def test_child_process_cannot_enter_unmocked_institutional_access(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = root / "profile"
            profile.mkdir()
            (profile / "marker").write_text("fixture", encoding="utf-8")
            result = run_cli(
                [sys.executable, str(ROOT / "oa_fetch.py"), "--institutional-login",
                 "--config", str(root / "config.json"), "--browser-profile", str(profile)],
                capture_output=True, text=True,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unmocked network or browser access", result.stderr)
