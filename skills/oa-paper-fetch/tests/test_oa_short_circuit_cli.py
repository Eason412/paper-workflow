import json
import sys
import unittest
from offline_support import OfflineTestCase
from contextlib import redirect_stderr, redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import institutional_fetch  # noqa: E402
import oa_fetch  # noqa: E402
import store  # noqa: E402


class ShortCircuitCliTests(OfflineTestCase):
    DOI = "10.1000/short-circuit"
    PDF_URL = "https://example.org/paper.pdf"

    def run_cli(self, root, *extra, institutional=False):
        stdout = StringIO()
        argv = [
            "oa_fetch.py", "--doi", self.DOI,
            "--out", str(root / "out"),
            "--config", str(root / "isolated-config.json"),
            "--institutional" if institutional else "--oa-only",
            "--oa-delay", "0", *extra,
        ]
        with (
            mock.patch.object(sys, "argv", argv),
            redirect_stdout(stdout),
            redirect_stderr(StringIO()),
        ):
            code = oa_fetch.main()
        return code, json.loads(stdout.getvalue())

    def test_openalex_download_checkpoints_and_resumes_without_queries(self):
        metadata = {
            "doi": f"https://doi.org/{self.DOI}",
            "title": "Short Circuit Paper",
            "publication_year": 2026,
            "authorships": [{"author": {"display_name": "Alice Chen"}}],
            "best_oa_location": {"is_oa": True, "pdf_url": self.PDF_URL},
        }
        pdf = b"%PDF-1.7\noffline fixture"
        with (
            TemporaryDirectory() as tmp,
            mock.patch.object(oa_fetch, "request_json", return_value=metadata) as query,
            mock.patch.object(oa_fetch, "unpaywall_lookup") as unpaywall,
            mock.patch.object(oa_fetch, "semantic_scholar_lookup") as scholar,
            mock.patch.object(institutional_fetch, "fetch_batch") as institutional,
            mock.patch.object(oa_fetch.urllib.request, "build_opener") as opener,
        ):
            root = Path(tmp)
            opener.return_value.open.return_value = BytesIO(pdf)
            code, payload = self.run_cli(root)
            self.assertEqual(code, 0)
            result = payload["results"][0]
            self.assertEqual(result["status"], "downloaded")
            saved = Path(result["file"])
            self.assertTrue(saved.name.startswith("2026_Chen_Short_Circuit_Paper_"))
            self.assertEqual(saved.read_bytes(), pdf)
            self.assertEqual(result["target_file"], str(saved))
            state = store.load_state(root / "out")
            self.assertEqual(state["records"][f"doi:{self.DOI}"]["file"], saved.name)
            query.assert_called_once()
            self.assertIn("api.openalex.org/works/", query.call_args.args[0])
            opener.return_value.open.assert_called_once()
            self.assertEqual(opener.return_value.open.call_args.args[0].full_url, self.PDF_URL)

            query.reset_mock()
            opener.reset_mock()
            code, resumed = self.run_cli(root)
            self.assertEqual(code, 0)
            self.assertEqual(resumed["results"][0]["status"], "exists")
            self.assertEqual(resumed["results"][0]["file"], str(saved))
            self.assertEqual(list((root / "out").glob("*.pdf")), [saved])
            query.assert_not_called()
            opener.assert_not_called()
            unpaywall.assert_not_called()
            scholar.assert_not_called()
            institutional.assert_not_called()

    def test_dry_run_reports_all_sources_without_pdf_state_or_institutional(self):
        with (
            TemporaryDirectory() as tmp,
            mock.patch.object(oa_fetch, "openalex_lookup", return_value={
                "title": "Short Circuit Paper", "urls": [self.PDF_URL],
            }) as openalex,
            mock.patch.object(oa_fetch, "unpaywall_lookup", return_value={
                "urls": ["https://example.org/repository.pdf"],
            }) as unpaywall,
            mock.patch.object(oa_fetch, "semantic_scholar_lookup", return_value={
                "urls": ["https://example.org/author.pdf"],
            }) as scholar,
            mock.patch.object(oa_fetch.urllib.request, "build_opener") as opener,
            mock.patch.object(institutional_fetch, "fetch_batch") as institutional,
        ):
            root = Path(tmp)
            code, payload = self.run_cli(root, "--dry-run", institutional=True)
            self.assertEqual(code, 0)
            result = payload["results"][0]
            self.assertEqual(result["status"], "candidate")
            self.assertEqual(len(result["candidates"]), 3)
            for query in (openalex, unpaywall, scholar):
                query.assert_called_once()
            opener.assert_not_called()
            institutional.assert_not_called()
            out = root / "out"
            self.assertFalse(list(out.glob("*.pdf")))
            self.assertFalse((out / store.STATE_FILENAME).exists())
            self.assertFalse((out / "oa_fetch_pending.csv").exists())
            report = json.loads((out / "oa_fetch_results.json").read_text())
            self.assertEqual(report[0]["candidates"], result["candidates"])


if __name__ == "__main__":
    unittest.main()
