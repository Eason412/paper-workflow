#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Build a Markdown course report through the bundled LaTeX workflow."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TextIO

if __package__:
    from . import build_qa, build_runtime
else:
    import build_qa, build_runtime


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--course", default="")
    parser.add_argument("--student-name", default="")
    parser.add_argument("--student-id", default="")
    parser.add_argument("--logo", default="")
    parser.add_argument("--no-cover", action="store_true")
    parser.add_argument("--allow-slide-draft", action="store_true", help="已废弃，无效果")
    parser.add_argument("--keep-repeated-citations", action="store_true")
    parser.add_argument("--keep-reference-urls", action="store_true")
    parser.add_argument("--work-dir", type=Path, default=Path("latex"))
    parser.add_argument("--tex", type=Path, default=Path("course_report.tex"))
    parser.add_argument("--pdf", type=Path, default=Path("course_report.pdf"))
    parser.add_argument("--keep-intermediates", action="store_true")
    parser.add_argument("--skip-compile", action="store_true")
    parser.add_argument("--command-timeout", type=float, default=build_runtime.DEFAULT_COMMAND_TIMEOUT)
    return parser.parse_args()


def resolve_build_paths(args: argparse.Namespace) -> tuple[Path, Path, Path, Path, Path]:
    source = args.source.resolve()
    if not source.is_file():
        raise RuntimeError(f"source Markdown was not found: {source}")
    if args.command_timeout <= 0:
        raise RuntimeError("--command-timeout must be greater than zero")
    project_dir = source.parent
    work_dir = build_runtime.project_path(args.work_dir, project_dir)
    tex_path = build_runtime.project_path(args.tex, project_dir)
    pdf_path = build_runtime.project_path(args.pdf, project_dir)
    build_runtime.validate_output_path(tex_path, source, ".tex", "--tex")
    build_runtime.validate_output_path(pdf_path, source, ".pdf", "--pdf")
    if not build_runtime.is_within(work_dir, project_dir):
        raise RuntimeError(
            "--work-dir must be inside the source Markdown directory so generated metadata, "
            "copied logos, and relative assets stay self-contained."
        )
    if not build_runtime.is_within(tex_path, project_dir):
        raise RuntimeError(
            "--tex must be inside the source Markdown directory so relative images compile; "
            "use --pdf to place the final PDF elsewhere."
        )
    if work_dir.exists() and not work_dir.is_dir():
        raise RuntimeError(f"--work-dir must be a directory path: {work_dir}")
    build_runtime.validate_generated_path_collisions(source, work_dir, tex_path, pdf_path)
    return source, project_dir, work_dir, tex_path, pdf_path


def select_build_logo(args: argparse.Namespace, work_dir: Path, project_dir: Path, default_logo: Path) -> str:
    logo_arg = "" if args.no_cover else args.logo
    if logo_arg:
        logo_arg = build_runtime.copy_logo_into_project(logo_arg, work_dir, project_dir)
    if not args.no_cover and not logo_arg:
        project_default_logo = project_dir / "assets" / "njust_logo.png"
        if project_default_logo.exists():
            logo_arg = "assets/njust_logo.png"
        elif default_logo.exists():
            copied_logo = work_dir / "njust_logo.png"
            shutil.copy2(default_logo, copied_logo)
            logo_arg = build_runtime.relative_project_path(copied_logo, project_dir)
    return logo_arg


def run_prepare_stage(
    args: argparse.Namespace, source: Path, work_dir: Path, project_dir: Path, prepare_script: Path, logo_arg: str,
) -> tuple[Path, list[str], list[str]]:
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
    if args.keep_repeated_citations:
        prepare_cmd.append("--keep-repeated-citations")
    build_runtime.run(prepare_cmd, cwd=project_dir, timeout=args.command_timeout)

    prepare_report = work_dir / "prepare_report.json"
    prepare = build_runtime.read_json(prepare_report)
    warnings = build_qa.prepare_warnings(prepare)
    for warning in warnings:
        print(f"prepare warning: {warning}", file=sys.stderr)
    failures = build_qa.validate_prepare_qa(prepare) + build_qa.validate_cover_fields(prepare)
    return prepare_report, warnings, failures


def convert_body_to_tex(
    args: argparse.Namespace, pandoc: str, work_dir: Path, tex_path: Path, project_dir: Path,
    template: Path, lua_filter: Path,
) -> None:
    body = work_dir / "report_body.md"
    metadata = work_dir / "metadata.yaml"
    build_runtime.run(
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
            build_runtime.pandoc_no_highlight_arg(pandoc, args.command_timeout),
            "--output",
            str(tex_path),
        ],
        cwd=project_dir,
        timeout=args.command_timeout,
    )


def run_postprocess_stage(
    args: argparse.Namespace, tex_path: Path, work_dir: Path, project_dir: Path, postprocess_script: Path,
) -> tuple[Path, list[str]]:
    postprocess_qa = work_dir / "postprocess_qa.json"
    postprocess_cmd = [
        sys.executable, str(postprocess_script), str(tex_path),
        "--in-place", "--qa", str(postprocess_qa),
    ]
    if args.keep_reference_urls:
        postprocess_cmd.append("--keep-reference-urls")
    build_runtime.run(
        postprocess_cmd,
        cwd=project_dir,
        timeout=args.command_timeout,
    )

    qa = build_runtime.read_json(postprocess_qa)
    failures = build_qa.validate_postprocess_qa(qa, args.keep_reference_urls)
    return postprocess_qa, failures


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
        source, project_dir, work_dir, tex_path, pdf_path = resolve_build_paths(args)
        pandoc = build_runtime.require_tool("pandoc", "Markdown to LaTeX conversion")
        work_dir.mkdir(parents=True, exist_ok=True)
        project_lock = build_runtime.acquire_project_lock(project_dir, args.command_timeout)
        logo_arg = select_build_logo(args, work_dir, project_dir, default_logo)
        prepare_report, warnings, failures = run_prepare_stage(
            args, source, work_dir, project_dir, prepare_script, logo_arg,
        )
        if failures:
            print("Prepare QA failed: " + "; ".join(failures), file=sys.stderr)
            return 1

        convert_body_to_tex(args, pandoc, work_dir, tex_path, project_dir, template, lua_filter)
        postprocess_qa, failures = run_postprocess_stage(
            args, tex_path, work_dir, project_dir, postprocess_script,
        )
        if failures:
            print("Postprocess QA failed: " + "; ".join(failures), file=sys.stderr)
            return 1

        if not args.skip_compile:
            build_runtime.compile_tex(tex_path, pdf_path, project_dir, args.command_timeout, args.keep_intermediates)

        summary = {
            "tex": str(tex_path),
            "pdf": str(pdf_path),
            "prepare_report": str(prepare_report),
            "postprocess_qa": str(postprocess_qa),
            "warning_count": len(warnings),
            "warnings": warnings,
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
