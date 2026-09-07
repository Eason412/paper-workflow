from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))

from scripts import build_course_report as build  # noqa: E402
from scripts import postprocess_course_tex as post  # noqa: E402
from scripts import prepare_course_report as prepare  # noqa: E402


class PrepareRegressionTests(unittest.TestCase):
    def test_abstract_headings_inside_fences_do_not_remove_body(self) -> None:
        for fence in ("```markdown", "~~~markdown", "````markdown"):
            closing = fence.removesuffix("markdown")
            lines = ["# 报告", "## 方法", fence, "## 摘要", "示例代码", "```", closing, "保留正文"]
            with self.subTest(fence=fence):
                output, metadata, _ = prepare.extract_abstract(lines)
                self.assertEqual(output, lines)
                self.assertEqual(metadata, {})

    def test_real_abstract_preserves_code_headings_and_keyword_examples(self) -> None:
        lines = ["# 报告", "## 摘要", "真实摘要", "```markdown", "## 方法", "关键词：示例", "```", "关键词：报告", "## 正文", "正文内容"]

        output, metadata, _ = prepare.extract_abstract(lines)

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
                    deduped, report = prepare.dedupe_repeated_citations(body)
                    self.assertIn(formula, deduped)
                    self.assertIn(prose, deduped)
                    self.assertEqual(report["removed_marker_count"], 1)
                    self.assertEqual(prepare.collect_body_citations(formula), [])
                    self.assertEqual(prepare.collect_invalid_body_citations(formula.replace("[1]", "[1-3-5]")), [])

    def test_escaped_currency_does_not_hide_citations(self) -> None:
        body = r"价格 \$5 引用[1]，另一个 \$6 引用[2]。"
        self.assertEqual(prepare.collect_body_citations(body), [1, 2])

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
                    qa = prepare.scan_body(image + "\n\n" + definition, root)
                    self.assertEqual(qa["image_count"], 1)
                    self.assertEqual(qa["missing_images"], [])
                    self.assertEqual(qa["unsafe_image_paths"], [])
                    self.assertEqual(qa["images"][0]["path"], "figure.png")

            qa = prepare.scan_body("![图 1 方法图][fig]\n\n[fig]: ../outside.png", root)
            self.assertEqual(qa["unsafe_image_paths"], ["../outside.png"])
            self.assertEqual(qa["missing_images"], ["../outside.png"])
            self.assertEqual(qa["captions_with_manual_numbers"], ["图 1 方法图"])

    def test_fenced_reference_image_definition_does_not_create_an_image(self) -> None:
        body = "![方法图][fig]\n\n```markdown\n[fig]: ../outside.png\n```"
        self.assertEqual(prepare.scan_body(body, ROOT)["image_count"], 0)

    def test_code_block_h1_is_not_used_as_title_or_deleted(self) -> None:
        lines = ["```python", "# Fake code", "```", "## 正文", "内容。"]

        output, title, warnings = prepare.prepare_body(lines)

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

        result = prepare.detect_slide_draft(lines)

        self.assertFalse(result["detected"])
        self.assertEqual(result["page_heading_count"], 0)
        self.assertEqual(result["slide_field_count"], 0)

    def test_markdown_image_title_and_fragment_do_not_enter_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "figure.png"
            image.write_bytes(b"png fixture")
            qa = prepare.scan_body(
                '![figure](figure.png "optional title")\n\n![again](figure.png#preview)\n',
                root,
            )

        self.assertEqual(qa["missing_images"], [])
        self.assertEqual(qa["unsafe_image_paths"], [])
        self.assertEqual([item["path"] for item in qa["images"]], ["figure.png", "figure.png"])

    def test_malformed_citation_range_is_reported(self) -> None:
        body = "正文引用[1-3-5]。\n\n## 参考文献\n\n[1] A.\n[2] B.\n[3] C.\n"

        qa = prepare.scan_body(body, ROOT)

        self.assertEqual(qa["invalid_citation_markers"], ["[1-3-5]"])
        self.assertEqual(qa["citation_numbers"], [])

    def test_deduplication_preserves_unrelated_double_spaces(self) -> None:
        body = "首次引用[1]。\n\nsecond  keep  [1]  spacing\n\n## 参考文献\n\n[1] A.\n"

        deduped, report = prepare.dedupe_repeated_citations(body)

        self.assertEqual(report["removed_marker_count"], 1)
        self.assertIn("second  keep", deduped)

    def test_nested_link_label_never_controls_citation_deduplication(self) -> None:
        references = "\n\n## References\n\n[1] Ref.\n"
        link_after, _ = prepare.dedupe_repeated_citations(
            "正文引用[1]，再看 [link [1]](https://example.com/a_(b))." + references
        )
        link_before, _ = prepare.dedupe_repeated_citations(
            "先看 [link [1]](https://example.com/a_(b))，再正文引用[1]." + references
        )

        self.assertIn("[link [1]](https://example.com/a_(b))", link_after)
        self.assertIn("正文引用[1]", link_after)
        self.assertIn("[link [1]](https://example.com/a_(b))", link_before)
        self.assertIn("正文引用[1]", link_before)

    def test_adjacent_numeric_citations_are_not_treated_as_reference_links(self) -> None:
        body = "正文 [1][2]。\n\n## References\n\n[1] A.\n[2] B.\n"

        deduped, report = prepare.dedupe_repeated_citations(body)

        self.assertIn("[1][2]", deduped)
        self.assertEqual(report["removed_marker_count"], 0)
        self.assertEqual(prepare.collect_body_citations(deduped.split("## References", 1)[0]), [1, 2])

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
                deduped, report = prepare.dedupe_repeated_citations(body)
                self.assertIn(comment, deduped)
                self.assertIn(prose, deduped)
                self.assertEqual(report["removed_marker_count"], 1)
                self.assertEqual(prepare.collect_body_citations(body), [1])

    def test_multiline_html_comment_does_not_hide_citations(self) -> None:
        body = "<!-- 第一行 [1]\n第二行 -->\n\n正文引用[1]。\n\n再次引用[2]。\n\n## References\n\n[1] A.\n[2] B.\n"

        deduped, report = prepare.dedupe_repeated_citations(body)

        self.assertIn("正文引用[1]。", deduped)
        self.assertIn("再次引用[2]。", deduped)
        self.assertEqual(report["removed_marker_count"], 0)
        self.assertEqual(prepare.collect_body_citations(deduped.split("## References", 1)[0]), [1, 2])

    def test_comment_inside_code_does_not_swallow_following_citation(self) -> None:
        body = "```html\n<!-- [1] -->\n```\n\n正文引用[1]。\n\n再次引用[2]。\n\n## References\n\n[1] A.\n[2] B.\n"

        deduped, report = prepare.dedupe_repeated_citations(body)

        self.assertIn("正文引用[1]。", deduped)
        self.assertIn("再次引用[2]。", deduped)
        self.assertEqual(report["removed_marker_count"], 0)
        self.assertEqual(prepare.collect_body_citations(deduped.split("## References", 1)[0]), [1, 2])

    def test_comment_with_unpaired_math_delimiter_does_not_hide_citations(self) -> None:
        body = "<!-- 未配对 $x[1] -->\n\n正文引用[1]。\n\n## References\n\n[1] A.\n"

        deduped, report = prepare.dedupe_repeated_citations(body)

        self.assertIn("正文引用[1]。", deduped)
        self.assertEqual(report["removed_marker_count"], 0)
        self.assertEqual(prepare.collect_body_citations(deduped.split("## References", 1)[0]), [1])

    def test_comment_delimiters_precede_inline_code_and_math_masking(self) -> None:
        for body in (
            "<!-- ` -->正文引用[1]，代码 `y`。",
            "<!-- $x -->正文引用[1]，变量 $y$。",
            "代码 `<!--` 与正文引用[1]。",
            "代码 ``示例 ` <!--`` 与正文引用[1]。",
        ):
            with self.subTest(body=body):
                self.assertEqual(prepare.collect_body_citations(body), [1])
                transformed, _ = prepare.dedupe_repeated_citations(body + "\n\n再次引用[1]。")
                self.assertIn("正文引用[1]", transformed)
                self.assertIn("再次引用。", transformed)

    def test_escaped_comment_opening_remains_visible_prose(self) -> None:
        body = r"字面量 \<!-- [1] -->，正文引用[1]。"
        transformed, _ = prepare.dedupe_repeated_citations(body)
        self.assertIn(r"\<!-- [1] -->", transformed)
        self.assertIn("正文引用。", transformed)

    def test_commented_bibliography_is_not_a_real_reference_section(self) -> None:
        body = "<!--\n## References\n[1] Hidden reference\n-->\n\n正文引用[1]。"
        self.assertEqual(prepare.split_reference_section(body), (body, ""))
        self.assertEqual(prepare.extract_reference_numbers(body), [])


class BuildRegressionTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("pandoc"), "pandoc is required for metadata integration")
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
                    text=True, capture_output=True, timeout=30, check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                metadata = root / "latex" / "metadata.yaml"
                parsed = subprocess.run(
                    [shutil.which("pandoc") or "pandoc", "--from=markdown", "--to=json", "--metadata-file", str(metadata)],
                    input="", text=True, capture_output=True, timeout=30, check=True,
                )
                student_value = json.loads(parsed.stdout)["meta"]["studentid"]
                self.assertEqual(student_value, {"t": "MetaInlines", "c": [{"t": "Str", "c": student_id}]})
                self.assertIn(r"\newcommand{\studentid}{" + student_id + "}", tex.read_text(encoding="utf-8"))

    @unittest.skipUnless(shutil.which("pandoc"), "pandoc is required for build integration")
    def test_reference_image_outside_project_is_rejected_before_pandoc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "report.md"
            source.write_text("# 报告\n\n## 正文\n\n![方法图][fig]\n\n[fig]: ../outside.png\n", encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "build_course_report.py"), str(source), "--no-cover", "--skip-compile"],
                text=True, capture_output=True, timeout=30, check=False,
            )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("outside.png", completed.stderr)

    def test_command_output_is_bounded_and_preserves_head_and_tail(self) -> None:
        output = build.command_output(
            "stdout-head\n" + "x" * build.MAX_COMMAND_OUTPUT_CHARS,
            "y" * build.MAX_COMMAND_OUTPUT_CHARS + "\nstderr-tail",
        )

        self.assertLessEqual(len(output), build.MAX_COMMAND_OUTPUT_CHARS)
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
        self.assertEqual(build.validate_cover_fields(course_cover), [])

        missing = {"cover": {"enabled": True, "thesis": False}}
        self.assertEqual(
            build.validate_cover_fields(missing),
            ["course, student name, and student ID are required for a course cover"],
        )

        for cover in ({"enabled": False}, {"enabled": True, "thesis": True}):
            with self.subTest(cover=cover):
                self.assertEqual(build.validate_cover_fields({"cover": cover}), [])

    @unittest.skipUnless(shutil.which("pandoc"), "pandoc is required for build integration")
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
                capture_output=True,
                check=False,
                timeout=30,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    @unittest.skipUnless(shutil.which("pandoc"), "pandoc is required for build integration")
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

    def test_project_lock_rejects_a_second_build_until_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            first = build.acquire_project_lock(project, timeout=0.1)
            try:
                with self.assertRaisesRegex(RuntimeError, "another build still holds"):
                    build.acquire_project_lock(project, timeout=0.01)
            finally:
                first.close()

            released = build.acquire_project_lock(project, timeout=0.1)
            released.close()

    def test_pandoc_highlight_flag_tracks_installed_cli(self) -> None:
        modern_help = mock.Mock(stdout="--syntax-highlighting=STYLE\n")
        legacy_help = mock.Mock(stdout="--no-highlight\n")

        with mock.patch.object(build, "run", return_value=modern_help):
            self.assertEqual(
                build.pandoc_no_highlight_arg("pandoc"),
                "--syntax-highlighting=none",
            )
        with mock.patch.object(build, "run", return_value=legacy_help):
            self.assertEqual(build.pandoc_no_highlight_arg("pandoc"), "--no-highlight")

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
                build.validate_output_path(output_dir, source, ".pdf", "--output-pdf")

    def test_pdf_and_output_pdf_may_be_the_same_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.md"
            source.write_text("# title\n", encoding="utf-8")
            pdf = root / "report.pdf"

            build.validate_generated_path_collisions(source, root / "latex", root / "report.tex", pdf, pdf)

    def test_subprocess_timeout_is_bounded_and_explained(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            build.run(
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
        self.assertIn(r"\caption[]{\textbf{方案}对比（续表）}", output)
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


if __name__ == "__main__":
    unittest.main()
