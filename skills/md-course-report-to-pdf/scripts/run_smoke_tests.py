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
import subprocess
import sys
import tempfile
from pathlib import Path
import re


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


def inspect_pdf(pdf_path: Path) -> dict[str, object]:
    result: dict[str, object] = {
        "header_valid": False,
        "page_count": None,
        "a4_portrait": None,
        "embedded_fonts": None,
        "image_count": None,
        "continued_table_text": None,
        "continued_table_pages_valid": None,
        "qpdf_check": None,
    }
    if not pdf_path.is_file():
        return result
    with pdf_path.open("rb") as handle:
        result["header_valid"] = handle.read(5) == b"%PDF-"

    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo:
        inspected = run([pdfinfo, str(pdf_path)], pdf_path.parent)
        if inspected.returncode == 0:
            pages = re.search(r"(?m)^Pages:\s+(\d+)", inspected.stdout)
            size = re.search(r"(?m)^Page size:\s+([\d.]+)\s+x\s+([\d.]+)\s+pts", inspected.stdout)
            result["page_count"] = int(pages.group(1)) if pages else None
            if size:
                width, height = map(float, size.groups())
                result["a4_portrait"] = abs(width - 595.28) <= 2 and abs(height - 841.89) <= 2

    pdffonts = shutil.which("pdffonts")
    if pdffonts:
        inspected = run([pdffonts, str(pdf_path)], pdf_path.parent)
        if inspected.returncode == 0:
            flags = [
                match
                for line in inspected.stdout.splitlines()
                if (match := re.search(r"\s+(yes|no)\s+(yes|no)\s+(yes|no)\s+\d+\s+\d+\s*$", line, re.I))
            ]
            result["embedded_fonts"] = bool(flags) and all(match.group(1).lower() == "yes" for match in flags)

    pdfimages = shutil.which("pdfimages")
    if pdfimages:
        inspected = run([pdfimages, "-list", str(pdf_path)], pdf_path.parent)
        if inspected.returncode == 0:
            result["image_count"] = sum(
                1 for line in inspected.stdout.splitlines() if re.match(r"^\s*\d+\s+\d+\s+\w+", line)
            )
    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        inspected = run([pdftotext, str(pdf_path), "-"], pdf_path.parent)
        if inspected.returncode == 0:
            result["continued_table_text"] = inspected.stdout.count("LONGTABLEQA") > 1
            table_pages = [
                page
                for page in inspected.stdout.split("\f")
                if re.search(r"ROW\s+\d{2}", page)
            ]
            if len(table_pages) > 1:
                result["continued_table_pages_valid"] = all("LONGTABLEQA" in page for page in table_pages[1:])
    qpdf = shutil.which("qpdf")
    if qpdf:
        inspected = run([qpdf, "--check", str(pdf_path)], pdf_path.parent)
        result["qpdf_check"] = inspected.returncode == 0
    return result


