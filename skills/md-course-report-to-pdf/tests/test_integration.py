"""Report regressions; fixtures and build outputs stay outside the repository."""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
from scripts import build_course_report as build
from scripts import prepare_course_report as prepare
from scripts import postprocess_course_tex as post

if os.environ.get("MD_COURSE_REPORT_REQUIRE_PANDOC") == "1" and not shutil.which("pandoc"):
    raise RuntimeError("Pandoc is required for CI integration tests")

@unittest.skipUnless(shutil.which("pandoc"), "pandoc is required for report integration")
class BuildIntegrationTests(unittest.TestCase):
    def test_student_id_keeps_leading_zeroes_and_all_digits_through_pandoc(self) -> None:
        for student_id in ("0000000000", "000123456789012345678901234567890123456789"):
            with self.subTest(student_id=student_id), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = root / "report.md"
                source.write_text("# 报告\n\n## 正文\n\n内容。\n", encoding="utf-8")
                tex = root / "report.tex"
                completed = subprocess.run(
                    [sys.executable, str(SCRIPTS / "build_course_report.py"), str(source),
                     "--course", "示例课程", "--student-name", "示例学生",
                     "--student-id", student_id, "--tex", str(tex), "--skip-compile"],
                    text=True, encoding="utf-8", capture_output=True, timeout=30, check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                metadata = root / "latex" / "metadata.yaml"
                parsed = subprocess.run(
                    [shutil.which("pandoc") or "pandoc", "--from=markdown", "--to=json", "--metadata-file", str(metadata)],
                    input="", text=True, encoding="utf-8", capture_output=True, timeout=30, check=True,
                )
                student_value = json.loads(parsed.stdout)["meta"]["studentid"]
                self.assertEqual(student_value, {"t": "MetaInlines", "c": [{"t": "Str", "c": student_id}]})
                self.assertIn(r"\newcommand{\studentid}{" + student_id + "}", tex.read_text(encoding="utf-8"))

    def test_reference_image_outside_project_is_rejected_before_pandoc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "report.md"
            source.write_text("# 报告\n\n## 正文\n\n![方法图][fig]\n\n[fig]: ../outside.png\n", encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "build_course_report.py"), str(source), "--no-cover", "--skip-compile"],
                text=True, encoding="utf-8", capture_output=True, timeout=30, check=False,
            )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("outside.png", completed.stderr)

    def test_course_cover_front_matter_builds_without_cli_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "report.md"
            source.write_text(
                "---\n"
                "course: 机器学习\n"
                "student_name: 张三\n"
                "student_id: 20260001\n"
                "---\n"
                "# 课程报告\n\n"
                "## 正文\n\n内容。\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "build_course_report.py"),
                    str(source),
                    "--skip-compile",
                ],
                cwd=ROOT,
                text=True,
            encoding="utf-8",
                capture_output=True,
                check=False,
                timeout=30,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_build_exposes_prepare_warnings_without_corrupting_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "report.md"
            source.write_text("# 课程报告\n\n## 正文\n\n内容。\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "build_course_report.py"),
                    str(source),
                    "--no-cover",
                    "--skip-compile",
                ],
                cwd=ROOT,
                text=True,
            encoding="utf-8",
                capture_output=True,
                check=False,
                timeout=30,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        summary = json.loads(completed.stdout)
        self.assertGreater(summary["warning_count"], 0)
        self.assertEqual(summary["warning_count"], len(summary["warnings"]))
        self.assertIn("prepare warning:", completed.stderr)
        self.assertTrue(any("摘要" in warning for warning in summary["warnings"]))


