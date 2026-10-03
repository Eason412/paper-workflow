#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Run smoke tests for the Markdown course-report PDF workflow."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

if __package__:
    from . import smoke_cases, smoke_runtime
else:
    import smoke_cases, smoke_runtime


def check_smoke_prerequisites(sources: list[Path]) -> bool | None:
    required = [smoke_runtime.BUILD]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        print(json.dumps({"ok": False, "error": "required files missing", "missing": missing}, ensure_ascii=False))
        return None

    missing_sources = [str(path) for path in sources if not path.exists()]
    if missing_sources:
        print(
            json.dumps(
                {"ok": False, "error": "example files missing", "missing": missing_sources},
                ensure_ascii=False,
            )
        )
        return None

    if shutil.which("pandoc") is None:
        print(json.dumps({"ok": False, "error": "pandoc not found"}, ensure_ascii=False))
        return None

    compiler_available = shutil.which("tectonic") is not None or shutil.which("xelatex") is not None
    require_compiler = os.environ.get("MD_COURSE_REPORT_REQUIRE_COMPILER") == "1"
    if require_compiler and not compiler_available:
        print(json.dumps({"ok": False, "error": "compiler required but tectonic/xelatex not found"}, ensure_ascii=False))
        return None
    require_pdf_tools = os.environ.get("MD_COURSE_REPORT_REQUIRE_PDF_TOOLS") == "1"
    pdf_tools = ("pdfinfo", "pdffonts", "pdfimages", "pdftotext", "qpdf")
    missing_pdf_tools = [name for name in pdf_tools if shutil.which(name) is None]
    if require_pdf_tools and missing_pdf_tools:
        print(
            json.dumps(
                {"ok": False, "error": "PDF QA tools required but missing", "missing": missing_pdf_tools},
                ensure_ascii=False,
            )
        )
        return None
    return compiler_available


def run_smoke_cases(sources: list[Path], compiler_available: bool) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="md-course-report-smoke-") as tmp:
        work_root = Path(tmp)
        cases = {source.name: smoke_cases.render_case(source, work_root, compiler_available) for source in sources}
        no_cover_case = smoke_cases.render_no_cover_case(smoke_runtime.EXAMPLES / "minimal_report.md", work_root, compiler_available)
        thesis_case = smoke_cases.render_thesis_case(smoke_runtime.EXAMPLES / "学位论文模板.md", work_root, compiler_available)
        caption_cases = smoke_cases.render_caption_cases(work_root, compiler_available)
        compiler_failure = (
            smoke_cases.render_compile_failure(work_root)
            if compiler_available
            else {"ok": True, "skipped": True, "reason": "no LaTeX compiler available"}
        )
        absolute_logo_case = smoke_cases.render_absolute_logo_case(work_root, compiler_available)

    ok = (
        all(bool(result.get("ok")) for result in cases.values())
        and bool(no_cover_case.get("ok"))
        and bool(thesis_case.get("ok"))
        and bool(compiler_failure.get("ok"))
        and bool(absolute_logo_case.get("ok"))
        and all(bool(result.get("ok")) for result in caption_cases.values())
    )
    summary = {
        "ok": ok,
        "compiler_available": compiler_available,
        "cases": cases,
        "no_cover_case": no_cover_case,
        "thesis_case": thesis_case,
        "compiler_failure": compiler_failure,
        "absolute_logo_case": absolute_logo_case,
        "caption_cases": caption_cases,
    }
    return summary


def main() -> int:
    sources = [
        smoke_runtime.EXAMPLES / "minimal_report.md",
        smoke_runtime.EXAMPLES / "table_report.md",
        smoke_runtime.EXAMPLES / "citation_report.md",
        smoke_runtime.EXAMPLES / "no_reference_report.md",
        smoke_runtime.EXAMPLES / "标准课程报告模板.md",
    ]
    compiler_available = check_smoke_prerequisites(sources)
    if compiler_available is None:
        return 1
    summary = run_smoke_cases(sources, compiler_available)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