def render_case(source: Path, work_root: Path, compiler_available: bool) -> dict[str, object]:
    case_dir = work_root / source.stem
    case_dir.mkdir(parents=True)
    copied_source = case_dir / source.name
    shutil.copy2(source, copied_source)
    if source.name == "table_report.md":
        text = copied_source.read_text(encoding="utf-8")
        extra_rows = "\n".join(
            f"| ROW {number:02d} | 跨页长表回归数据 | 第 {number:02d} 行约束说明 |"
            for number in range(4, 75)
        )
        text = text.replace(
            "| 方案 C | 扩展性强 | 配置较复杂 |\n: 方案对比",
            f"| 方案 C | 扩展性强 | 配置较复杂 |\n{extra_rows}\n: LONGTABLEQA",
        )
        copied_source.write_text(text, encoding="utf-8")

    latex_dir = case_dir / "latex"
    tex = case_dir / "report.tex"
    pdf_path = work_root / "published" / source.stem / "final.pdf"
    build_cmd = [
        sys.executable,
        str(BUILD),
        str(copied_source),
        "--work-dir",
        str(latex_dir),
        "--course",
        COURSE,
        "--student-name",
        STUDENT_NAME,
        "--student-id",
        STUDENT_ID,
        "--tex",
        str(tex),
        "--pdf",
        str(pdf_path),
    ]
    if not compiler_available:
        build_cmd.append("--skip-compile")

    built = run(build_cmd, case_dir)
    if built.returncode != 0:
        return fail("build failed", {"stdout": built.stdout, "stderr": built.stderr})

    try:
        build_summary = json.loads(built.stdout)
    except json.JSONDecodeError:
        return fail("build summary is not JSON", {"stdout": built.stdout, "stderr": built.stderr})

    if not tex.exists():
        return fail("expected TeX output missing", str(tex))
    report = load_json(latex_dir / "prepare_report.json")

    errors: list[str] = []
    qa = report.get("qa", {})
    if not isinstance(qa, dict):
        return fail("prepare QA is not an object", report)

    cover = report.get("cover", {})
    if not isinstance(cover, dict):
        return fail("cover QA is not an object", report)
    check(
        cover.get("logo_exists") is LOCAL_DEFAULT_LOGO.exists(),
        "default logo QA must match local asset availability",
        errors,
    )

    if compiler_available:
        check(pdf_path.exists(), "compiled PDF must exist", errors)
        check(pdf_path.exists() and pdf_path.stat().st_size > 0, "compiled PDF must be nonempty", errors)
        check(build_summary.get("pdf") == str(pdf_path), "summary must identify the sole PDF output", errors)
        pdf_qa = inspect_pdf(pdf_path)
        check(pdf_qa.get("header_valid") is True, "PDF header must be valid", errors)
        if shutil.which("pdfinfo"):
            check(isinstance(pdf_qa.get("page_count"), int) and int(pdf_qa["page_count"]) > 0, "PDF must have pages", errors)
            check(pdf_qa.get("a4_portrait") is True, "PDF pages must be A4 portrait", errors)
        if shutil.which("pdffonts"):
            check(pdf_qa.get("embedded_fonts") is True, "PDF fonts must be embedded", errors)
        if shutil.which("qpdf"):
            check(pdf_qa.get("qpdf_check") is True, "qpdf structure check must pass", errors)
        if source.name == "table_report.md":
            if shutil.which("pdfinfo"):
                check(isinstance(pdf_qa.get("page_count"), int) and int(pdf_qa["page_count"]) >= 8, "longtable fixture must span multiple pages", errors)
            if shutil.which("pdftotext"):
                check(pdf_qa.get("continued_table_text") is True, "continued longtable caption must render on a later page", errors)
                check(
                    pdf_qa.get("continued_table_pages_valid") is True,
                    "every later page containing longtable rows must repeat the continued caption",
                    errors,
                )
    else:
        pdf_qa = None

    return {
        "ok": not errors,
        "errors": errors,
        "pdf": {
            "attempted": compiler_available,
            "exists": pdf_path.exists() if compiler_available else None,
            "nonempty": pdf_path.stat().st_size > 0 if compiler_available and pdf_path.exists() else None,
            "qa": pdf_qa,
        },
        "build": build_summary,
    }


def render_no_cover_case(source: Path, work_root: Path, compiler_available: bool) -> dict[str, object]:
    case_dir = work_root / "no_cover"
    case_dir.mkdir(parents=True)
    copied_source = case_dir / source.name
    shutil.copy2(source, copied_source)
    fixture_image = case_dir / "fixture.png"
    shutil.copy2(LOCAL_DEFAULT_LOGO, fixture_image)
    copied_source.write_text(
        copied_source.read_text(encoding="utf-8") + "\n\n![烟测图片](fixture.png)\n",
        encoding="utf-8",
    )

    latex_dir = case_dir / "latex"
    tex = case_dir / "report.tex"
    pdf_path = case_dir / "report.pdf"
    build_cmd = [
        sys.executable,
        str(BUILD),
        str(copied_source),
        "--no-cover",
        "--work-dir",
        str(latex_dir),
        "--tex",
        str(tex),
        "--pdf",
        str(pdf_path),
        "--keep-intermediates",
    ]
    if not compiler_available:
        build_cmd.append("--skip-compile")
    built = run(build_cmd, case_dir)
    if built.returncode != 0:
        return fail("no-cover build failed", {"stdout": built.stdout, "stderr": built.stderr})

    try:
        build_summary = json.loads(built.stdout)
    except json.JSONDecodeError:
        return fail("no-cover build summary is not JSON", {"stdout": built.stdout, "stderr": built.stderr})

    report = load_json(latex_dir / "prepare_report.json")
    tex_text = tex.read_text(encoding="utf-8") if tex.exists() else ""
    cover = report.get("cover", {})

    errors: list[str] = []
    check(tex.exists(), "no-cover TeX output must exist", errors)
    check(isinstance(cover, dict), "no-cover QA must include cover object", errors)
    if isinstance(cover, dict):
        check(cover.get("enabled") is False, "cover.enabled must be false when --no-cover is used", errors)
    check(r"\begin{titlepage}" not in tex_text, "no-cover output must not contain a titlepage", errors)
    qa = report.get("qa", {})
    check(isinstance(qa, dict) and qa.get("image_count") == 1, "no-cover case must process one real image", errors)
    if compiler_available:
        check(pdf_path.exists(), "no-cover compiled PDF must exist", errors)
        check(pdf_path.exists() and pdf_path.stat().st_size > 0, "no-cover compiled PDF must be nonempty", errors)
        check(tex.with_suffix(".log").exists(), "--keep-intermediates must preserve the compiler log", errors)
        check(tex.with_suffix(".aux").exists(), "--keep-intermediates must preserve the aux file", errors)
        pdf_qa = inspect_pdf(pdf_path)
        if shutil.which("pdfimages"):
            check(isinstance(pdf_qa.get("image_count"), int) and int(pdf_qa["image_count"]) >= 1, "rendered PDF must contain the fixture image", errors)
    else:
        pdf_qa = None
    return {"ok": not errors, "errors": errors, "build": build_summary, "pdf_qa": pdf_qa}