@unittest.skipUnless(shutil.which("pandoc"), "pandoc is required for Lua filter regression tests")
class LuaFilterRegressionTests(unittest.TestCase):
    def run_pandoc(self, markdown: str, *extra_args: str) -> str:
        completed = subprocess.run(
            [
                shutil.which("pandoc") or "pandoc",
                "--from=markdown+raw_tex+tex_math_dollars",
                "--to=latex",
                f"--lua-filter={SCRIPTS / 'drop_first_h1.lua'}",
                *extra_args,
            ],
            input=markdown,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
            timeout=30,
        )
        return completed.stdout

    def test_ordered_lists_keep_single_multiple_and_nested_items(self) -> None:
        for markdown, labels in (
            ("1. Single [1]\n", ["Single"]),
            ("1. First [1]\n2. Second [2]\n3. Third [3]\n", ["First", "Second", "Third"]),
            ("1. Outer [1]\n\n    1. Inner [2]\n    2. Nested [3]\n", ["Outer", "Inner", "Nested"]),
        ):
            with self.subTest(markdown=markdown):
                output = self.run_pandoc(markdown)
                self.assertEqual(output.count(r"\item"), len(labels))
                for number, label in enumerate(labels, 1):
                    self.assertIn(label, output)
                    self.assertIn(r"\textsupcite{" + str(number) + "}", output)

    def test_pandoc_rich_table_caption_gets_continuation(self) -> None:
        tex = self.run_pandoc("| A | B |\n|---|---|\n| 1 | 2 |\n: **方案**对比\n")
        output = post.add_longtable_continuations(tex)
        self.assertIn(r"\caption*{\textbf{方案}对比（续表）}", output)
        self.assertIn(r"\endfoot", output)
        self.assertIn(r"\endlastfoot", output)

    def test_prepared_math_and_first_prose_citation_survive_pandoc(self) -> None:
        prepared, _ = prepare.dedupe_repeated_citations(
            "$x[1]$\n\n首次引用[1]。\n\n$$\ny[1]\n$$\n\n再次引用[1]。"
        )
        output = self.run_pandoc(prepared)
        self.assertIn("x[1]", output)
        self.assertIn("y[1]", output)
        self.assertEqual(output.count(r"\textsupcite{1}"), 1)

    def test_citation_and_display_math_transform_only_semantic_nodes(self) -> None:
        output = self.run_pandoc(
            "正文 A [1] and.\n\n"
            "`code [2]`\n\n"
            "[link [3]](https://example.com)\n\n"
            "```text\ncode block [4]\n\\[raw-code\\]\n```\n\n"
            "$$x + y$$\n\n"
            "\\[raw + tex\\]\n"
        )

        self.assertIn(r"A \textsupcite{1} and", output)
        self.assertNotIn(r"\textsupcite{2}", output)
        self.assertNotIn(r"\textsupcite{3}", output)
        self.assertNotIn(r"\textsupcite{4}", output)
        self.assertIn(r"\begin{equation}", output)
        self.assertIn("raw + tex", output)

    def test_only_matching_metadata_title_is_removed(self) -> None:
        output = self.run_pandoc(
            "# Preface\n\ntext\n\n# Actual Title\n\nbody\n",
            "--metadata=title:Actual Title",
        )

        self.assertIn(r"\section{Preface}", output)
        self.assertNotIn(r"\section{Actual Title}", output)

    def test_prepare_normalizes_supported_citation_punctuation_for_lua(self) -> None:
        prepared, _ = prepare.dedupe_repeated_citations("正文 [1, 2]、[3，4]、[5–6]。")

        output = self.run_pandoc(prepared)

        self.assertIn(r"\textsupcite{1-2}", output)
        self.assertIn(r"\textsupcite{3-4}", output)
        self.assertIn(r"\textsupcite{5-6}", output)
