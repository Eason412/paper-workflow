from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SkillContractTests(unittest.TestCase):
    def test_skill_is_the_primary_oa_first_entrypoint(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("primary entry point", text)
        self.assertIn("OA first", text)
        self.assertIn("IEEE Xplore", text)
        self.assertIn("Wiley Online Library", text)
        self.assertIn("ScienceDirect", text)
        self.assertIn("Never ask for, read, type, or store", text)
        self.assertIn("oa_fetch.py", text)
        self.assertIn("~/Desktop/Papers", text)
        self.assertIn("manifest", text.lower())
        self.assertIn("Do not invent", text)
        self.assertIn("pending", text.lower())
        self.assertIn("citation_title", text)
        self.assertIn("renamed_from", text)
        self.assertIn("filename_error", text)
        self.assertIn("title_resolution_ambiguous", text)
        self.assertIn("publisher_title_mismatch", text)
        self.assertIn("publisher_title_unverifiable", text)

    def test_codex_install_payload_contains_entrypoint_metadata_and_backends(self):
        for relative in (
            "SKILL.md", "agents/openai.yaml", "oa_fetch.py",
            "institutional_fetch.py", "config.py", "manifest.py", "store.py",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)
        metadata = (ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
        self.assertIn("$oa-paper-fetch", metadata)
        self.assertIn("allow_implicit_invocation: true", metadata)

    def test_bilingual_readmes_share_the_core_user_contract(self):
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")

        self.assertIn("[简体中文](README.zh-CN.md)", english)
        self.assertIn("[English](README.md)", chinese)
        for token in (
            "0.5.0",
            "Python 3.10",
            "~/Desktop/Papers",
            "title_resolution_ambiguous",
            "publisher_title_mismatch",
            "publisher_title_unverifiable",
            "profile_missing_login_required",
            "login_refresh_required",
            "institutional_cap_reached",
            "0.85",
            "0.93",
            "oa_fetch_pending.csv",
            "AGENTS.md",
            "SKILL.md",
        ):
            self.assertIn(token, english)
            self.assertIn(token, chinese)
        self.assertNotIn("Python 3.9", english)
        self.assertNotIn("Python 3.9", chinese)

        def bash_blocks(text):
            blocks = re.findall(r"```bash\n(.*?)\n```", text, flags=re.S)
            return [
                tuple(
                    line.rstrip()
                    for line in block.splitlines()
                    if line.strip() and not line.lstrip().startswith("#")
                )
                for block in blocks
            ]

        self.assertEqual(bash_blocks(english), bash_blocks(chinese))

    def test_maintenance_manual_links_point_to_existing_sources(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        links = re.findall(r"\]\(([^)]+)\)", agents)
        self.assertIn("SKILL.md", links)
        self.assertIn("tests/test_title_resolution.py", links)
        for link in links:
            if not link.startswith(("https://", "http://")):
                self.assertTrue((ROOT / link.split("#", 1)[0]).exists(), link)


if __name__ == "__main__":
    unittest.main()
