"""Report regressions; fixtures and build outputs stay outside the repository."""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
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
from scripts import build_qa
from scripts import build_runtime
from scripts import report_assets
from scripts import report_citations
from scripts import report_metadata

class PrepareRegressionTests(unittest.TestCase):
    def test_abstract_headings_inside_fences_do_not_remove_body(self) -> None:
        for fence in ("```markdown", "~~~markdown", "````markdown"):
            closing = fence.removesuffix("markdown")
            lines = ["# 报告", "## 方法", fence, "## 摘要", "示例代码", "```", closing, "保留正文"]
            with self.subTest(fence=fence):
                output, metadata, _ = report_metadata.extract_abstract(lines)
                self.assertEqual(output, lines)
                self.assertEqual(metadata, {})

    def test_real_abstract_preserves_code_headings_and_keyword_examples(self) -> None:
        lines = ["# 报告", "## 摘要", "真实摘要", "```markdown", "## 方法", "关键词：示例", "```", "关键词：报告", "## 正文", "正文内容"]

        output, metadata, _ = report_metadata.extract_abstract(lines)

        self.assertEqual(output, ["# 报告", "## 正文", "正文内容"])
        self.assertIn("## 方法\n关键词：示例", metadata["abstract_zh"])
        self.assertEqual(metadata["keywords_zh"], "报告")

    def test_math_never_controls_citation_deduplication_or_qa(self) -> None:
        for formula in ("$x[1]$", "$$x[1]$$", "$$\nx[1]\n$$", r"\(x[1]\)", "\\[\nx[1]\n\\]"):
            for formula_first in (True, False):
                with self.subTest(formula=formula, formula_first=formula_first):
                    prose = "首次正文引用[1]。"
                    parts = [formula, prose] if formula_first else [prose, formula]
                    body = "\n\n".join(parts) + "\n\n再次引用[1]。"
                    deduped, report = report_citations.dedupe_repeated_citations(body)
                    self.assertIn(formula, deduped)
                    self.assertIn(prose, deduped)
                    self.assertEqual(report["removed_marker_count"], 1)
                    self.assertEqual(report_citations.collect_body_citations(formula), [])
                    self.assertEqual(report_citations.collect_invalid_body_citations(formula.replace("[1]", "[1-3-5]")), [])

    def test_escaped_currency_does_not_hide_citations(self) -> None:
        body = r"价格 \$5 引用[1]，另一个 \$6 引用[2]。"
        self.assertEqual(report_citations.collect_body_citations(body), [1, 2])

    def test_reference_images_share_inline_image_path_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "figure.png").write_bytes(b"png fixture")
            for image, definition in (
                ("![方法图][fig]", '[fig]: figure.png "标题"'),
                ("![方法图][]", "[方法图]: <figure.png>"),
                ("![方法图]", "[方法图]: figure.png"),
                ("![方法图][FIG name]", "[fig   name]: figure.png"),
            ):
                with self.subTest(image=image):
                    qa = report_assets.scan_body(image + "\n\n" + definition, root)
                    self.assertEqual(qa["image_count"], 1)
                    self.assertEqual(qa["missing_images"], [])
                    self.assertEqual(qa["unsafe_image_paths"], [])
                    self.assertEqual(qa["images"][0]["path"], "figure.png")

            qa = report_assets.scan_body("![图 1 方法图][fig]\n\n[fig]: ../outside.png", root)
            self.assertEqual(qa["unsafe_image_paths"], ["../outside.png"])
            self.assertEqual(qa["missing_images"], ["../outside.png"])
            self.assertEqual(qa["captions_with_manual_numbers"], ["图 1 方法图"])

    def test_fenced_reference_image_definition_does_not_create_an_image(self) -> None:
        body = "![方法图][fig]\n\n```markdown\n[fig]: ../outside.png\n```"
        self.assertEqual(report_assets.scan_body(body, ROOT)["image_count"], 0)

    def test_code_block_h1_is_not_used_as_title_or_deleted(self) -> None:
        lines = ["```python", "# Fake code", "```", "## 正文", "内容。"]

        output, title, warnings = report_metadata.prepare_body(lines)

        self.assertEqual(output, lines)
        self.assertIsNone(title)
        self.assertTrue(warnings)

    def test_slide_detector_ignores_fenced_examples(self) -> None:
        lines = ["```text"]
        for number in range(1, 4):
            lines.extend(
                [
                    f"## 第 {number} 页｜示例",
                    "屏幕：示例。",
                    "讲：示例。",
                    "图：示例。",
                ]
            )
        lines.append("```")

        result = report_metadata.detect_slide_draft(lines)

        self.assertFalse(result["detected"])
        self.assertEqual(result["page_heading_count"], 0)
        self.assertEqual(result["slide_field_count"], 0)

    def test_markdown_image_title_and_fragment_do_not_enter_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "figure.png"
            image.write_bytes(b"png fixture")
            qa = report_assets.scan_body(
                '![figure](figure.png "optional title")\n\n![again](figure.png#preview)\n',
                root,
            )

        self.assertEqual(qa["missing_images"], [])
        self.assertEqual(qa["unsafe_image_paths"], [])
        self.assertEqual([item["path"] for item in qa["images"]], ["figure.png", "figure.png"])

    def test_malformed_citation_range_is_reported(self) -> None:
        body = "正文引用[1-3-5]。\n\n## 参考文献\n\n[1] A.\n[2] B.\n[3] C.\n"

        qa = report_assets.scan_body(body, ROOT)

        self.assertEqual(qa["invalid_citation_markers"], ["[1-3-5]"])
        self.assertEqual(qa["citation_numbers"], [])

    def test_deduplication_preserves_unrelated_double_spaces(self) -> None:
        body = "首次引用[1]。\n\nsecond  keep  [1]  spacing\n\n## 参考文献\n\n[1] A.\n"

        deduped, report = report_citations.dedupe_repeated_citations(body)

        self.assertEqual(report["removed_marker_count"], 1)
        self.assertIn("second  keep", deduped)

    def test_nested_link_label_never_controls_citation_deduplication(self) -> None:
        references = "\n\n## References\n\n[1] Ref.\n"
        link_after, _ = report_citations.dedupe_repeated_citations(
            "正文引用[1]，再看 [link [1]](https://example.com/a_(b))." + references
        )
        link_before, _ = report_citations.dedupe_repeated_citations(
            "先看 [link [1]](https://example.com/a_(b))，再正文引用[1]." + references
        )

        self.assertIn("[link [1]](https://example.com/a_(b))", link_after)
        self.assertIn("正文引用[1]", link_after)
        self.assertIn("[link [1]](https://example.com/a_(b))", link_before)
        self.assertIn("正文引用[1]", link_before)

    def test_adjacent_numeric_citations_are_not_treated_as_reference_links(self) -> None:
        body = "正文 [1][2]。\n\n## References\n\n[1] A.\n[2] B.\n"

        deduped, report = report_citations.dedupe_repeated_citations(body)

        self.assertIn("[1][2]", deduped)
        self.assertEqual(report["removed_marker_count"], 0)
        self.assertEqual(report_citations.collect_body_citations(deduped.split("## References", 1)[0]), [1, 2])

    def test_html_comments_do_not_participate_in_citation_deduplication(self) -> None:
        """HTML comments must not own first-citation position or affect QA."""
        for comment, comment_first in (
            ("<!-- 引用 [1] 但不可见 -->", True),
            ("<!-- 引用 [1] 但不可见 -->", False),
        ):
            with self.subTest(comment=comment, comment_first=comment_first):
                prose = "首次正文引用[1]。"
                parts = [comment, prose] if comment_first else [prose, comment]
                body = "\n\n".join(parts) + "\n\n再次引用[1]。"
                deduped, report = report_citations.dedupe_repeated_citations(body)
                self.assertIn(comment, deduped)
                self.assertIn(prose, deduped)
                self.assertEqual(report["removed_marker_count"], 1)
                self.assertEqual(report_citations.collect_body_citations(body), [1])

    def test_multiline_html_comment_does_not_hide_citations(self) -> None:
        body = "<!-- 第一行 [1]\n第二行 -->\n\n正文引用[1]。\n\n再次引用[2]。\n\n## References\n\n[1] A.\n[2] B.\n"

        deduped, report = report_citations.dedupe_repeated_citations(body)

        self.assertIn("正文引用[1]。", deduped)
        self.assertIn("再次引用[2]。", deduped)
        self.assertEqual(report["removed_marker_count"], 0)
        self.assertEqual(report_citations.collect_body_citations(deduped.split("## References", 1)[0]), [1, 2])

    def test_comment_inside_code_does_not_swallow_following_citation(self) -> None:
        body = "```html\n<!-- [1] -->\n```\n\n正文引用[1]。\n\n再次引用[2]。\n\n## References\n\n[1] A.\n[2] B.\n"

        deduped, report = report_citations.dedupe_repeated_citations(body)

        self.assertIn("正文引用[1]。", deduped)
        self.assertIn("再次引用[2]。", deduped)
        self.assertEqual(report["removed_marker_count"], 0)
        self.assertEqual(report_citations.collect_body_citations(deduped.split("## References", 1)[0]), [1, 2])

    def test_comment_with_unpaired_math_delimiter_does_not_hide_citations(self) -> None:
        body = "<!-- 未配对 $x[1] -->\n\n正文引用[1]。\n\n## References\n\n[1] A.\n"

        deduped, report = report_citations.dedupe_repeated_citations(body)

        self.assertIn("正文引用[1]。", deduped)
        self.assertEqual(report["removed_marker_count"], 0)
        self.assertEqual(report_citations.collect_body_citations(deduped.split("## References", 1)[0]), [1])

    def test_comment_delimiters_precede_inline_code_and_math_masking(self) -> None:
        for body in (
            "<!-- ` -->正文引用[1]，代码 `y`。",
            "<!-- $x -->正文引用[1]，变量 $y$。",
            "代码 `<!--` 与正文引用[1]。",
            "代码 ``示例 ` <!--`` 与正文引用[1]。",
        ):
            with self.subTest(body=body):
                self.assertEqual(report_citations.collect_body_citations(body), [1])
                transformed, _ = report_citations.dedupe_repeated_citations(body + "\n\n再次引用[1]。")
                self.assertIn("正文引用[1]", transformed)
                self.assertIn("再次引用。", transformed)

    def test_escaped_comment_opening_remains_visible_prose(self) -> None:
        body = r"字面量 \<!-- [1] -->，正文引用[1]。"
        transformed, _ = report_citations.dedupe_repeated_citations(body)
        self.assertIn(r"\<!-- [1] -->", transformed)
        self.assertIn("正文引用。", transformed)

    def test_commented_bibliography_is_not_a_real_reference_section(self) -> None:
        body = "<!--\n## References\n[1] Hidden reference\n-->\n\n正文引用[1]。"
        self.assertEqual(report_citations.split_reference_section(body), (body, ""))
        self.assertEqual(report_citations.extract_reference_numbers(body), [])


    def test_reference_section_keeps_subheadings_and_ends_at_next_section(self) -> None:
        lines = [
            "# 报告", "## 正文", "引用[1][2]。", "## 参考文献",
            "### 中文文献", "[1] A.", "### 英文文献", "[2] B.", "## 附录", "附录。",
        ]
        self.assertEqual(report_citations.reference_section_bounds(lines), (3, 8))
        self.assertEqual(report_citations.reference_section_bounds(lines[:8]), (3, 8))