def render_thesis_case(source: Path, work_root: Path, compiler_available: bool) -> dict[str, object]:
    """Build the 学位论文 template with NO cover CLI args; cover comes from front matter."""
    case_dir = work_root / "thesis_cover"
    case_dir.mkdir(parents=True)
    copied_source = case_dir / source.name
    shutil.copy2(source, copied_source)

    latex_dir = case_dir / "latex"
    tex = case_dir / "report.tex"
    pdf_path = case_dir / "report.pdf"
    build_cmd = [
        sys.executable,
        str(BUILD),
        str(copied_source),
        "--work-dir",
        str(latex_dir),
        "--tex",
        str(tex),
        "--pdf",
        str(pdf_path),
    ]
    if not compiler_available:
        build_cmd.append("--skip-compile")
    built = run(build_cmd, case_dir)
    if built.returncode != 0:
        return fail("thesis build failed", {"stdout": built.stdout, "stderr": built.stderr})

    report = load_json(latex_dir / "prepare_report.json")
    post_qa = load_json(latex_dir / "postprocess_qa.json")
    cover = report.get("cover", {})
    qa = report.get("qa", {})
    errors: list[str] = []
    check(report.get("warnings") == [], "thesis prepare warnings must be empty", errors)
    check(isinstance(cover, dict) and cover.get("thesis") is True, "thesis cover must be detected from front matter", errors)
    check(post_qa.get("thesis_cover_rendered") is True, "thesis titlepage must be rendered", errors)
    check(post_qa.get("course_cover_rendered") is False, "course cover must not render for thesis input", errors)
    tex_text = tex.read_text(encoding="utf-8") if tex.exists() else ""
    check("硕士学位论文" in tex_text, "thesis degree type must appear on the cover", errors)
    check("分类号" in tex_text and "论文提交时间" in tex_text, "thesis cover field labels must appear", errors)
    if isinstance(qa, dict):
        check(qa.get("citation_numbers") == [1, 2, 3], "thesis template citations must be [1, 2, 3]", errors)
        check(qa.get("reference_numbers") == [1, 2, 3], "thesis template references must be [1, 2, 3]", errors)
    if compiler_available:
        check(pdf_path.exists() and pdf_path.stat().st_size > 0, "thesis compiled PDF must be nonempty", errors)
    return {"ok": not errors, "errors": errors}


def render_compile_failure(work_root: Path) -> dict[str, object]:
    case_dir = work_root / "compiler_failure"
    case_dir.mkdir(parents=True)
    source = case_dir / "compiler_failure.md"
    source.write_text(
        "# 编译器失败诊断\n\n## 正文\n\n```{=latex}\n\\undefinedcontrolsequenceforcoursetest\n```\n",
        encoding="utf-8",
    )
    original_source = source.read_text(encoding="utf-8")
    tex = case_dir / "report.tex"
    pdf_path = case_dir / "report.pdf"
    built = run(
        [
            sys.executable,
            str(BUILD),
            str(source),
            "--no-cover",
            "--work-dir",
            str(case_dir / "latex"),
            "--tex",
            str(tex),
            "--pdf",
            str(pdf_path),
        ],
        case_dir,
    )
    errors: list[str] = []
    check(built.returncode != 0, "invalid LaTeX must fail compilation", errors)
    check(bool(built.stderr.strip()), "compiler failure diagnostics must be nonempty", errors)
    check(source.read_text(encoding="utf-8") == original_source, "compiler failure must preserve the source", errors)
    check(len(built.stderr) <= 17_000, "compiler failure diagnostics must stay bounded", errors)
    check(not pdf_path.exists(), "failed compilation must not leave a final PDF", errors)
    return {"ok": not errors, "errors": errors, "stderr": built.stderr}


