"""Run external tools and manage build paths, locking, compilation and PDF publication."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import TextIO

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None  # type: ignore[assignment]


GENERATED_SUFFIXES = (
    ".aux",
    ".log",
    ".out",
    ".toc",
    ".xdv",
    ".fls",
    ".fdb_latexmk",
    ".synctex.gz",
)


INTERMEDIATE_NAMES = ("report_body.md", "metadata.yaml", "prepare_report.json", "postprocess_qa.json")


DEFAULT_COMMAND_TIMEOUT = 180.0


MAX_COMMAND_OUTPUT_CHARS = 16_000


def bounded_output(text: str, limit: int = MAX_COMMAND_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    marker = "\n... 0 characters omitted ...\n"
    while True:
        kept = max(0, limit - len(marker))
        omitted = len(text) - kept
        updated = f"\n... {omitted} characters omitted ...\n"
        if len(updated) == len(marker):
            marker = updated
            break
        marker = updated
    kept = max(0, limit - len(marker))
    head = kept // 2
    tail = kept - head
    return text[:head] + marker + (text[-tail:] if tail else "")


def command_output(stdout: str | bytes | None, stderr: str | bytes | None) -> str:
    streams: list[str] = []
    for label, value in (("stdout", stdout), ("stderr", stderr)):
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        if value and value.strip():
            streams.append(f"[{label}]\n{value.strip()}")
    return bounded_output("\n".join(streams))


def run(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: float = DEFAULT_COMMAND_TIMEOUT,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            cmd,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        details = command_output(exc.stdout, exc.stderr)
        suffix = f"\n{details}" if details else ""
        raise RuntimeError(f"command timed out after {timeout:g}s: {cmd[0]}{suffix}") from exc
    if completed.returncode != 0:
        details = command_output(completed.stdout, completed.stderr)
        suffix = f"\n{details}" if details else ""
        raise RuntimeError(f"command failed with exit code {completed.returncode}: {cmd[0]}{suffix}")
    return completed


def require_tool(name: str, purpose: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"{name} is required for {purpose}, but was not found on PATH.")
    return path


def pandoc_no_highlight_arg(pandoc_path: str, timeout: float = DEFAULT_COMMAND_TIMEOUT) -> str:
    completed = run([pandoc_path, "--help"], timeout=timeout)
    if "--syntax-highlighting" in completed.stdout:
        return "--syntax-highlighting=none"
    return "--no-highlight"


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def project_path(path: Path, project_dir: Path) -> Path:
    return path if path.is_absolute() else project_dir / path


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def validate_output_path(path: Path, source: Path, expected_suffix: str, option: str) -> None:
    if path.suffix.lower() != expected_suffix:
        raise RuntimeError(f"{option} must end with {expected_suffix}: {path}")
    if path.exists() and path.is_dir():
        raise RuntimeError(f"{option} must be a file path, not a directory: {path}")
    if paths_are_same(path, source):
        raise RuntimeError(f"{option} must not overwrite the source Markdown: {path}")


def paths_are_same(first: Path, second: Path) -> bool:
    if first.resolve() == second.resolve():
        return True
    if first.exists() and second.exists():
        try:
            return first.samefile(second)
        except OSError:
            return False
    return False


def validate_generated_path_collisions(
    source: Path,
    work_dir: Path,
    tex_path: Path,
    pdf_path: Path,
) -> None:
    generated = [work_dir / name for name in INTERMEDIATE_NAMES]
    for path in generated:
        if paths_are_same(source, path):
            raise RuntimeError(f"source Markdown conflicts with a generated intermediate: {path}")
    if paths_are_same(tex_path, pdf_path):
        raise RuntimeError("--tex and --pdf must not refer to the same file")


def acquire_project_lock(project_dir: Path, timeout: float) -> TextIO:
    digest = hashlib.sha256(str(project_dir.resolve()).encode("utf-8")).hexdigest()[:20]
    lock_path = Path(tempfile.gettempdir()) / f"md-course-report-{digest}.lock"
    handle = lock_path.open("a+", encoding="utf-8")
    deadline = time.monotonic() + timeout
    while True:
        try:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                import msvcrt

                handle.seek(0, 2)
                if handle.tell() == 0:
                    handle.write("\0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return handle
        except OSError:
            if time.monotonic() >= deadline:
                handle.close()
                raise RuntimeError(f"another build still holds the project lock after {timeout:g}s: {project_dir}")
            time.sleep(0.05)


def atomic_copy(source: Path, destination: Path) -> None:
    if destination.exists() and destination.is_dir():
        raise RuntimeError(f"output PDF must be a file path, not a directory: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
        delete=False,
    )
    temporary = Path(handle.name)
    handle.close()
    try:
        shutil.copy2(source, temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def validate_pdf_file(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"compiled PDF was not found: {path}")
    with path.open("rb") as handle:
        header = handle.read(5)
    if header != b"%PDF-" or path.stat().st_size <= 5:
        raise RuntimeError(f"compiler produced an invalid PDF file: {path}")


def relative_project_path(path: Path, project_dir: Path) -> str:
    try:
        return path.resolve().relative_to(project_dir.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def copy_logo_into_project(logo: str, work_dir: Path, project_dir: Path) -> str:
    logo_path = Path(logo)
    if not logo_path.is_absolute():
        return logo_path.as_posix()
    if not logo_path.exists():
        raise RuntimeError(f"--logo file was not found: {logo_path}")
    suffix = logo_path.suffix if logo_path.suffix else ".png"
    copied_logo = work_dir / f"user_logo{suffix}"
    shutil.copy2(logo_path, copied_logo)
    return relative_project_path(copied_logo, project_dir)


def compile_tex(
    tex_path: Path,
    expected_pdf: Path,
    cwd: Path,
    timeout: float,
    keep_intermediates: bool,
) -> None:
    expected_pdf.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="md-course-report-compile-", dir=expected_pdf.parent) as tmp:
        compile_dir = Path(tmp)
        tectonic = shutil.which("tectonic")
        if tectonic:
            command = [tectonic, "--outdir", str(compile_dir)]
            if keep_intermediates:
                command.extend(["--keep-intermediates", "--keep-logs"])
            command.append(str(tex_path))
            run(command, cwd=cwd, timeout=timeout)
        else:
            xelatex = shutil.which("xelatex")
            if not xelatex:
                raise RuntimeError("No LaTeX compiler found. Install or expose tectonic, or provide xelatex on PATH.")
            for _ in range(2):
                run(
                    [
                        xelatex,
                        "-interaction=nonstopmode",
                        "-halt-on-error",
                        "-file-line-error",
                        f"-output-directory={compile_dir}",
                        str(tex_path),
                    ],
                    cwd=cwd,
                    timeout=timeout,
                )

        produced_pdf = compile_dir / tex_path.with_suffix(".pdf").name
        validate_pdf_file(produced_pdf)
        atomic_copy(produced_pdf, expected_pdf)
        if keep_intermediates:
            base_name = tex_path.stem
            for suffix in GENERATED_SUFFIXES:
                generated = compile_dir / f"{base_name}{suffix}"
                if generated.is_file():
                    shutil.copy2(generated, Path(str(tex_path.with_suffix("")) + suffix))
    validate_pdf_file(expected_pdf)
