#!/usr/bin/env python3
"""Build a Markdown course report through the bundled LaTeX workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from typing import TextIO

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None  # type: ignore[assignment]
from pathlib import Path


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


def command_output(stdout: str | bytes | None, stderr: str | bytes | None) -> str:
    streams: list[str] = []
    for label, value in (("stdout", stdout), ("stderr", stderr)):
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        if value and value.strip():
            streams.append(f"[{label}]\n{value.strip()}")
    return "\n".join(streams)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--course", default="")
    parser.add_argument("--student-name", default="")
    parser.add_argument("--student-id", default="")
    parser.add_argument("--logo", default="")
    parser.add_argument("--no-cover", action="store_true")
    parser.add_argument("--allow-slide-draft", action="store_true")
    parser.add_argument("--work-dir", type=Path, default=Path("latex"))
    parser.add_argument("--tex", type=Path, default=Path("course_report.tex"))
    parser.add_argument("--pdf", type=Path, default=Path("course_report.pdf"))
    parser.add_argument("--output-pdf", type=Path)
    parser.add_argument("--keep-intermediates", action="store_true")
    parser.add_argument("--skip-compile", action="store_true")
    parser.add_argument("--command-timeout", type=float, default=DEFAULT_COMMAND_TIMEOUT)
    return parser.parse_args()


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
    output_pdf: Path | None,
) -> None:
    generated = [work_dir / name for name in INTERMEDIATE_NAMES]
    for path in generated:
        if paths_are_same(source, path):
            raise RuntimeError(f"source Markdown conflicts with a generated intermediate: {path}")
    if paths_are_same(tex_path, pdf_path):
        raise RuntimeError("--tex and --pdf must not refer to the same file")
    if output_pdf is not None and paths_are_same(tex_path, output_pdf):
        raise RuntimeError("--tex and --output-pdf must not refer to the same file")


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
        return str(path.resolve().relative_to(project_dir.resolve()))
    except ValueError:
        return str(path.resolve())


def copy_logo_into_project(logo: str, work_dir: Path, project_dir: Path) -> str:
    logo_path = Path(logo)
    if not logo_path.is_absolute():
        return logo
    if not logo_path.exists():
        raise RuntimeError(f"--logo file was not found: {logo_path}")
    suffix = logo_path.suffix if logo_path.suffix else ".png"
    copied_logo = work_dir / f"user_logo{suffix}"
    shutil.copy2(logo_path, copied_logo)
    return relative_project_path(copied_logo, project_dir)


def validate_prepare_qa(report: dict[str, object]) -> list[str]:
    failures: list[str] = []
    qa = report.get("qa", {})
    if not isinstance(qa, dict):
        return ["prepare QA is not an object"]
    cover = report.get("cover", {})
    if not isinstance(cover, dict):
        return ["cover QA is not an object"]
    if qa.get("missing_images"):
        failures.append("image files are missing")
    if qa.get("unsafe_image_paths"):
        failures.append("image paths are absolute, remote, or outside the source Markdown directory")
    slide_draft = qa.get("probable_slide_draft")
    if (
        isinstance(slide_draft, dict)
        and slide_draft.get("detected") is True
        and slide_draft.get("allowed") is not True
    ):
        failures.append(
            "input looks like page-by-page lecture notes or a slide draft; rewrite it as a course report first "
            "or pass --allow-slide-draft to force conversion"
        )
    if cover.get("logo_path") and cover.get("logo_exists") is not True:
        failures.append("logo file is missing")
    if cover.get("logo_path") and cover.get("logo_inside_project") is not True:
        failures.append("logo path is absolute, remote, or outside the source Markdown directory")
    if qa.get("captions_with_manual_numbers"):
        failures.append("figure captions contain manual numbers")
    if qa.get("missing_reference_entries"):
        failures.append("citations are missing reference-list entries")
    if qa.get("invalid_citation_markers"):
        failures.append("citation markers use invalid numeric syntax")
    if qa.get("tables_without_adjacent_caption"):
        failures.append("Markdown pipe tables are missing adjacent Pandoc captions")
    if qa.get("invalid_table_captions"):
        failures.append("Markdown pipe table captions use unsupported syntax")
    if qa.get("table_captions_separated_by_blank_line"):
        failures.append("Markdown pipe table captions are separated by blank lines")
    if qa.get("table_captions_with_manual_numbers"):
        failures.append("table captions contain manual numbers")
    return failures


def validate_cover_fields(report: dict[str, object]) -> list[str]:
    cover = report.get("cover", {})
    if not isinstance(cover, dict):
        return []
    if cover.get("enabled") is False or cover.get("thesis") is True:
        return []
    if all(cover.get(key) for key in ("course", "studentname", "studentid")):
        return []
    return ["course, student name, and student ID are required for a course cover"]


def validate_postprocess_qa(qa: dict[str, object]) -> list[str]:
    failures: list[str] = []
    if qa.get("body_has_abstract_section") is not False:
        failures.append("body_has_abstract_section is not false")
    references_required = bool(qa.get("textsupcite_count") or qa.get("reference_labels"))
    if references_required and qa.get("references_section_found") is not True:
        failures.append("references section was not found after postprocessing")
    if qa.get("remaining_raw_citations_before_references") not in ([], None):
        failures.append("raw citation markers remain before references")
    if qa.get("remaining_unnumbered_display_math") != 0:
        failures.append("unnumbered display math remains")
    if qa.get("dangling_url_macro") is not False:
        failures.append("dangling URL macro remains")
    if qa.get("reference_urls"):
        failures.append("reference URLs remain")
    if qa.get("longtables_missing_caption") not in (0, None):
        failures.append("longtable captions are missing")
    if qa.get("longtables_missing_endfoot") not in (0, None):
        failures.append("longtable continuation footers are missing")
    if qa.get("longtables_missing_endlastfoot") not in (0, None):
        failures.append("longtable final-page footers are missing")
    if qa.get("longtables_missing_continued_caption") not in (0, None):
        failures.append("longtable continued captions are missing")
    if qa.get("longtable_headers_centered") is not True:
        failures.append("longtable headers are not centered")
    if qa.get("longtable_cells_centered") is not True:
        failures.append("longtable cells are not centered")
    if qa.get("longtable_columns_vertical_centered") is not True:
        failures.append("longtable columns are not vertically centered")
    if qa.get("table_captions_with_manual_numbers"):
        failures.append("manual table caption numbers remain")
    if qa.get("toc_section_font_size") != "4":
        failures.append("TOC level-1 entries are not four-size (官方: 一级标题/致谢/参考文献/附录 4号)")
    if qa.get("toc_section_is_bold") is not True:
        failures.append("TOC level-1 entries are not bold (官方: 一级标题加粗)")
    if qa.get("toc_sub_font_size") != "-4":
        failures.append("TOC sub-level entries are not small-four")
    if qa.get("toc_entry_font_sizes") != ["-4", "4"]:
        failures.append("TOC entry font sizes are not [小4号 sub, 4号 level-1]")
    if qa.get("toc_uses_shared_numwidth") is not True:
        failures.append("TOC entries do not use the shared number-width setting")
    if qa.get("toc_page_width_configured") is not True:
        failures.append("TOC page-number width/right margin are not configured")
    if qa.get("cover_fields_use_makebox_centering") is not True:
        failures.append("cover fields do not use fixed-width centered makebox layout")
    if qa.get("cover_fields_have_underlines") is not True:
        failures.append("cover fields do not use equal-width underlined value boxes")
    return failures


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


def cleanup_intermediates(tex_path: Path, expected_pdf: Path) -> None:
    base = tex_path.with_suffix("")
    for suffix in GENERATED_SUFFIXES:
        path = Path(str(base) + suffix)
        if path == expected_pdf:
            continue
        if path.exists():
            path.unlink()


def main() -> int:
    args = parse_args()
    project_lock: TextIO | None = None
    skill_dir = Path(__file__).resolve().parents[1]
    prepare_script = skill_dir / "scripts" / "prepare_course_report.py"
    postprocess_script = skill_dir / "scripts" / "postprocess_course_tex.py"
    template = skill_dir / "assets" / "templates" / "ctexart-course-report.tex"
    lua_filter = skill_dir / "scripts" / "drop_first_h1.lua"
    default_logo = skill_dir / "assets" / "njust_logo.png"

    try:
        pandoc = require_tool("pandoc", "Markdown to LaTeX conversion")
        source = args.source.resolve()
        if not source.is_file():
            raise RuntimeError(f"source Markdown was not found: {source}")
        if args.command_timeout <= 0:
            raise RuntimeError("--command-timeout must be greater than zero")
        if args.skip_compile and args.output_pdf:
            raise RuntimeError("--output-pdf requires compilation; omit --output-pdf when using --skip-compile.")
        project_dir = source.parent
        work_dir = project_path(args.work_dir, project_dir)
        tex_path = project_path(args.tex, project_dir)
        pdf_path = project_path(args.pdf, project_dir)
        output_pdf = project_path(args.output_pdf, project_dir) if args.output_pdf else None
        validate_output_path(tex_path, source, ".tex", "--tex")
        validate_output_path(pdf_path, source, ".pdf", "--pdf")
        if output_pdf:
            validate_output_path(output_pdf, source, ".pdf", "--output-pdf")
        if not is_within(work_dir, project_dir):
            raise RuntimeError(
                "--work-dir must be inside the source Markdown directory so generated metadata, "
                "copied logos, and relative assets stay self-contained."
            )
        if not is_within(tex_path, project_dir):
            raise RuntimeError(
                "--tex must be inside the source Markdown directory so relative images compile; "
                "use --output-pdf to copy the final PDF elsewhere."
            )
        if work_dir.exists() and not work_dir.is_dir():
            raise RuntimeError(f"--work-dir must be a directory path: {work_dir}")
        validate_generated_path_collisions(source, work_dir, tex_path, pdf_path, output_pdf)
        work_dir.mkdir(parents=True, exist_ok=True)
        project_lock = acquire_project_lock(project_dir, args.command_timeout)
        logo_arg = "" if args.no_cover else args.logo
        if logo_arg:
            logo_arg = copy_logo_into_project(logo_arg, work_dir, project_dir)
        if not args.no_cover and not logo_arg:
            project_default_logo = project_dir / "assets" / "njust_logo.png"
            if project_default_logo.exists():
                logo_arg = "assets/njust_logo.png"
            elif default_logo.exists():
                copied_logo = work_dir / "njust_logo.png"
                shutil.copy2(default_logo, copied_logo)
                logo_arg = relative_project_path(copied_logo, project_dir)

        prepare_cmd = [
            sys.executable,
            str(prepare_script),
            str(source),
            "--out-dir",
            str(work_dir),
            "--course",
            args.course,
            "--student-name",
            args.student_name,
            "--student-id",
            args.student_id,
            "--logo",
            logo_arg,
        ]
        if args.no_cover:
            prepare_cmd.append("--no-cover")
        if args.allow_slide_draft:
            prepare_cmd.append("--allow-slide-draft")
        run(prepare_cmd, cwd=project_dir, timeout=args.command_timeout)

        prepare_report = work_dir / "prepare_report.json"
        prepare = read_json(prepare_report)
        failures = validate_prepare_qa(prepare) + validate_cover_fields(prepare)
        if failures:
            print("Prepare QA failed: " + "; ".join(failures), file=sys.stderr)
            return 1

        body = work_dir / "report_body.md"
        metadata = work_dir / "metadata.yaml"
        run(
            [
                pandoc,
                str(body),
                "--from",
                "markdown+tex_math_dollars+pipe_tables+raw_tex+raw_html",
                "--to",
                "latex",
                "--standalone",
                "--template",
                str(template),
                f"--lua-filter={lua_filter}",
                "--metadata-file",
                str(metadata),
                "--resource-path=.",
                pandoc_no_highlight_arg(pandoc, args.command_timeout),
                "--output",
                str(tex_path),
            ],
            cwd=project_dir,
            timeout=args.command_timeout,
        )

        postprocess_qa = work_dir / "postprocess_qa.json"
        run(
            [
                sys.executable,
                str(postprocess_script),
                str(tex_path),
                "--in-place",
                "--qa",
                str(postprocess_qa),
            ],
            cwd=project_dir,
            timeout=args.command_timeout,
        )

        qa = read_json(postprocess_qa)
        failures = validate_postprocess_qa(qa)
        if failures:
            print("Postprocess QA failed: " + "; ".join(failures), file=sys.stderr)
            return 1

        if not args.skip_compile:
            compile_tex(tex_path, pdf_path, project_dir, args.command_timeout, args.keep_intermediates)
            if output_pdf:
                if not pdf_path.exists():
                    raise RuntimeError(f"PDF was not found for copy: {pdf_path}")
                if output_pdf.resolve() != pdf_path.resolve():
                    atomic_copy(pdf_path, output_pdf)
                    validate_pdf_file(output_pdf)
            if not args.keep_intermediates:
                cleanup_intermediates(tex_path, pdf_path)

        summary = {
            "tex": str(tex_path),
            "pdf": str(pdf_path if not output_pdf else output_pdf),
            "prepare_report": str(prepare_report),
            "postprocess_qa": str(postprocess_qa),
            "warning_count": len(prepare.get("warnings", [])),
        }
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except (OSError, subprocess.CalledProcessError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"build_course_report failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if project_lock is not None:
            project_lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
