#!/usr/bin/env python3
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
PREPARE = SCRIPTS / "prepare_course_report.py"
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


def first_longtable(tex: str) -> str:
    match = re.search(r"\\begin\{longtable\}.*?\\end\{longtable\}", tex, flags=re.S)
    return match.group(0) if match else ""


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
    pdf_path = case_dir / "report.pdf"
    exported_pdf = case_dir / "exported" / "final.pdf"
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
    else:
        build_cmd.extend(["--output-pdf", str(exported_pdf)])

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
    post_qa = load_json(latex_dir / "postprocess_qa.json")

    errors: list[str] = []
    warnings = report.get("warnings", [])
    qa = report.get("qa", {})
    if not isinstance(qa, dict):
        return fail("prepare QA is not an object", report)

    check(warnings == [], "prepare warnings must be empty", errors)
    check(post_qa.get("remaining_raw_citations_before_references") == [], "raw citations remain", errors)
    check(post_qa.get("remaining_unnumbered_display_math") == 0, "unnumbered display math remains", errors)
    font_sizes = post_qa.get("toc_entry_font_sizes", [])
    check(font_sizes == ["-4", "4"], "toc_entry_font_sizes must be ['-4', '4'] (sub 小4号, level-1 4号)", errors)
    check(post_qa.get("toc_section_font_size") == "4", "TOC level-1 entries must be four-size", errors)
    check(post_qa.get("toc_section_is_bold") is True, "TOC level-1 entries must be bold", errors)
    check(post_qa.get("toc_sub_font_size") == "-4", "TOC sub-level entries must be small-four", errors)
    check(post_qa.get("toc_uses_shared_numwidth") is True, "TOC entries must use shared number width", errors)
    check(post_qa.get("toc_page_width_configured") is True, "TOC page number width/right margin must be configured", errors)
    check(post_qa.get("cover_fields_use_makebox_centering") is True, "cover fields must use centered makebox layout", errors)
    check(post_qa.get("cover_fields_have_underlines") is True, "cover value boxes must use equal-width underlines", errors)
    cover = report.get("cover", {})
    if not isinstance(cover, dict):
        return fail("cover QA is not an object", report)
    check(
        cover.get("logo_exists") is LOCAL_DEFAULT_LOGO.exists(),
        "default logo QA must match local asset availability",
        errors,
    )

    citation_dedup = qa.get("citation_dedup", {})
    if source.name == "minimal_report.md":
        check(isinstance(citation_dedup, dict), "citation_dedup must be an object", errors)
        check(citation_dedup.get("removed_marker_count") == 1, "minimal duplicate citation marker must be removed", errors)
        check(citation_dedup.get("rewritten_marker_count") == 0, "minimal duplicate citation marker should not be rewritten", errors)

    if source.name == "citation_report.md":
        check(qa.get("citation_numbers") == [1, 2, 3], "citation case must collect only real body citations", errors)
        check(qa.get("reference_numbers") == [1, 2, 3], "citation case must collect only real reference labels", errors)
        check(qa.get("pipe_table_count") == 0, "pipe table inside code block must be ignored", errors)
        check(isinstance(citation_dedup, dict), "citation_dedup must be an object", errors)
        check(
            citation_dedup.get("normalized_marker_count", 0) >= 1,
            "citation case must normalize Chinese/full-width citation markers",
            errors,
        )
        check(
            citation_dedup.get("rewritten_marker_count", 0) >= 1,
            "citation case must rewrite mixed repeated/new markers",
            errors,
        )
        check(
            citation_dedup.get("removed_marker_count", 0) >= 1,
            "citation case must remove fully repeated markers",
            errors,
        )

    if source.name == "no_reference_report.md":
        check(qa.get("citation_numbers") == [], "no-reference case must have no citations", errors)
        check(qa.get("reference_numbers") == [], "no-reference case must have no reference labels", errors)
        check(post_qa.get("references_section_found") is False, "no-reference case should not invent references", errors)

    if source.name == "table_report.md":
        tex_text = tex.read_text(encoding="utf-8")
        table_block = first_longtable(tex_text)
        check(qa.get("pipe_table_count") == 1, "table pipe_table_count must be 1", errors)
        check(qa.get("table_caption_count") == 1, "table table_caption_count must be 1", errors)
        check(post_qa.get("longtable_count") == 1, "table longtable_count must be 1", errors)
        check(post_qa.get("booktabs_longtable_count") == 1, "table booktabs_longtable_count must be 1", errors)
        check(post_qa.get("longtables_missing_caption") == 0, "table longtables_missing_caption must be 0", errors)
        check(post_qa.get("longtables_missing_endfoot") == 0, "table longtables_missing_endfoot must be 0", errors)
        check(post_qa.get("longtables_missing_endlastfoot") == 0, "table longtables_missing_endlastfoot must be 0", errors)
        check(
            post_qa.get("longtables_missing_continued_caption") == 0,
            "table longtables_missing_continued_caption must be 0",
            errors,
        )
        check(post_qa.get("longtable_headers_centered") is True, "table headers must be centered", errors)
        check(post_qa.get("longtable_cells_centered") is True, "table cells must be centered", errors)
        check(post_qa.get("longtable_columns_vertical_centered") is True, "table columns must be vertically centered", errors)
        check("（续表）" in table_block, "longtable must include continued caption text", errors)
        check(r"\endfirsthead" in table_block and r"\endhead" in table_block, "longtable must keep repeated heads", errors)
        check(r"\endfoot" in table_block and r"\endlastfoot" in table_block, "longtable must define foot and lastfoot", errors)
        check(r"\multicolumn{1}{c}{方案}" in table_block, "plain longtable header cells must be centered", errors)
        check(r"\raggedright" not in table_block and r"\raggedleft" not in table_block, "longtable must not keep ragged table cells", errors)

    if compiler_available:
        check(pdf_path.exists(), "compiled PDF must exist", errors)
        check(pdf_path.exists() and pdf_path.stat().st_size > 0, "compiled PDF must be nonempty", errors)
        check(exported_pdf.exists(), "--output-pdf copy must exist", errors)
        check(
            exported_pdf.exists() and exported_pdf.read_bytes() == pdf_path.read_bytes(),
            "--output-pdf copy must match the compiled PDF",
            errors,
        )
        pdf_qa = inspect_pdf(exported_pdf)
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

    if source.name == "标准课程报告模板.md":
        check(qa.get("image_count") == 0, "standard template must not reference a missing live image", errors)
        check(qa.get("pipe_table_count") == 1, "standard template pipe_table_count must be 1", errors)
        check(qa.get("table_caption_count") == 1, "standard template table_caption_count must be 1", errors)
        check(qa.get("citation_numbers") == [1, 2, 3], "standard template citations must be [1, 2, 3]", errors)
        check(qa.get("reference_numbers") == [1, 2, 3], "standard template references must be [1, 2, 3]", errors)

    return {
        "ok": not errors,
        "errors": errors,
        "prepare": {
            "warning_count": len(warnings) if isinstance(warnings, list) else None,
            "pipe_table_count": qa.get("pipe_table_count"),
            "table_caption_count": qa.get("table_caption_count"),
            "citation_dedup": qa.get("citation_dedup"),
        },
        "postprocess": {
            "remaining_raw_citations_before_references": post_qa.get(
                "remaining_raw_citations_before_references"
            ),
            "remaining_unnumbered_display_math": post_qa.get("remaining_unnumbered_display_math"),
            "toc_entry_font_sizes": post_qa.get("toc_entry_font_sizes"),
            "toc_section_font_size": post_qa.get("toc_section_font_size"),
            "toc_section_is_bold": post_qa.get("toc_section_is_bold"),
            "toc_sub_font_size": post_qa.get("toc_sub_font_size"),
            "toc_uses_shared_numwidth": post_qa.get("toc_uses_shared_numwidth"),
            "toc_page_width_configured": post_qa.get("toc_page_width_configured"),
            "cover_fields_use_makebox_centering": post_qa.get("cover_fields_use_makebox_centering"),
            "cover_fields_have_underlines": post_qa.get("cover_fields_have_underlines"),
            "longtable_count": post_qa.get("longtable_count"),
            "booktabs_longtable_count": post_qa.get("booktabs_longtable_count"),
            "longtables_missing_caption": post_qa.get("longtables_missing_caption"),
            "longtables_missing_endfoot": post_qa.get("longtables_missing_endfoot"),
            "longtables_missing_endlastfoot": post_qa.get("longtables_missing_endlastfoot"),
            "longtables_missing_continued_caption": post_qa.get("longtables_missing_continued_caption"),
            "longtable_headers_centered": post_qa.get("longtable_headers_centered"),
            "longtable_cells_centered": post_qa.get("longtable_cells_centered"),
            "longtable_columns_vertical_centered": post_qa.get("longtable_columns_vertical_centered"),
        },
        "pdf": {
            "attempted": compiler_available,
            "exists": pdf_path.exists() if compiler_available else None,
            "nonempty": pdf_path.stat().st_size > 0 if compiler_available and pdf_path.exists() else None,
            "exported": exported_pdf.exists() if compiler_available else None,
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
    else:
        build_cmd.extend(["--output-pdf", str(pdf_path)])
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
    check(post_qa.get("cover_fields_use_makebox_centering") is True, "thesis cover macros must stay defined", errors)
    tex_text = tex.read_text(encoding="utf-8") if tex.exists() else ""
    check("硕士学位论文" in tex_text, "thesis degree type must appear on the cover", errors)
    check("分类号" in tex_text and "论文提交时间" in tex_text, "thesis cover field labels must appear", errors)
    if isinstance(qa, dict):
        check(qa.get("citation_numbers") == [1, 2, 3], "thesis template citations must be [1, 2, 3]", errors)
        check(qa.get("reference_numbers") == [1, 2, 3], "thesis template references must be [1, 2, 3]", errors)
    if compiler_available:
        check(pdf_path.exists() and pdf_path.stat().st_size > 0, "thesis compiled PDF must be nonempty", errors)
    return {"ok": not errors, "errors": errors}


def render_negative_case(
    name: str,
    markdown: str,
    expected_error: str,
    work_root: Path,
    extra_args: list[str] | None = None,
    expect_prepare_failure: bool = True,
) -> dict[str, object]:
    case_dir = work_root / name
    case_dir.mkdir(parents=True)
    source = case_dir / f"{name}.md"
    source.write_text(markdown, encoding="utf-8")

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
        "--tex",
        str(tex),
        "--pdf",
        str(pdf_path),
        "--skip-compile",
    ]
    if extra_args:
        build_cmd.extend(extra_args)
    built = run(build_cmd, case_dir)

    errors: list[str] = []
    check(built.returncode != 0, "negative case should fail", errors)
    if expect_prepare_failure:
        check("Prepare QA failed" in built.stderr, "missing prepare QA failure message", errors)
    check(expected_error in built.stderr, f"missing expected error: {expected_error}", errors)
    check(not tex.exists(), "negative case should fail before Pandoc emits TeX", errors)
    return {
        "ok": not errors,
        "errors": errors,
        "stdout": built.stdout,
        "stderr": built.stderr,
    }


def render_compile_failure(work_root: Path) -> dict[str, object]:
    case_dir = work_root / "compiler_failure"
    case_dir.mkdir(parents=True)
    source = case_dir / "compiler_failure.md"
    source.write_text(
        "# 编译器失败诊断\n\n## 正文\n\n```{=latex}\n\\undefinedcontrolsequenceforcoursetest\n```\n",
        encoding="utf-8",
    )
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
    check("command failed with exit code" in built.stderr, "compiler failure must include the command exit code", errors)
    check(
        "Undefined control sequence" in built.stderr and "report.tex:" in built.stderr,
        "compiler failure must preserve the useful compiler diagnostic",
        errors,
    )
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


def render_prepare_absolute_logo_warning(work_root: Path) -> dict[str, object]:
    case_dir = work_root / "prepare_absolute_logo_warning"
    case_dir.mkdir(parents=True)
    source = case_dir / "prepare_absolute_logo_warning.md"
    shutil.copy2(EXAMPLES / "minimal_report.md", source)

    out_dir = case_dir / "latex"
    prepared = run(
        [
            sys.executable,
            str(PREPARE),
            str(source),
            "--out-dir",
            str(out_dir),
            "--course",
            COURSE,
            "--student-name",
            STUDENT_NAME,
            "--student-id",
            STUDENT_ID,
            "--logo",
            str(LOCAL_DEFAULT_LOGO.resolve()),
        ],
        case_dir,
    )
    if prepared.returncode != 0:
        return fail("prepare with absolute logo should warn, not crash", {"stdout": prepared.stdout, "stderr": prepared.stderr})

    report = load_json(out_dir / "prepare_report.json")
    cover = report.get("cover", {})
    warnings = report.get("warnings", [])
    errors: list[str] = []
    check(isinstance(cover, dict), "prepare absolute logo QA must include cover object", errors)
    check(isinstance(warnings, list), "prepare absolute logo warnings must be a list", errors)
    if isinstance(cover, dict):
        check(cover.get("logo_exists") is True, "prepare absolute logo must exist", errors)
        check(cover.get("logo_inside_project") is False, "prepare absolute logo must be marked outside project", errors)
    if isinstance(warnings, list):
        check(
            any("logo 路径不是项目内相对路径" in str(item) for item in warnings),
            "prepare absolute logo must emit a path warning",
            errors,
        )
    return {"ok": not errors, "errors": errors}


def main() -> int:
    required = [BUILD, PREPARE]
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
        negative_cases = {
            "table_missing_caption": render_negative_case(
                "table_missing_caption",
                "# 表格缺表题\n\n| A | B |\n|---|---|\n| 1 | 2 |\n",
                "missing adjacent Pandoc captions",
                work_root,
            ),
            "table_caption_blank_line": render_negative_case(
                "table_caption_blank_line",
                "# 表题空行\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n: 路线比较\n",
                "captions are separated by blank lines",
                work_root,
            ),
            "table_manual_number_caption": render_negative_case(
                "table_manual_number_caption",
                "# 手写表号\n\n| A | B |\n|---|---|\n| 1 | 2 |\n: 表 1 路线比较\n",
                "table captions contain manual numbers",
                work_root,
            ),
            "table_colon_prefix_caption": render_negative_case(
                "table_colon_prefix_caption",
                "# 错误表题语法\n\n| A | B |\n|---|---|\n| 1 | 2 |\n表: 路线比较\n",
                "unsupported syntax",
                work_root,
            ),
            "absolute_image_path": render_negative_case(
                "absolute_image_path",
                "# 绝对图片路径\n\n![系统文件](/etc/hosts)\n",
                "absolute, remote, or outside",
                work_root,
            ),
            "missing_logo": render_negative_case(
                "missing_logo",
                "# 缺失 logo\n\n正文。\n",
                "logo file is missing",
                work_root,
                extra_args=["--logo", "assets/missing_logo.png"],
            ),
            "absolute_logo_path": render_absolute_logo_case(work_root, compiler_available),
            "prepare_absolute_logo_warning": render_prepare_absolute_logo_warning(work_root),
            "outside_work_dir": render_negative_case(
                "outside_work_dir",
                "# 项目外工作目录\n\n正文。\n",
                "--work-dir must be inside",
                work_root,
                extra_args=["--work-dir", str(work_root / "outside_latex")],
                expect_prepare_failure=False,
            ),
            "skip_compile_output_pdf": render_negative_case(
                "skip_compile_output_pdf",
                "# 跳过编译\n\n正文。\n",
                "--output-pdf requires compilation",
                work_root,
                extra_args=["--output-pdf", str(work_root / "skip_compile_output_pdf" / "out.pdf")],
                expect_prepare_failure=False,
            ),
            "bad_pdf_suffix": render_negative_case(
                "bad_pdf_suffix",
                "# 错误 PDF 后缀\n\n正文。\n",
                "--pdf must end with .pdf",
                work_root,
                extra_args=["--pdf", str(work_root / "bad_pdf_suffix" / "out.md")],
                expect_prepare_failure=False,
            ),
            "tex_overwrites_source": render_negative_case(
                "tex_overwrites_source",
                "# 输出覆盖源文件\n\n正文。\n",
                "--tex must end with .tex",
                work_root,
                extra_args=["--tex", str(work_root / "tex_overwrites_source" / "tex_overwrites_source.md")],
                expect_prepare_failure=False,
            ),
            "slide_draft_input": render_negative_case(
                "slide_draft_input",
                "# 逐页内容稿\n\n"
                "## 第 1 页｜标题\n\n屏幕：一句话。\n\n讲：讲稿。\n\n图：图片提示。\n\n"
                "## 第 2 页｜标题\n\n屏幕：一句话。\n\n讲：讲稿。\n\n图：图片提示。\n\n"
                "## 第 3 页｜标题\n\n屏幕：一句话。\n\n讲：讲稿。\n\n图：图片提示。\n",
                "page-by-page lecture notes or a slide draft",
                work_root,
            ),
            "compiler_failure": (
                render_compile_failure(work_root)
                if compiler_available
                else {"ok": True, "skipped": True, "reason": "no LaTeX compiler available"}
            ),
        }

    ok = (
        all(bool(result.get("ok")) for result in cases.values())
        and bool(no_cover_case.get("ok"))
        and bool(thesis_case.get("ok"))
        and all(bool(result.get("ok")) for result in negative_cases.values())
    )
    summary = {
        "ok": ok,
        "compiler_available": compiler_available,
        "cases": cases,
        "no_cover_case": no_cover_case,
        "thesis_case": thesis_case,
        "negative_cases": negative_cases,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
