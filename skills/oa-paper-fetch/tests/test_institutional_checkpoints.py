"""Institutional checkpoint failures and response lifetimes, without live access."""
from contextlib import nullcontext, redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import institutional_fetch as inst
import oa_fetch
import store


class CheckpointTests(unittest.TestCase):
    def test_failed_checkpoint_stops_batch_and_preserves_original_pdf(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "papers.txt"
            source.write_text("10.1109/first\n10.1109/second\n", encoding="utf-8")
            output = root / "output"
            ctx = mock.Mock()
            fetched = []

            def fetch(ctx, page, item, base, landing, dest, doi, timeout):
                fetched.append(doi)
                store.atomic_write_bytes(dest, b"%PDF-1.7 fixture")
                return ({**base, "success": True, "source": "institutional", "file": str(dest),
                         "meta": {"doi": doi, "title": "Verified title", "year": "2024", "first_author": "Author"}}, False)

            save = store.save_state
            def failing_save(out, state):
                if any(r.get("status") == "downloaded" for r in state["records"].values()):
                    raise OSError("simulated checkpoint failure")
                return save(out, state)

            argv = ["oa_fetch.py", "--batch", str(source), "--out", str(output),
                    "--config", str(root / "preferences.json"), "--institutional", "--oa-delay", "0"]
            with (mock.patch.object(sys, "argv", argv),
                  mock.patch.object(oa_fetch, "resolve_item", side_effect=lambda item, *a: {
                      "success": False, "error": "no_open_access_pdf_downloaded", "meta": {"doi": item["doi"]}}),
                  mock.patch.object(inst, "profile_available", return_value=True),
                  mock.patch.object(inst, "_load_playwright", return_value=lambda: nullcontext(object())),
                  mock.patch.object(inst, "_launch", return_value=ctx),
                  mock.patch.object(inst, "_fetch_page_pdf", side_effect=fetch),
                  mock.patch.object(inst.time, "sleep"),
                  mock.patch.object(store, "save_state", side_effect=failing_save),
                  redirect_stdout(StringIO()), redirect_stderr(StringIO())):
                self.assertEqual(oa_fetch.main(), 4)
            self.assertEqual(fetched, ["10.1109/first"])
            ctx.close.assert_called_once()
            pdfs = list(output.glob("*.pdf"))
            self.assertEqual(len(pdfs), 1)
            self.assertTrue(store.verify_pdf(pdfs[0]))
            self.assertNotIn("2024_Author", pdfs[0].name)
            saved = json.loads((output / store.STATE_FILENAME).read_text(encoding="utf-8"))
            self.assertEqual(saved["records"]["doi:10.1109/first"]["status"], "failed")

    def test_each_response_is_disposed_once_on_all_exit_paths(self):
        url = "https://ieeexplore.ieee.org/paper.pdf"
        def response(status=200, headers=None, final=url, error=None, body=b"%PDF-1.7 fixture"):
            return SimpleNamespace(status=status, ok=200 <= status < 300, headers=headers or {},
                                   url=final, body=mock.Mock(return_value=body, side_effect=error),
                                   dispose=mock.Mock())
        cases = [
            ([response()], "downloaded"),
            ([response(status=403)], "http_403"),
            ([response(status=302)], "http_302"),
            ([response(status=302, headers={"location": "https://example.org/other"})], "unsafe_pdf_url"),
            ([response(final="https://example.org/other")], "unsafe_pdf_url"),
            ([response(error=OSError("read failed"))], "read_OSError"),
            ([response(body=b"html")], "not_pdf"),
            ([response(body=b"%PDF-" + b"x" * 30)], "too_large"),
            ([response(status=302, headers={"location": "/next.pdf"}), response()], "downloaded"),
            ([response(status=302, headers={"location": "/next.pdf"}) for _ in range(6)], "too_many_redirects"),
        ]
        for responses, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as raw:
                ctx = SimpleNamespace(request=SimpleNamespace(get=mock.Mock(side_effect=responses)))
                with mock.patch.object(inst, "MAX_PDF_BYTES", 25):
                    _, reason = inst._download(ctx, url, Path(raw) / "paper.pdf", 5, publisher="ieee")
                self.assertEqual(reason, expected)
                for item in responses:
                    item.dispose.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
