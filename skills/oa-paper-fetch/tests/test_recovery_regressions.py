"""Offline regression coverage for batch identity and durable resume boundaries."""
import json
import sys
import unittest
from contextlib import nullcontext, redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import institutional_fetch
import manifest
import oa_fetch
import store
from test_institutional_boundaries import GuardablePage


class RecoveryRegressionTests(unittest.TestCase):
    def test_ids_stay_unique_across_explicit_suffix_and_default_collisions(self):
        for ids in (["a", "a", "a-2"], ["a", "a-2", "a"],
                    [None, "row1", "row1-2"], ["row2", None, "row2-2"]):
            with self.subTest(ids=ids):
                rows = [{"id": item_id, "title": "Same exact title"} for item_id in ids]
                records = manifest.normalize_items(rows)
                self.assertEqual(len({item["id"] for item in records}), len(rows))
                self.assertEqual(len({item["canonical_id"] for item in records}), len(rows))
                self.assertEqual(records, manifest.normalize_items(rows))
                self.assertEqual([item["manifest_status"] for item in records], ["ready"] * 3)

    def test_invalid_state_fails_before_fetch_and_preserves_original_bytes(self):
        bad_payloads = [b"not json", b"\xff", b"[]"]
        bad_payloads.extend(json.dumps({"version": version, "records": {}}).encode()
                            for version in (2, "1", True, None))
        bad_payloads.extend(json.dumps({"records": value}).encode()
                            for value in (None, [], 7, {"doi:10.1000/test": "bad"},
                                          {"doi:10.1000/test": []}))
        for field, value in (("input_ids", "row1"), ("input_ids", [None]),
                             ("runs", {}), ("runs", [1]), ("meta", [])):
            bad_payloads.append(json.dumps({"records": {
                "doi:10.1000/test": {field: value}}}).encode())
        for raw in bad_payloads:
            with self.subTest(raw=raw), TemporaryDirectory() as tmp:
                out = Path(tmp)
                state_path = out / store.STATE_FILENAME
                state_path.write_bytes(raw)
                stderr = StringIO()
                with (
                    mock.patch.object(sys, "argv", ["oa_fetch.py", "--doi", "10.1000/test",
                                                   "--out", tmp, "--config", str(out / "config.json")]),
                    mock.patch.object(oa_fetch, "resolve_item") as resolve,
                    redirect_stdout(StringIO()), redirect_stderr(stderr),
                ):
                    self.assertEqual(oa_fetch.main(), 4)
                resolve.assert_not_called()
                self.assertEqual(state_path.read_bytes(), raw)
                self.assertIn("state", stderr.getvalue())

    def test_legacy_state_without_optional_record_fields_remains_usable(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            path = out / store.STATE_FILENAME
            path.write_text(json.dumps({"records": {"doi:10.1000/test": {
                "file": "legacy.pdf", "status": "downloaded"}}}))
            state = store.load_state(out)
            self.assertEqual(store.recorded_pdf_path(out, state, "doi:10.1000/test"),
                             out / "legacy.pdf")
            store.record_result(state, {"id": "row1", "canonical_id": "doi:10.1000/test"},
                                {"success": True, "status": "exists", "meta": {}})
            self.assertEqual(state["records"]["doi:10.1000/test"]["input_ids"], ["row1"])
            self.assertEqual(len(state["records"]["doi:10.1000/test"]["runs"]), 1)

    def test_title_and_url_identity_blocks_do_not_enter_institutional_retry(self):
        for status in ("ambiguous", "unresolved"):
            with self.subTest(status=status), TemporaryDirectory() as tmp:
                out = Path(tmp)
                batch = out / "input.csv"
                batch.write_text("id,title,doi,url\nref-1,Exact source title,,"
                                 "https://ieeexplore.ieee.org/document/123\n")
                evidence = {"status": status, "reason": "fixture_identity_evidence",
                            "candidates": [{"title": "Candidate", "doi": "10.1000/other"}]}
                stdout = StringIO()
                with (
                    mock.patch.object(sys, "argv", ["oa_fetch.py", "--batch", str(batch),
                                                   "--out", tmp, "--institutional",
                                                   "--config", str(out / "config.json")]),
                    mock.patch.object(oa_fetch, "resolve_title_identity", return_value=evidence),
                    mock.patch.object(institutional_fetch, "profile_available", return_value=True),
                    mock.patch.object(institutional_fetch, "fetch_batch") as fetch,
                    mock.patch.object(oa_fetch, "download_pdf") as download,
                    redirect_stdout(stdout), redirect_stderr(StringIO()),
                ):
                    self.assertEqual(oa_fetch.main(), 1)
                fetch.assert_not_called()
                download.assert_not_called()
                result = json.loads(stdout.getvalue())["results"][0]
                self.assertEqual(result["error"], f"title_resolution_{status}")
                self.assertEqual(result["title_resolution"], evidence)
                self.assertNotIn("institutional", result)
                self.assertEqual(result["status"], "pending" if status == "ambiguous" else "failed")

    def test_real_institutional_batch_keeps_main_stdout_json(self):
        class BlockedPage(GuardablePage):
            url = "https://ieeexplore.ieee.org/document/123"

            def goto(self, *args, **kwargs):
                return SimpleNamespace(status=403)

            def close(self):
                pass

        context = mock.Mock()
        context.new_page.side_effect = lambda: BlockedPage()
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            batch = out / "input.txt"
            batch.write_text("\n".join(f"10.1109/paper{i}" for i in range(5)))
            stdout, stderr = StringIO(), StringIO()
            with (
                mock.patch.object(sys, "argv", ["oa_fetch.py", "--batch", str(batch), "--out", tmp,
                                               "--institutional", "--max-institutional", "4",
                                               "--oa-delay", "0", "--config", str(out / "config.json")]),
                mock.patch.object(oa_fetch, "resolve_item", side_effect=lambda item, *args: {
                    "success": False, "error": "no_open_access_pdf_downloaded",
                    "meta": {"doi": item["doi"]}}),
                mock.patch.object(institutional_fetch, "profile_available", return_value=True),
                mock.patch.object(institutional_fetch, "_load_playwright", return_value=lambda: nullcontext(object())),
                mock.patch.object(institutional_fetch, "_launch", return_value=context),
                mock.patch.object(institutional_fetch.time, "sleep"),
                redirect_stdout(stdout), redirect_stderr(stderr),
            ):
                self.assertEqual(oa_fetch.main(), 1)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(len(payload["results"]), 5)
            self.assertIn("capped at 4", stderr.getvalue())
            self.assertIn("[institutional 1/4]", stderr.getvalue())
            self.assertIn("aborting: 3 blocks", stderr.getvalue())
            context.close.assert_called_once()

    def test_both_download_paths_and_resume_agree_on_signature_length(self):
        url = "https://ieeexplore.ieee.org/paper.pdf"
        for data in (b"%PDF", b"%PDF-", b"%PDF-1"):
            for source in ("oa", "institutional"):
                with self.subTest(data=data, source=source), TemporaryDirectory() as tmp:
                    target = Path(tmp) / "paper.pdf"
                    if source == "oa":
                        response = mock.MagicMock()
                        response.__enter__.return_value.read.return_value = data
                        opener = mock.Mock()
                        opener.open.return_value = response
                        with mock.patch.object(oa_fetch.urllib.request, "build_opener", return_value=opener):
                            ok, reason = oa_fetch.download_pdf(url, target, 5, False)
                    else:
                        response = SimpleNamespace(status=200, ok=True, url=url, body=lambda: data)
                        context = mock.Mock()
                        context.request.get.return_value = response
                        ok, reason = institutional_fetch._download(context, url, target, 5, publisher="ieee")
                    expected = len(data) > 5
                    self.assertEqual(ok, expected)
                    self.assertEqual(reason, "downloaded" if expected else "not_pdf")
                    self.assertEqual(target.exists(), expected)
                    self.assertEqual(store.verify_pdf(target), expected)


if __name__ == "__main__":
    unittest.main()
