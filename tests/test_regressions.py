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


class BuildRegressionTests(unittest.TestCase):
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
