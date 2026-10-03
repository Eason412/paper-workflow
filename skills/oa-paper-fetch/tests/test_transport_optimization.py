"""Focused transport diagnostics for institutional publisher responses."""

from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from offline_support import OfflineTestCase
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import institutional_fetch  # noqa: E402


class _Response:
    def __init__(self, body, *, headers=None, url="https://www.sciencedirect.com/science/article/pii/S123/pdfft"):
        self.status = 200
        self.ok = True
        self.url = url
        self.headers = headers or {}
        self._body = body
        self.disposed = False

    def body(self):
        return self._body

    def dispose(self):
        self.disposed = True


class _Context:
    def __init__(self, response):
        self.request = mock.Mock(get=mock.Mock(return_value=response))


class TransportOptimizationTests(OfflineTestCase):
    def test_html_classifier_uses_content_type_and_safe_prefix_only(self):
        self.assertTrue(
            institutional_fetch._looks_like_html(
                b"access page", {"content-type": "text/html; charset=utf-8"}
            )
        )
        self.assertTrue(institutional_fetch._looks_like_html(b"  <!doctype html>"))
        self.assertFalse(
            institutional_fetch._looks_like_html(
                b"not a pdf but binary", {"content-type": "application/pdf"}
            )
        )

    def test_sciencedirect_html_pdf_response_reports_browser_download_required(self):
        response = _Response(
            b"<html><body>ViewPDF</body></html>",
            headers={"Content-Type": "text/html; charset=UTF-8"},
        )
        ctx = _Context(response)
        with TemporaryDirectory() as tmp:
            dest = Path(tmp) / "paper.pdf"
            result = institutional_fetch._download(
                ctx,
                response.url,
                dest,
                timeout=5,
                publisher="elsevier",
            )
            self.assertEqual(result, (False, "not_pdf_browser_download_required"))
            self.assertFalse(dest.exists())
        self.assertTrue(response.disposed)

    def test_login_html_still_takes_precedence_over_browser_diagnostic(self):
        response = _Response(
            b"<html><body>Sign in to continue</body></html>",
            headers={"content-type": "text/html"},
        )
        ctx = _Context(response)
        with TemporaryDirectory() as tmp:
            result = institutional_fetch._download(
                ctx,
                response.url,
                Path(tmp) / "paper.pdf",
                timeout=5,
                publisher="elsevier",
            )
        self.assertEqual(result, (False, "not_pdf_login_or_challenge"))
        self.assertTrue(response.disposed)

    def test_other_publishers_keep_generic_non_pdf_reason(self):
        response = _Response(
            b"<html><body>Server error</body></html>",
            headers={"content-type": "text/html"},
            url="https://ieeexplore.ieee.org/stampPDF/final.pdf",
        )
        ctx = _Context(response)
        with TemporaryDirectory() as tmp:
            result = institutional_fetch._download(
                ctx,
                response.url,
                Path(tmp) / "paper.pdf",
                timeout=5,
                publisher="ieee",
            )
        self.assertEqual(result, (False, "not_pdf"))
        self.assertTrue(response.disposed)

    def test_browser_handoff_does_not_count_as_a_login_block(self):
        self.assertFalse(
            institutional_fetch._counts_as_block(
                "not_pdf_browser_download_required"
            )
        )
        self.assertTrue(
            institutional_fetch._counts_as_block("not_pdf_login_or_challenge")
        )
        self.assertTrue(
            institutional_fetch._counts_as_block("landing_login_or_challenge")
        )

    def test_batch_continues_handoffs_until_a_real_block_stops_it(self):
        class PlaywrightManager:
            def __enter__(self):
                return object()

            def __exit__(self, exc_type, exc, tb):
                return False

        class Context:
            def new_page(self):
                return mock.Mock()

            def close(self):
                return None

        with TemporaryDirectory() as tmp:
            items = [
                {
                    "idx": index,
                    "doi": f"10.1109/{index}",
                    "dest": str(Path(tmp) / f"paper-{index}.pdf"),
                }
                for index in range(6)
            ]
            handoff = {
                "success": False,
                "error": "not_pdf_browser_download_required",
            }
            login_block = {
                "success": False,
                "error": "not_pdf_login_or_challenge",
            }
            with (
                mock.patch.object(
                    institutional_fetch,
                    "_load_playwright",
                    return_value=lambda: PlaywrightManager(),
                ),
                mock.patch.object(institutional_fetch, "_launch", return_value=Context()),
                mock.patch.object(
                    institutional_fetch,
                    "_fetch_page_pdf",
                    side_effect=[
                        ({**handoff, "idx": 0}, False),
                        ({**handoff, "idx": 1}, False),
                        ({**login_block, "idx": 2}, True),
                        ({**login_block, "idx": 3}, True),
                        ({**login_block, "idx": 4}, True),
                    ],
                ) as fetch_page,
                mock.patch.object(institutional_fetch.time, "sleep"),
            ):
                results = institutional_fetch.fetch_batch(
                    items,
                    profile_dir=str(Path(tmp) / "profile"),
                    delay=4,
                    jitter=0,
                )

        self.assertEqual(fetch_page.call_count, 5)
        self.assertEqual(
            [result["error"] for result in results[:3]],
            [
                "not_pdf_browser_download_required",
                "not_pdf_browser_download_required",
                "not_pdf_login_or_challenge",
            ],
        )
        self.assertEqual(
            [result["error"] for result in results[3:]],
            [
                "not_pdf_login_or_challenge",
                "not_pdf_login_or_challenge",
                "aborted_after_repeated_blocks",
            ],
        )


if __name__ == "__main__":
    unittest.main()
