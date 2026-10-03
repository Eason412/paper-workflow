"""Provide smoke-test paths, process execution and result checks shared by test cases."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


EXAMPLES = ROOT / "examples"


SCRIPTS = ROOT / "scripts"


BUILD = SCRIPTS / "build_course_report.py"


LOCAL_DEFAULT_LOGO = ROOT / "assets" / "njust_logo.png"


COURSE = "示例课程"


STUDENT_NAME = "示例学生"


STUDENT_ID = "0000000000"


SMOKE_TIMEOUT = 240


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=SMOKE_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        message = f"smoke command timed out after {SMOKE_TIMEOUT}s: {cmd[0]}"
        return subprocess.CompletedProcess(cmd, 124, stdout, (stderr + "\n" + message).strip())


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def fail(message: str, details: object | None = None) -> dict[str, object]:
    result: dict[str, object] = {"ok": False, "error": message}
    if details is not None:
        result["details"] = details
    return result


def check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)