def render_absolute_logo_case(work_root: Path, compiler_available: bool) -> dict[str, object]:
    case_dir = work_root / "absolute_logo_path"
    case_dir.mkdir(parents=True)
    source = case_dir / "absolute_logo_path.md"
    shutil.copy2(EXAMPLES / "minimal_report.md", source)

    latex_dir = case_dir / "latex"
    tex = case_dir / "report.tex"
    pdf_path = case_dir / "report.pdf"
    build_cmd = [
        sys.executable,
        str(BUILD),
        str(source),
        "--work-dir",
        str(latex_dir),
        "--course",
        COURSE,
        "--student-name",
        STUDENT_NAME,
        "--student-id",
        STUDENT_ID,
        "--logo",
        str(LOCAL_DEFAULT_LOGO.resolve()),
        "--tex",
        str(tex),
        "--pdf",
        str(pdf_path),
    ]
    if not compiler_available:
        build_cmd.append("--skip-compile")
    built = run(build_cmd, case_dir)
    if built.returncode != 0:
        return fail("absolute logo build failed", {"stdout": built.stdout, "stderr": built.stderr})

    report = load_json(latex_dir / "prepare_report.json")
    cover = report.get("cover", {})
    errors: list[str] = []
    check(isinstance(cover, dict), "absolute logo QA must include cover object", errors)
    if isinstance(cover, dict):
        logo_path = str(cover.get("logo_path", ""))
        check(cover.get("logo_exists") is True, "absolute logo copy must exist", errors)
        check(cover.get("logo_inside_project") is True, "absolute logo copy must be inside project", errors)
        check(not Path(logo_path).is_absolute(), "absolute logo must be converted to a relative project path", errors)
    if compiler_available:
        check(pdf_path.exists(), "absolute logo compiled PDF must exist", errors)
        check(pdf_path.exists() and pdf_path.stat().st_size > 0, "absolute logo compiled PDF must be nonempty", errors)
    return {"ok": not errors, "errors": errors}


def render_caption_cases(work_root: Path, compiler_available: bool) -> dict[str, object]:
    table = "| A | B |\n|---|---|\n| 1 | 2 |\n"
    variants = {
        "caption_blank": table + "\n: 标题\n",
        "caption_before": ": 标题\n\n" + table,
        "caption_table_prefix": table + "\nTable: 标题\n",
    }
    results = {}
    for name, markdown in variants.items():
        source = work_root / (name + ".md")
        source.write_text("# 报告\n\n## 正文\n\n" + markdown, encoding="utf-8")
        case_dir = work_root / name
        case_dir.mkdir()
        copied = case_dir / "input.md"
        shutil.copy2(source, copied)
        options = [] if compiler_available else ["--skip-compile"]
        built = run([sys.executable, str(BUILD), str(copied), "--no-cover", *options], case_dir)
        tex = case_dir / "course_report.tex"
        errors: list[str] = []
        check(built.returncode == 0, "supported table caption must build", errors)
        check(tex.exists() and r"\caption{标题}" in tex.read_text(encoding="utf-8"), "caption must survive Pandoc", errors)
        results[name] = {"ok": not errors, "errors": errors, "stderr": built.stderr}
    return results


def main() -> int:
    required = [BUILD]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        print(json.dumps({"ok": False, "error": "required files missing", "missing": missing}, ensure_ascii=False))
        return 1

    sources = [
        EXAMPLES / "minimal_report.md",
        EXAMPLES / "table_report.md",
        EXAMPLES / "citation_report.md",
        EXAMPLES / "no_reference_report.md",
        EXAMPLES / "标准课程报告模板.md",
    ]
    missing_sources = [str(path) for path in sources if not path.exists()]
    if missing_sources:
        print(
            json.dumps(
                {"ok": False, "error": "example files missing", "missing": missing_sources},
                ensure_ascii=False,
            )
        )
        return 1

    if shutil.which("pandoc") is None:
        print(json.dumps({"ok": False, "error": "pandoc not found"}, ensure_ascii=False))
        return 1

    compiler_available = shutil.which("tectonic") is not None or shutil.which("xelatex") is not None
    require_compiler = os.environ.get("MD_COURSE_REPORT_REQUIRE_COMPILER") == "1"
    if require_compiler and not compiler_available:
        print(json.dumps({"ok": False, "error": "compiler required but tectonic/xelatex not found"}, ensure_ascii=False))
        return 1
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
        return 1
    with tempfile.TemporaryDirectory(prefix="md-course-report-smoke-") as tmp:
        work_root = Path(tmp)
        cases = {source.name: render_case(source, work_root, compiler_available) for source in sources}
        no_cover_case = render_no_cover_case(EXAMPLES / "minimal_report.md", work_root, compiler_available)
        thesis_case = render_thesis_case(EXAMPLES / "学位论文模板.md", work_root, compiler_available)
        caption_cases = render_caption_cases(work_root, compiler_available)
        compiler_failure = (
            render_compile_failure(work_root)
            if compiler_available
            else {"ok": True, "skipped": True, "reason": "no LaTeX compiler available"}
        )
        absolute_logo_case = render_absolute_logo_case(work_root, compiler_available)

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
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
