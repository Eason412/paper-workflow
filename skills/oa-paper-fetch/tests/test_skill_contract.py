"""Installation structure and local navigation, without prose contracts."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SkillContractTests(unittest.TestCase):
    def test_install_payload_and_entrypoint_metadata(self):
        for relative in (
            "SKILL.md", "agents/openai.yaml", "oa_fetch.py",
            "institutional_fetch.py", "config.py", "manifest.py", "store.py",
            "pyproject.toml", "uv.lock", "references/browser-workflow.md",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = text.split("---", 2)[1]
        self.assertRegex(frontmatter, r"(?m)^name:\s*oa-paper-fetch\s*$")
        self.assertRegex(frontmatter, r"(?m)^description:\s*\S")
        metadata = (ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
        for key in ("display_name", "short_description", "default_prompt"):
            self.assertRegex(metadata, rf"(?m)^\s+{key}:\s*\S")
        self.assertIn("$oa-paper-fetch", metadata)

    def test_local_document_links_resolve(self):
        documents = [ROOT / name for name in ("SKILL.md", "AGENTS.md", "README.md", "README.zh-CN.md")]
        documents.extend((ROOT / "references").glob("*.md"))
        for document in documents:
            for link in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
                if link.startswith(("https://", "http://", "#")):
                    continue
                with self.subTest(document=document.name, link=link):
                    self.assertTrue((document.parent / link.split("#", 1)[0]).exists())


if __name__ == "__main__":
    unittest.main()
