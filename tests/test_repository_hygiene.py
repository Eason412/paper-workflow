"""Repository-level ignore rules without creating actual documents or sessions."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RepositoryHygieneTests(unittest.TestCase):
    def test_runtime_artifacts_are_ignored_but_skill_sources_are_not(self):
        artifacts = [
            "output/paper.pdf", "output/oa_fetch_state.json",
            "oa_fetch_manifest.csv", "oa_fetch_pending.csv",
            "output/oa_fetch_results.json", "output/oa_fetch_results.csv",
            "profile/Default/Cookies", ".oa-paper-fetch/profile/Preferences",
            "course_report.tex", "latex/report_body.md", "report.aux",
            "output/paper.pdf.part-example",
            "skills/oa-paper-fetch/output/paper.pdf",
            "skills/oa-paper-fetch/profile/Default/Cookies",
            "skills/md-course-report-to-pdf/latex/metadata.yaml",
        ]
        sources = [
            "README.md", "AGENTS.md",
            "skills/oa-paper-fetch/SKILL.md",
            "skills/oa-paper-fetch/oa_fetch.py",
            "skills/oa-paper-fetch/tests/test_store_resume.py",
            "skills/md-course-report-to-pdf/SKILL.md",
            "skills/md-course-report-to-pdf/assets/templates/ctexart-course-report.tex",
            "skills/md-course-report-to-pdf/examples/minimal_report.md",
            "skills/md-course-report-to-pdf/references/njust-thesis-format.doc",
        ]
        with tempfile.TemporaryDirectory() as raw:
            sandbox = Path(raw)
            subprocess.run(["git", "init", "-q", str(sandbox)], check=True, capture_output=True)
            for relative in (
                ".gitignore", "skills/oa-paper-fetch/.gitignore",
                "skills/md-course-report-to-pdf/.gitignore",
            ):
                target = sandbox / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            checked = subprocess.run(
                ["git", "-C", str(sandbox), "-c", "core.excludesFile=",
                 "check-ignore", "--no-index", "--stdin", "-z"],
                input="\0".join(artifacts + sources) + "\0", text=True,
                capture_output=True, check=False,
            )
            self.assertEqual(checked.returncode, 0, checked.stderr)
            ignored = set(checked.stdout.split("\0")) - {""}
            self.assertEqual(ignored, set(artifacts))


if __name__ == "__main__":
    unittest.main()
