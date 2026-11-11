"""Structural, link-integrity, and fact-check script tests for paper-writing-zh."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "paper-writing-zh"
COMPARE = SKILL_DIR / "scripts" / "compare_facts.py"
MD_LINK = re.compile(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]*)?\)")


class PaperWritingZhTests(unittest.TestCase):
    def test_skill_md_stays_compact_and_links_resolve(self):
        skill_md = SKILL_DIR / "SKILL.md"
        lines = skill_md.read_text(encoding="utf-8").splitlines()
        self.assertLessEqual(len(lines), 85, "SKILL.md should stay concise (<= 85 lines)")

        md_files = [skill_md] + sorted((SKILL_DIR / "references").glob("*.md"))
        for md in md_files:
            text = md.read_text(encoding="utf-8")
            for target in MD_LINK.findall(text):
                if target.startswith(("http://", "https://", "file://")):
                    continue
                resolved = (md.parent / target).resolve()
                if resolved.name == "examples.md" and not resolved.exists():
                    continue  # examples.md is local-only / gitignored
                self.assertTrue(resolved.exists(), f"Broken link {target!r} in {md.name}")

    def test_compare_facts_catches_bad_fold_and_bilingual_diff(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            old_p = tmp / "old.md"
            new_p = tmp / "new.md"
            base_doc = "## 摘要\n误差降低了 50%，精度达 98.5%。\n\n## Abstract\nError drops by 50% and accuracy reaches 98.5%.\n"
            old_p.write_text(base_doc, encoding="utf-8")
            new_p.write_text(base_doc, encoding="utf-8")

            ok = subprocess.run([sys.executable, str(COMPARE), str(old_p), str(new_p)],
                                capture_output=True, text=True, check=False)
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)

            # Introduce "降低了 2 倍" and bilingual number drift (keep same global number set by having 96.2% elsewhere)
            bad_doc = "## 摘要\n误差降低了 2 倍，精度达 98.5%。\n\n## Abstract\nError drops and accuracy reaches 50%.\n\n## 正文\n原值为 2 倍。\n"
            old_p.write_text("## 摘要\n误差小，精度达 98.5% 或 50%。\n\n## Abstract\nAccuracy reaches 98.5% or 50%.\n\n## 正文\n原值为 2 倍。\n", encoding="utf-8")
            new_p.write_text(bad_doc, encoding="utf-8")

            bad = subprocess.run([sys.executable, str(COMPARE), str(old_p), str(new_p)],
                                 capture_output=True, text=True, check=False)
            self.assertEqual(bad.returncode, 1)
            self.assertIn("倍数病句： 降低了 2 倍", bad.stdout)
            self.assertIn("双语摘要数字提示：", bad.stdout)


if __name__ == "__main__":
    unittest.main()