@unittest.skipUnless(shutil.which("pandoc"), "pandoc is required for report integration")
class ReportBehaviorTests(unittest.TestCase):
    def build_report(self, root, markdown, *options):
        source = root / "report.md"
        source.write_text(markdown, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/build_course_report.py"), str(source),
             "--no-cover", "--skip-compile", *options],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        tex_path = root / "course_report.tex"
        return result, tex_path.read_text(encoding="utf-8") if tex_path.exists() else ""

    def test_code_links_and_raw_latex_do_not_block_report(self):
        body = (
            '# 报告\n\n## 正文\n\n代码 `array[1]`，'
            '[链接 [2]](https://example.com/code)。\n\n'
            '```{=latex}\n\\textbf{raw [3]}\n```\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            result, tex = self.build_report(Path(tmp), body)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(r"\texttt{array{[}1{]}}", tex)
            self.assertIn("https://example.com/code", tex)
            self.assertIn(r"\textbf{raw [3]}", tex)

    def test_real_remaining_prose_citation_blocks_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, _ = self.build_report(Path(tmp), "# 报告\n\n## 方法[1]\n\n正文。\n\n## 参考文献\n[1] A.\n")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((Path(tmp) / "course_report.pdf").exists())

    def test_appendix_keeps_url_and_converts_its_citation(self):
        for heading in ("## 附录", "# 附录"):
            with self.subTest(heading=heading), tempfile.TemporaryDirectory() as tmp:
                result, tex = self.build_report(Path(tmp),
                    "# 报告\n\n## 正文\n\n引用[1]。\n\n## 参考文献\n"
                    "[1] A. https://example.com/reference\n\n" + heading +
                    "\n\n复现 https://example.com/code ，附录引用[1]。\n")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("https://example.com/code", tex)
                self.assertNotIn("https://example.com/reference", tex)
                self.assertIn(r"附录引用\textsupcite{1}", tex)
                self.assertLess(tex.index("参考文献}", tex.index(r"\begin{document}")), tex.index(r"\section{附录}"))

    def test_pandoc_caption_forms_build_and_missing_or_manual_captions_fail(self):
        table = "| A | B |\n|---|---|\n| 1 | 2 |\n"
        for markdown in (table + "\n: 标题\n", ": 标题\n\n" + table, table + "\nTable: 标题\n"):
            with self.subTest(markdown=markdown), tempfile.TemporaryDirectory() as tmp:
                result, tex = self.build_report(Path(tmp), "# 报告\n\n## 正文\n\n" + markdown)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(r"\caption{标题}", tex)
        for markdown in (table, table + ": 表 1 标题\n"):
            with self.subTest(markdown=markdown), tempfile.TemporaryDirectory() as tmp:
                result, _ = self.build_report(Path(tmp), "# 报告\n\n## 正文\n\n" + markdown)
                self.assertNotEqual(result.returncode, 0)

    def test_raw_display_math_with_tag_or_label_builds(self):
        for formula in (r"\[x+y\tag{A}\]", r"\[x+y\label{eq:custom}\]"):
            with self.subTest(formula=formula), tempfile.TemporaryDirectory() as tmp:
                result, tex = self.build_report(Path(tmp), "# 报告\n\n## 正文\n\n```{=latex}\n" + formula + "\n```\n")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(formula, tex)

    def test_keep_repeated_citations_switch_preserves_both_annotations(self):
        for options, count in (((), 1), (("--keep-repeated-citations",), 2)):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as tmp:
                result, tex = self.build_report(Path(tmp), "# 报告\n\n## 正文\n\n首次[1]。\n\n再次[1]。\n\n## 参考文献\n[1] A.\n", *options)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(tex.count(r"\textsupcite{1}"), count)

    def test_keep_reference_urls_switch_preserves_bibliography_url(self):
        for options, expected in (((), False), (("--keep-reference-urls",), True)):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as tmp:
                result, tex = self.build_report(Path(tmp), "# 报告\n\n## 正文\n\n引用[1]。\n\n## 参考文献\n[1] A. https://example.com/reference\n", *options)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual("https://example.com/reference" in tex, expected)

    def test_slide_draft_warns_but_builds_with_or_without_deprecated_flag(self):
        markdown = "# 报告\n" + "\n".join(
            f"## 第 {n} 页｜标题\n\n屏幕：内容。\n\n讲：内容。\n\n图：内容。" for n in range(1, 4))
        for options in ((), ("--allow-slide-draft",)):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as tmp:
                result, tex = self.build_report(Path(tmp), markdown, *options)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(any("逐页" in warning for warning in json.loads(result.stdout)["warnings"]))
                self.assertIn("屏幕：内容", tex)

    def test_success_and_failure_preserve_existing_logs_and_unrelated_pdf(self):
        # Simulated compiler output makes publication/cleanup regression offline.
        for succeeds in (True, False):
            with self.subTest(succeeds=succeeds), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = root / "report.md"
                source.write_text("# 报告\n\n## 正文\n\n正文。\n", encoding="utf-8")
                log = root / "report.log"
                log.write_bytes(b"existing log")
                unrelated = root / "old.pdf"
                unrelated.write_bytes(b"%PDF-unrelated")
                pdf = root / "report.pdf"
                pdf.write_bytes(b"%PDF-previous")
                original_run = build.run
                original_which = shutil.which
                def compiler_run(cmd, cwd=None, timeout=180):
                    if cmd[0] == "fixture-tectonic":
                        output = Path(cmd[cmd.index("--outdir") + 1]) / "report.pdf"
                        output.write_bytes(b"%PDF-newly-compiled")
                        if not succeeds:
                            raise RuntimeError("fixture compilation failed")
                        return subprocess.CompletedProcess(cmd, 0, "compiled", "")
                    return original_run(cmd, cwd=cwd, timeout=timeout)
                with mock.patch.object(sys, "argv", ["build", str(source), "--no-cover", "--tex", "report.tex", "--pdf", "report.pdf"]), \
                     mock.patch.object(build.shutil, "which", side_effect=lambda name: "fixture-tectonic" if name == "tectonic" else original_which(name)), \
                     mock.patch.object(build, "run", side_effect=compiler_run), \
                     contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    code = build.main()
                self.assertEqual(code, 0 if succeeds else 1)
                self.assertEqual(log.read_bytes(), b"existing log")
                self.assertEqual(unrelated.read_bytes(), b"%PDF-unrelated")
                self.assertEqual(pdf.read_bytes(), b"%PDF-newly-compiled" if succeeds else b"%PDF-previous")
