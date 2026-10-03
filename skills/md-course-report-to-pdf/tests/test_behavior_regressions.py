"""Observable regressions from real report inputs; all outputs are temporary."""
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
sys.path.insert(0, str(ROOT))
from scripts import build_course_report as build
from scripts import prepare_course_report as prepare
from scripts import postprocess_course_tex as post


class InputBehaviorTests(unittest.TestCase):
    def test_quoted_front_matter_ignores_trailing_comment(self):
        fields, body = prepare.parse_front_matter(
            '---\ncourse: "机器学习" # 课程名\nstudent_id: 00123\n---\n# 报告\n'
        )
        self.assertEqual(fields, {"course": "机器学习", "student_id": "00123"})
        self.assertIn("# 报告", body)

    def test_invalid_front_matter_reports_the_bad_line(self):
        for value in ('course: "未闭合', 'course: "课程" garbage', 'course: |', 'not a key value', '  course: nested'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "front matter line 2"):
                prepare.parse_front_matter(f"---\n{value}\n---\n# 报告")

    def test_windows_resource_path_serializes_as_posix_metadata(self):
        metadata = prepare.yaml_block("logo", PureWindowsPath("latex/njust_logo.png"))
        self.assertNotIn("\\", metadata)
        self.assertEqual(json.loads(metadata.split(": ", 1)[1]), "latex/njust_logo.png")

    def test_true_raw_prose_citation_is_reported(self):
        body = r"正文 {[}1{]}，代码 \texttt{array{[}2{]}}。"
        self.assertEqual(post.qa_report(body, body, "")["remaining_raw_citations_before_references"], ["1"])

    def test_real_output_alias_cannot_overwrite_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "report.md"
            original = b"# original report\n"
            source.write_bytes(original)
            alias = root / "report.tex"
            os.link(source, alias)
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/build_course_report.py"), str(source),
                 "--no-cover", "--skip-compile", "--tex", str(alias)],
                capture_output=True, text=True, encoding="utf-8", timeout=30,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(result.stderr.strip())
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(alias.read_bytes(), original)

    def test_utf8_process_output_and_invalid_diagnostics_are_readable(self):
        result = build.run([sys.executable, "-c", "import sys; sys.stdout.buffer.write('机器学习'.encode('utf-8'))"])
        self.assertEqual(result.stdout, "机器学习")
        with self.assertRaises(RuntimeError) as caught:
            build.run([sys.executable, "-c", "import sys; sys.stderr.buffer.write(b'bad byte \\xff'); sys.exit(1)"])
        self.assertIn("bad byte", str(caught.exception))


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
