"""Build smoke fixtures and check course, thesis, caption and failure cases."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

if __package__:
    from . import smoke_pdf, smoke_runtime
else:
    import smoke_pdf, smoke_runtime


def copy_standard_fixture(source: Path, work_root: Path) -> tuple[Path, Path]:
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

    return case_dir, copied_source


def build_standard_case_command(
    copied_source: Path, latex_dir: Path, tex: Path, pdf_path: Path, compiler_available: bool,
) -> list[str]:
    build_cmd = [
        sys.executable,
        str(smoke_runtime.BUILD),
        str(copied_source),
        "--work-dir",
        str(latex_dir),
        "--course",
        smoke_runtime.COURSE,
        "--student-name",
        smoke_runtime.STUDENT_NAME,
        "--student-id",
        smoke_runtime.STUDENT_ID,
        "--tex",
        str(tex),
        "--pdf",
        str(pdf_path),
    ]
    if not compiler_available:
        build_cmd.append("--skip-compile")

    return build_cmd


def check_standard_pdf(
    source: Path, pdf_path: Path, build_summary: dict[str, object], errors: list[str],
) -> dict[str, object]:
    smoke_runtime.check(pdf_path.exists(), "compiled PDF must exist", errors)
    smoke_runtime.check(pdf_path.exists() and pdf_path.stat().st_size > 0, "compiled PDF must be nonempty", errors)
    smoke_runtime.check(build_summary.get("pdf") == str(pdf_path), "summary must identify the sole PDF output", errors)
    pdf_qa = smoke_pdf.inspect_pdf(pdf_path)
    smoke_runtime.check(pdf_qa.get("header_valid") is True, "PDF header must be valid", errors)
    if shutil.which("pdfinfo"):
        smoke_runtime.check(isinstance(pdf_qa.get("page_count"), int) and int(pdf_qa["page_count"]) > 0, "PDF must have pages", errors)
        smoke_runtime.check(pdf_qa.get("a4_portrait") is True, "PDF pages must be A4 portrait", errors)
    if shutil.which("pdffonts"):
        smoke_runtime.check(pdf_qa.get("embedded_fonts") is True, "PDF fonts must be embedded", errors)
    if shutil.which("qpdf"):
        smoke_runtime.check(pdf_qa.get("qpdf_check") is True, "qpdf structure check must pass", errors)
    if source.name == "table_report.md":
        if shutil.which("pdfinfo"):
            smoke_runtime.check(isinstance(pdf_qa.get("page_count"), int) and int(pdf_qa["page_count"]) >= 8, "longtable fixture must span multiple pages", errors)
        if shutil.which("pdftotext"):
            smoke_runtime.check(pdf_qa.get("continued_table_text") is True, "continued longtable caption must render on a later page", errors)
            smoke_runtime.check(
                pdf_qa.get("continued_table_pages_valid") is True,
                "every later page containing longtable rows must repeat the continued caption",
                errors,
            )
    return pdf_qa


def render_case(source: Path, work_root: Path, compiler_available: bool) -> dict[str, object]:
    case_dir, copied_source = copy_standard_fixture(source, work_root)
    latex_dir = case_dir / "latex"
    tex = case_dir / "report.tex"
    pdf_path = work_root / "published" / source.stem / "final.pdf"
    build_cmd = build_standard_case_command(copied_source, latex_dir, tex, pdf_path, compiler_available)

    built = smoke_runtime.run(build_cmd, case_dir)
    if built.returncode != 0:
        return smoke_runtime.fail("build failed", {"stdout": built.stdout, "stderr": built.stderr})

    try:
        build_summary = json.loads(built.stdout)
    except json.JSONDecodeError:
        return smoke_runtime.fail("build summary is not JSON", {"stdout": built.stdout, "stderr": built.stderr})

    if not tex.exists():
        return smoke_runtime.fail("expected TeX output missing", str(tex))
    report = smoke_runtime.load_json(latex_dir / "prepare_report.json")

    errors: list[str] = []
    qa = report.get("qa", {})
    if not isinstance(qa, dict):
        return smoke_runtime.fail("prepare QA is not an object", report)

    cover = report.get("cover", {})
    if not isinstance(cover, dict):
        return smoke_runtime.fail("cover QA is not an object", report)
    smoke_runtime.check(
        cover.get("logo_exists") is smoke_runtime.LOCAL_DEFAULT_LOGO.exists(),
        "default logo QA must match local asset availability",
        errors,
    )

    pdf_qa = (
        check_standard_pdf(source, pdf_path, build_summary, errors)
        if compiler_available
        else None
    )

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


def check_no_cover_outputs(
    latex_dir: Path, tex: Path, pdf_path: Path, compiler_available: bool,
) -> tuple[list[str], dict[str, object] | None]:
    report = smoke_runtime.load_json(latex_dir / "prepare_report.json")
    tex_text = tex.read_text(encoding="utf-8") if tex.exists() else ""
    cover = report.get("cover", {})

    errors: list[str] = []
    smoke_runtime.check(tex.exists(), "no-cover TeX output must exist", errors)
    smoke_runtime.check(isinstance(cover, dict), "no-cover QA must include cover object", errors)
    if isinstance(cover, dict):
        smoke_runtime.check(cover.get("enabled") is False, "cover.enabled must be false when --no-cover is used", errors)
    smoke_runtime.check(r"\begin{titlepage}" not in tex_text, "no-cover output must not contain a titlepage", errors)
    qa = report.get("qa", {})
    smoke_runtime.check(isinstance(qa, dict) and qa.get("image_count") == 1, "no-cover case must process one real image", errors)
    if compiler_available:
        smoke_runtime.check(pdf_path.exists(), "no-cover compiled PDF must exist", errors)
        smoke_runtime.check(pdf_path.exists() and pdf_path.stat().st_size > 0, "no-cover compiled PDF must be nonempty", errors)
        smoke_runtime.check(tex.with_suffix(".log").exists(), "--keep-intermediates must preserve the compiler log", errors)
        smoke_runtime.check(tex.with_suffix(".aux").exists(), "--keep-intermediates must preserve the aux file", errors)
        pdf_qa = smoke_pdf.inspect_pdf(pdf_path)
        if shutil.which("pdfimages"):
            smoke_runtime.check(isinstance(pdf_qa.get("image_count"), int) and int(pdf_qa["image_count"]) >= 1, "rendered PDF must contain the fixture image", errors)
    else:
        pdf_qa = None
    return errors, pdf_qa


def render_no_cover_case(source: Path, work_root: Path, compiler_available: bool) -> dict[str, object]:
    case_dir = work_root / "no_cover"
    case_dir.mkdir(parents=True)
    copied_source = case_dir / source.name
    shutil.copy2(source, copied_source)
    fixture_image = case_dir / "fixture.png"
    shutil.copy2(smoke_runtime.LOCAL_DEFAULT_LOGO, fixture_image)
    copied_source.write_text(
        copied_source.read_text(encoding="utf-8") + "\n\n![烟测图片](fixture.png)\n",
        encoding="utf-8",
    )

    latex_dir = case_dir / "latex"
    tex = case_dir / "report.tex"
    pdf_path = case_dir / "report.pdf"
    build_cmd = [
        sys.executable,
        str(smoke_runtime.BUILD),
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
    built = smoke_runtime.run(build_cmd, case_dir)
    if built.returncode != 0:
        return smoke_runtime.fail("no-cover build failed", {"stdout": built.stdout, "stderr": built.stderr})

    try:
        build_summary = json.loads(built.stdout)
    except json.JSONDecodeError:
        return smoke_runtime.fail("no-cover build summary is not JSON", {"stdout": built.stdout, "stderr": built.stderr})

    errors, pdf_qa = check_no_cover_outputs(latex_dir, tex, pdf_path, compiler_available)
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
        str(smoke_runtime.BUILD),
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
    built = smoke_runtime.run(build_cmd, case_dir)
    if built.returncode != 0:
        return smoke_runtime.fail("thesis build failed", {"stdout": built.stdout, "stderr": built.stderr})

    report = smoke_runtime.load_json(latex_dir / "prepare_report.json")
    post_qa = smoke_runtime.load_json(latex_dir / "postprocess_qa.json")
    cover = report.get("cover", {})
    qa = report.get("qa", {})
    errors: list[str] = []
    smoke_runtime.check(report.get("warnings") == [], "thesis prepare warnings must be empty", errors)
    smoke_runtime.check(isinstance(cover, dict) and cover.get("thesis") is True, "thesis cover must be detected from front matter", errors)
    smoke_runtime.check(post_qa.get("thesis_cover_rendered") is True, "thesis titlepage must be rendered", errors)
    smoke_runtime.check(post_qa.get("course_cover_rendered") is False, "course cover must not render for thesis input", errors)
    tex_text = tex.read_text(encoding="utf-8") if tex.exists() else ""
    smoke_runtime.check("硕士学位论文" in tex_text, "thesis degree type must appear on the cover", errors)
    smoke_runtime.check("分类号" in tex_text and "论文提交时间" in tex_text, "thesis cover field labels must appear", errors)
    if isinstance(qa, dict):
        smoke_runtime.check(qa.get("citation_numbers") == [1, 2, 3], "thesis template citations must be [1, 2, 3]", errors)
        smoke_runtime.check(qa.get("reference_numbers") == [1, 2, 3], "thesis template references must be [1, 2, 3]", errors)
    if compiler_available:
        smoke_runtime.check(pdf_path.exists() and pdf_path.stat().st_size > 0, "thesis compiled PDF must be nonempty", errors)
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
    built = smoke_runtime.run(
        [
            sys.executable,
            str(smoke_runtime.BUILD),
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
    smoke_runtime.check(built.returncode != 0, "invalid LaTeX must fail compilation", errors)
    smoke_runtime.check(bool(built.stderr.strip()), "compiler failure diagnostics must be nonempty", errors)
    smoke_runtime.check(source.read_text(encoding="utf-8") == original_source, "compiler failure must preserve the source", errors)
    smoke_runtime.check(len(built.stderr) <= 17_000, "compiler failure diagnostics must stay bounded", errors)
    smoke_runtime.check(not pdf_path.exists(), "failed compilation must not leave a final PDF", errors)
    return {"ok": not errors, "errors": errors, "stderr": built.stderr}


def render_absolute_logo_case(work_root: Path, compiler_available: bool) -> dict[str, object]:
    case_dir = work_root / "absolute_logo_path"
    case_dir.mkdir(parents=True)
    source = case_dir / "absolute_logo_path.md"
    shutil.copy2(smoke_runtime.EXAMPLES / "minimal_report.md", source)

    latex_dir = case_dir / "latex"
    tex = case_dir / "report.tex"
    pdf_path = case_dir / "report.pdf"
    build_cmd = [
        sys.executable,
        str(smoke_runtime.BUILD),
        str(source),
        "--work-dir",
        str(latex_dir),
        "--course",
        smoke_runtime.COURSE,
        "--student-name",
        smoke_runtime.STUDENT_NAME,
        "--student-id",
        smoke_runtime.STUDENT_ID,
        "--logo",
        str(smoke_runtime.LOCAL_DEFAULT_LOGO.resolve()),
        "--tex",
        str(tex),
        "--pdf",
        str(pdf_path),
    ]
    if not compiler_available:
        build_cmd.append("--skip-compile")
    built = smoke_runtime.run(build_cmd, case_dir)
    if built.returncode != 0:
        return smoke_runtime.fail("absolute logo build failed", {"stdout": built.stdout, "stderr": built.stderr})

    report = smoke_runtime.load_json(latex_dir / "prepare_report.json")
    cover = report.get("cover", {})
    errors: list[str] = []
    smoke_runtime.check(isinstance(cover, dict), "absolute logo QA must include cover object", errors)
    if isinstance(cover, dict):
        logo_path = str(cover.get("logo_path", ""))
        smoke_runtime.check(cover.get("logo_exists") is True, "absolute logo copy must exist", errors)
        smoke_runtime.check(cover.get("logo_inside_project") is True, "absolute logo copy must be inside project", errors)
        smoke_runtime.check(not Path(logo_path).is_absolute(), "absolute logo must be converted to a relative project path", errors)
    if compiler_available:
        smoke_runtime.check(pdf_path.exists(), "absolute logo compiled PDF must exist", errors)
        smoke_runtime.check(pdf_path.exists() and pdf_path.stat().st_size > 0, "absolute logo compiled PDF must be nonempty", errors)
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
        built = smoke_runtime.run([sys.executable, str(smoke_runtime.BUILD), str(copied), "--no-cover", *options], case_dir)
        tex = case_dir / "course_report.tex"
        errors: list[str] = []
        smoke_runtime.check(built.returncode == 0, "supported table caption must build", errors)
        smoke_runtime.check(tex.exists() and r"\caption{标题}" in tex.read_text(encoding="utf-8"), "caption must survive Pandoc", errors)
        results[name] = {"ok": not errors, "errors": errors, "stderr": built.stderr}
    return results
