"""Shared offline guards for unittest and child CLI processes."""
from contextlib import ExitStack, contextmanager
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest import mock
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config
import institutional_fetch


@contextmanager
def offline_environment():
    """Fail even when production code catches an unmocked access error."""
    attempted = []
    default_config = config.DEFAULT_CONFIG_PATH.resolve()
    real_load_config = config.load_config
    def forbidden(*args, **kwargs):
        attempted.append("unmocked network or browser access")
        raise AssertionError(attempted[-1])

    def load_config(path, *args, **kwargs):
        if Path(path).expanduser().resolve() == default_config:
            attempted.append("real user configuration access")
            raise AssertionError(attempted[-1])
        return real_load_config(path, *args, **kwargs)

    with ExitStack() as stack:
        for target, attribute in (
            (socket.socket, "connect"), (socket.socket, "connect_ex"),
            (urllib.request, "urlopen"),
            (urllib.request.OpenerDirector, "open"),
            (institutional_fetch, "_load_playwright"),
            (institutional_fetch, "_launch"),
        ):
            stack.enter_context(mock.patch.object(target, attribute, side_effect=forbidden))
        stack.enter_context(mock.patch.object(config, "load_config", side_effect=load_config))
        try:
            yield
        finally:
            if attempted:
                raise AssertionError("; ".join(attempted))


class OfflineTestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        guard = offline_environment()
        guard.__enter__()
        self.addCleanup(guard.__exit__, None, None, None)


def run_cli(command, **kwargs):
    """Apply offline guards inside child CLI processes too."""
    bootstrap = """
import runpy, sys
sys.path.insert(0, sys.argv.pop(1))
from offline_support import offline_environment
sys.argv = sys.argv[1:]
with offline_environment():
    runpy.run_path(sys.argv[0], run_name="__main__")
"""
    return subprocess.run(
        [command[0], "-B", "-c", bootstrap, str(ROOT / "tests"), *command[1:]],
        timeout=30, **kwargs,
    )