class BuildRegressionTests(unittest.TestCase):
    def test_pdf_publication_copies_bytes_without_removing_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "compiled.pdf"
            source.write_bytes(b"%PDF-fixture data")
            destination = root / "published/report.pdf"
            build_runtime.atomic_copy(source, destination)
            self.assertEqual(destination.read_bytes(), source.read_bytes())
            self.assertEqual(list(destination.parent.iterdir()), [destination])

    def test_command_output_is_bounded_and_preserves_head_and_tail(self) -> None:
        output = build_runtime.command_output(
            "stdout-head\n" + "x" * build_runtime.MAX_COMMAND_OUTPUT_CHARS,
            "y" * build_runtime.MAX_COMMAND_OUTPUT_CHARS + "\nstderr-tail",
        )

        self.assertLessEqual(len(output), build_runtime.MAX_COMMAND_OUTPUT_CHARS)
        self.assertTrue(output.startswith("[stdout]\nstdout-head"))
        self.assertTrue(output.endswith("stderr-tail"))
        self.assertRegex(output, r"\.\.\. \d+ characters omitted \.\.\.")

    def test_cover_field_validation_uses_prepared_values(self) -> None:
        course_cover = {
            "cover": {
                "enabled": True,
                "thesis": False,
                "course": "机器学习",
                "studentname": "张三",
                "studentid": "20260001",
            }
        }
        self.assertEqual(build_qa.validate_cover_fields(course_cover), [])

        missing = {"cover": {"enabled": True, "thesis": False}}
        self.assertEqual(
            build_qa.validate_cover_fields(missing),
            ["course, student name, and student ID are required for a course cover"],
        )

        for cover in ({"enabled": False}, {"enabled": True, "thesis": True}):
            with self.subTest(cover=cover):
                self.assertEqual(build_qa.validate_cover_fields({"cover": cover}), [])

    def test_project_lock_rejects_a_second_build_until_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            first = build_runtime.acquire_project_lock(project, timeout=0.1)
            try:
                with self.assertRaisesRegex(RuntimeError, "another build still holds"):
                    build_runtime.acquire_project_lock(project, timeout=0.01)
            finally:
                first.close()

            released = build_runtime.acquire_project_lock(project, timeout=0.1)
            released.close()

    def test_pandoc_highlight_flag_tracks_installed_cli(self) -> None:
        modern_help = mock.Mock(stdout="--syntax-highlighting=STYLE\n")
        legacy_help = mock.Mock(stdout="--no-highlight\n")

        with mock.patch.object(build_runtime, "run", return_value=modern_help):
            self.assertEqual(
                build_runtime.pandoc_no_highlight_arg("pandoc"),
                "--syntax-highlighting=none",
            )
        with mock.patch.object(build_runtime, "run", return_value=legacy_help):
            self.assertEqual(build_runtime.pandoc_no_highlight_arg("pandoc"), "--no-highlight")

    def test_source_cannot_collide_with_generated_report_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "report_body.md"
            original = "# 原始文件\n\n正文。\n"
            source.write_text(original, encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "build_course_report.py"),
                    str(source),
                    "--no-cover",
                    "--skip-compile",
                    "--work-dir",
                    str(root),
                    "--tex",
                    str(root / "out.tex"),
                    "--pdf",
                    str(root / "out.pdf"),
                ],
                cwd=ROOT,
                text=True,
            encoding="utf-8",
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("generated intermediate", completed.stderr)
            self.assertEqual(source.read_text(encoding="utf-8"), original)

    def test_output_pdf_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.md"
            source.write_text("# title\n", encoding="utf-8")
            output_dir = root / "occupied.pdf"
            output_dir.mkdir()

            with self.assertRaisesRegex(RuntimeError, "must be a file path"):
                build_runtime.validate_output_path(output_dir, source, ".pdf", "--pdf")

    def test_pdf_may_be_placed_outside_source_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.md"
            source.write_text("# title\n", encoding="utf-8")
            pdf = root / "report.pdf"

            build_runtime.validate_generated_path_collisions(source, root / "latex", root / "report.tex", pdf)

    def test_subprocess_timeout_is_bounded_and_explained(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            build_runtime.run(
                [sys.executable, "-c", "import time; time.sleep(1)"],
                timeout=0.05,
            )


class PostprocessRegressionTests(unittest.TestCase):
    def test_longtable_rich_caption_keeps_complete_nested_braces(self) -> None:
        caption = r"\textbf{方案 \emph{一}}与 \(x_{1}\) 对比"
        source = "\\begin{longtable}{c}\n\\caption{" + caption + "}\\tabularnewline\n\\endfirsthead\n\\endhead\n数据 \\\\\n\\end{longtable}"

        output = post.add_longtable_continuations(source)
        qa = post.qa_report(output, output, "")

        self.assertIn(r"\caption[]{" + caption + "（续表）}", output)
        self.assertEqual(qa["longtables_missing_endfoot"], 0)
        self.assertEqual(qa["longtables_missing_endlastfoot"], 0)
        self.assertEqual(post.add_longtable_continuations(output), output)

    def test_reference_split_ignores_unpaired_body_sentinel(self) -> None:
        tex = (
            "before\n"
            + post.REF_SENTINEL
            + "\nbody remains\n"
            + post.REF_SENTINEL
            + "\n\\phantomsection\n"
            + post.REF_MARKER
            + "\n\\addcontentsline{toc}{section}{参考文献}\n[1] A"
        )

        body, refs = post.split_references(tex)

        self.assertIn("body remains", body)
        self.assertTrue(refs.startswith(post.REF_SENTINEL))
        self.assertIn("[1] A", refs)

    def test_nonnumeric_brackets_are_not_reported_as_raw_citations(self) -> None:
        body = r"literal {[}x+y{]} and citation {[}1, 2{]}"

        qa = post.qa_report(body, body, "")

        self.assertEqual(qa["remaining_raw_citations_before_references"], ["1, 2"])

    def test_reference_href_keeps_label_and_removes_url(self) -> None:
        cleaned = post.clean_reference_tail(
            post.REF_SENTINEL
            + "\n"
            + r"[1] \href{https://example.com/a}{Publisher page}."
            + "\n"
        )

        self.assertIn("Publisher page", cleaned)
        self.assertNotIn("https://", cleaned)
        self.assertNotIn(r"\href{}", cleaned)

    def test_longtable_gets_lastfoot_and_qa_checks_it(self) -> None:
        source = r"""\begin{longtable}{c}
\caption{测试}\tabularnewline
\toprule\noalign{}
表头 \\
\midrule\noalign{}
\endfirsthead
\endhead
数据 \\
\bottomrule
\end{longtable}"""

        output = post.add_longtable_continuations(source)
        qa = post.qa_report(output, output, "")

        self.assertIn(r"\endfoot", output)
        self.assertIn(r"\endlastfoot", output)
        self.assertEqual(qa["longtables_missing_endfoot"], 0)
        self.assertEqual(qa["longtables_missing_endlastfoot"], 0)


class InputBehaviorTests(unittest.TestCase):
    def test_invalid_inputs_fail_without_publishing_or_changing_source(self):
        for name, markdown, options in (
            ("absolute_image", "# 报告\n\n![图片](/outside/figure.png)\n", []),
            ("missing_logo", "# 报告\n\n正文。\n", ["--logo", "missing.png", "--course", "课程", "--student-name", "学生", "--student-id", "001"]),
            ("bad_pdf_suffix", "# 报告\n\n正文。\n", ["--pdf", "result.md"]),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = root / "report.md"
                source.write_text(markdown, encoding="utf-8")
                cover_options = ["--no-cover"] if name != "missing_logo" else []
                with mock.patch.object(sys, "argv", ["build", str(source), *cover_options, "--skip-compile", *options]), \
                     mock.patch.object(build_runtime, "require_tool", return_value="unused-pandoc"), \
                     contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as diagnostic:
                    result = build.main()
                self.assertNotEqual(result, 0)
                self.assertTrue(diagnostic.getvalue().strip())
                self.assertEqual(source.read_text(encoding="utf-8"), markdown)
                self.assertFalse((root / "course_report.pdf").exists())

    def test_outside_work_directory_is_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            source = project / "report.md"
            source.write_text("# 报告\n", encoding="utf-8")
            outside = root / "outside"
            with mock.patch.object(sys, "argv", ["build", str(source), "--no-cover", "--work-dir", str(outside)]), \
                 contextlib.redirect_stderr(io.StringIO()):
                result = build.main()
            self.assertNotEqual(result, 0)
            self.assertFalse(outside.exists())

    def test_prepare_absolute_logo_reports_existing_asset_outside_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "report.md"
            source.write_text("# 报告\n\n## 正文\n\n正文。", encoding="utf-8")
            output = root / "latex"
            with mock.patch.object(sys, "argv", ["prepare", str(source), "--out-dir", str(output), "--logo", str(ROOT / "assets/njust_logo.png")]), contextlib.redirect_stdout(io.StringIO()):
                code = prepare.main()
            report = json.loads((output / "prepare_report.json").read_text(encoding="utf-8"))
            self.assertEqual(code, 0)
            self.assertTrue(report["cover"]["logo_exists"])
            self.assertFalse(report["cover"]["logo_inside_project"])
            self.assertTrue(report["warnings"])

    def test_quoted_front_matter_ignores_trailing_comment(self):
        fields, body = report_metadata.parse_front_matter(
            '---\ncourse: "机器学习" # 课程名\nstudent_id: 00123\n---\n# 报告\n'
        )
        self.assertEqual(fields, {"course": "机器学习", "student_id": "00123"})
        self.assertIn("# 报告", body)

    def test_invalid_front_matter_reports_the_bad_line(self):
        for value in ('course: "未闭合', 'course: "课程" garbage', 'course: |', 'not a key value', '  course: nested'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "front matter line 2"):
                report_metadata.parse_front_matter(f"---\n{value}\n---\n# 报告")

    def test_windows_resource_path_serializes_as_posix_metadata(self):
        metadata = report_metadata.yaml_block("logo", PureWindowsPath("latex/njust_logo.png"))
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
        result = build_runtime.run([sys.executable, "-c", "import sys; sys.stdout.buffer.write('机器学习'.encode('utf-8'))"])
        self.assertEqual(result.stdout, "机器学习")
        with self.assertRaises(RuntimeError) as caught:
            build_runtime.run([sys.executable, "-c", "import sys; sys.stderr.buffer.write(b'bad byte \\xff'); sys.exit(1)"])
        self.assertIn("bad byte", str(caught.exception))


class TemplateRegressionTests(unittest.TestCase):
    def test_bundled_toc_and_cover_defaults_are_consistent(self):
        tex = (ROOT / "assets/templates/ctexart-course-report.tex").read_text(encoding="utf-8")
        def macro(name):
            match = re.search(r"\\newcommand\{\\" + name + r"\}\{([^\n]*)\}", tex)
            self.assertIsNotNone(match, name)
            return match.group(1)
        chapter_font = macro("reporttocsectionfont")
        self.assertIn(r"\zihao{4}", chapter_font)
        self.assertIn(r"\bfseries", chapter_font)
        self.assertIn(r"\zihao{-4}", macro("reporttocfont"))
        chapter_entry = tex.split(r"\renewcommand*\l@section", 1)[1].split(r"\renewcommand*\l@subsection", 1)[0]
        self.assertIn(r"\reporttocsectionfont", chapter_entry)
        for level in ("section", "subsection", "subsubsection", "paragraph"):
            entry = tex.split(r"\renewcommand*\l@" + level, 1)[1].split(r"\renewcommand", 1)[0]
            self.assertIn(r"\reporttocnumwidth", entry)
        self.assertRegex(tex, r"\\def\\@pnumwidth\{[^}]+\}")
        self.assertRegex(tex, r"\\def\\@tocrmarg\{[^}]+\}")
        cover = tex.split(r"\newcommand{\coverfield}", 1)[1].split(r"\newcommand{\covercoursefield}", 1)[0]
        self.assertIn(r"\makebox[\textwidth][c]", cover)
        self.assertIn(r"\coverunderline{#2}", cover)
        self.assertIn(r"\underline{\makebox[\covervaluewidth][c]", tex)
