import os
import sys
import unittest
from offline_support import OfflineTestCase
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import oa_resolution
import oa_sources
import oa_transport
import paper_metadata
import oa_fetch  # noqa: E402


class OaShortCircuitTests(OfflineTestCase):
    def _item(self, *, url=None, title=None, state_filename=None):
        item = {
            "id": "row-1",
            "title": title,
            "doi": "10.1000/example",
            "url": url,
            "canonical_id": "doi:10.1000/example",
        }
        if state_filename:
            item["_state_filename"] = state_filename
        return item

    def test_direct_candidate_success_skips_all_metadata_sources(self):
        direct_url = "https://repository.example/direct.pdf"
        with TemporaryDirectory() as tmp:
            with (
                mock.patch.object(
                    oa_transport, "download_pdf", return_value=(True, "downloaded")
                ) as download_pdf,
                mock.patch.object(oa_sources, "openalex_lookup") as openalex,
                mock.patch.object(oa_sources, "unpaywall_lookup") as unpaywall,
                mock.patch.object(oa_sources, "semantic_scholar_lookup") as semantic,
            ):
                result = oa_resolution.resolve_item(
                    self._item(url=direct_url), Path(tmp), 5, False, False
                )

        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "direct")
        self.assertEqual(result["pdf_url"], direct_url)
        self.assertEqual([call.args[0] for call in download_pdf.call_args_list], [direct_url])
        openalex.assert_not_called()
        unpaywall.assert_not_called()
        semantic.assert_not_called()

    def test_openalex_success_skips_unpaywall_and_semantic_scholar(self):
        openalex_url = "https://repository.example/openalex.pdf"
        found = {
            "title": "Metadata Supplied Title",
            "year": 2024,
            "first_author": "Author",
            "urls": [openalex_url],
        }
        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            with (
                mock.patch.object(oa_sources, "openalex_lookup", return_value=found) as openalex,
                mock.patch.object(oa_sources, "unpaywall_lookup") as unpaywall,
                mock.patch.object(oa_sources, "semantic_scholar_lookup") as semantic,
                mock.patch.object(
                    oa_transport, "download_pdf", return_value=(True, "downloaded")
                ) as download_pdf,
            ):
                result = oa_resolution.resolve_item(
                    self._item(), out_dir, 5, False, False
                )

        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "openalex")
        self.assertEqual(result["meta"]["title"], found["title"])
        expected_file = out_dir / paper_metadata.metadata_filename(
            result["meta"], found["title"], "doi:10.1000/example"
        )
        self.assertEqual(Path(result["file"]), expected_file)
        self.assertEqual(download_pdf.call_args.args[0], openalex_url)
        self.assertEqual(Path(download_pdf.call_args.args[1]), expected_file)
        openalex.assert_called_once_with("10.1000/example", "", 5)
        unpaywall.assert_not_called()
        semantic.assert_not_called()

    def test_failed_openalex_urls_continue_to_unpaywall_once_per_url(self):
        shared_url = "https://repository.example/shared.pdf"
        openalex_url = "https://repository.example/openalex.pdf"
        unpaywall_url = "https://repository.example/unpaywall.pdf"
        openalex_found = {"urls": [shared_url, openalex_url]}
        unpaywall_found = {"urls": [shared_url, unpaywall_url]}

        def download(url, *_args):
            if url == unpaywall_url:
                return True, "downloaded"
            return False, "not_pdf"

        with TemporaryDirectory() as tmp:
            with (
                mock.patch.object(
                    oa_sources, "openalex_lookup", return_value=openalex_found
                ) as openalex,
                mock.patch.object(
                    oa_sources, "unpaywall_lookup", return_value=unpaywall_found
                ) as unpaywall,
                mock.patch.object(oa_sources, "semantic_scholar_lookup") as semantic,
                mock.patch.object(oa_transport, "download_pdf", side_effect=download) as download_pdf,
                mock.patch.object(oa_resolution.time, "sleep"),
            ):
                result = oa_resolution.resolve_item(
                    self._item(), Path(tmp), 5, False, False
                )

        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "unpaywall")
        self.assertEqual(
            [attempt["url"] for attempt in result["attempts"]],
            [shared_url, openalex_url, unpaywall_url],
        )
        self.assertEqual(
            [call.args[0] for call in download_pdf.call_args_list],
            [shared_url, openalex_url, unpaywall_url],
        )
        self.assertEqual(
            [source["source"] for source in result["sources"]],
            ["openalex", "unpaywall"],
        )
        openalex.assert_called_once()
        unpaywall.assert_called_once()
        semantic.assert_not_called()

    def test_all_oa_sources_can_fail_before_semantic_scholar_succeeds(self):
        openalex_url = "https://repository.example/openalex-miss.pdf"
        unpaywall_url = "https://repository.example/unpaywall-miss.pdf"
        semantic_url = "https://repository.example/semantic.pdf"

        def download(url, *_args):
            return (url == semantic_url, "downloaded" if url == semantic_url else "not_pdf")

        with TemporaryDirectory() as tmp:
            with (
                mock.patch.object(
                    oa_sources, "openalex_lookup", return_value={"urls": [openalex_url]}
                ) as openalex,
                mock.patch.object(
                    oa_sources, "unpaywall_lookup", return_value={"urls": [unpaywall_url]}
                ) as unpaywall,
                mock.patch.object(
                    oa_sources,
                    "semantic_scholar_lookup",
                    return_value={"urls": [semantic_url]},
                ) as semantic,
                mock.patch.object(oa_transport, "download_pdf", side_effect=download) as download_pdf,
                mock.patch.object(oa_resolution.time, "sleep"),
            ):
                result = oa_resolution.resolve_item(
                    self._item(), Path(tmp), 5, False, False
                )

        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "semantic_scholar")
        self.assertEqual(
            [call.args[0] for call in download_pdf.call_args_list],
            [openalex_url, unpaywall_url, semantic_url],
        )
        self.assertEqual(
            [attempt["result"] for attempt in result["attempts"]],
            ["not_pdf", "not_pdf", "downloaded"],
        )
        self.assertEqual(
            [source["source"] for source in result["sources"]],
            ["openalex", "unpaywall", "semantic_scholar"],
        )
        openalex.assert_called_once()
        unpaywall.assert_called_once()
        semantic.assert_called_once()

    def test_dry_run_queries_all_sources_deduplicates_and_never_downloads(self):
        shared_url = "https://repository.example/shared.pdf"
        openalex_url = "https://repository.example/openalex.pdf"
        unpaywall_url = "https://repository.example/unpaywall.pdf"
        semantic_url = "https://repository.example/semantic.pdf"
        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            with (
                mock.patch.object(
                    oa_sources,
                    "openalex_lookup",
                    return_value={"title": "Dry Run Title", "urls": [shared_url, openalex_url]},
                ) as openalex,
                mock.patch.object(
                    oa_sources,
                    "unpaywall_lookup",
                    return_value={"urls": [shared_url, unpaywall_url]},
                ) as unpaywall,
                mock.patch.object(
                    oa_sources,
                    "semantic_scholar_lookup",
                    return_value={"urls": [unpaywall_url, semantic_url]},
                ) as semantic,
                mock.patch.object(oa_transport, "download_pdf") as download_pdf,
            ):
                result = oa_resolution.resolve_item(
                    self._item(), out_dir, 5, False, True
                )
            self.assertFalse(out_dir.exists())

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "candidate")
        self.assertEqual(
            [candidate["url"] for candidate in result["candidates"]],
            [shared_url, openalex_url, unpaywall_url, semantic_url],
        )
        self.assertEqual(
            [source["source"] for source in result["sources"]],
            ["openalex", "unpaywall", "semantic_scholar"],
        )
        self.assertEqual(result["meta"]["title"], "Dry Run Title")
        download_pdf.assert_not_called()
        openalex.assert_called_once()
        unpaywall.assert_called_once()
        semantic.assert_called_once()

    def test_existing_state_filename_survives_metadata_enrichment(self):
        state_filename = "recorded-name.pdf"
        found = {
            "title": "New Publisher Metadata",
            "year": 2023,
            "first_author": "Lee",
            "urls": ["https://repository.example/state.pdf"],
        }
        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            with (
                mock.patch.object(oa_sources, "openalex_lookup", return_value=found),
                mock.patch.object(oa_sources, "unpaywall_lookup") as unpaywall,
                mock.patch.object(oa_sources, "semantic_scholar_lookup") as semantic,
                mock.patch.object(
                    oa_transport, "download_pdf", return_value=(True, "exists")
                ) as download_pdf,
            ):
                result = oa_resolution.resolve_item(
                    self._item(state_filename=state_filename),
                    out_dir,
                    5,
                    False,
                    False,
                )

        expected_file = out_dir / state_filename
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "exists")
        self.assertEqual(Path(result["file"]), expected_file)
        self.assertEqual(Path(result["target_file"]), expected_file)
        self.assertEqual(Path(download_pdf.call_args.args[1]), expected_file)
        self.assertEqual(result["meta"]["title"], found["title"])
        unpaywall.assert_not_called()
        semantic.assert_not_called()

    def test_openalex_closed_work_exposes_no_oa_locations(self):
        closed = {
            "doi": "https://doi.org/10.1000/example",
            "title": "Closed Work",
            "open_access": {
                "is_oa": False,
                "oa_url": "https://publisher.example/closed.pdf",
            },
            "best_oa_location": {
                "is_oa": False,
                "pdf_url": "https://repository.example/closed.pdf",
                "landing_page_url": "https://repository.example/closed",
            },
            "primary_location": {
                "pdf_url": "https://publisher.example/paywall.pdf",
                "landing_page_url": "https://publisher.example/paywall",
            },
        }
        with mock.patch.object(oa_transport, "request_json", return_value=closed) as request_json:
            result = oa_sources.openalex_lookup("10.1000/example", None, 5)

        self.assertEqual(result["urls"], [])
        request_json.assert_called_once()

    def test_openalex_prioritizes_pdf_urls_across_locations(self):
        response = {
            "doi": "https://doi.org/10.1000/example",
            "title": "Open Work",
            "open_access": {
                "is_oa": True,
                "oa_url": "https://repository.example/oa-landing",
            },
            "best_oa_location": {
                "is_oa": True,
                "pdf_url": "https://repository.example/best.pdf",
                "landing_page_url": "https://repository.example/best",
            },
            "primary_location": {
                "is_oa": True,
                "pdf_url": "https://publisher.example/primary.pdf",
                "landing_page_url": "https://publisher.example/primary",
            },
        }
        with mock.patch.object(oa_transport, "request_json", return_value=response):
            result = oa_sources.openalex_lookup("10.1000/example", None, 5)

        self.assertEqual(
            result["urls"],
            [
                "https://repository.example/best.pdf",
                "https://publisher.example/primary.pdf",
                "https://repository.example/best",
                "https://publisher.example/primary",
                "https://repository.example/oa-landing",
            ],
        )

    def test_unpaywall_prioritizes_pdf_urls_across_locations(self):
        response = {
            "title": "Repository Work",
            "year": 2022,
            "best_oa_location": {
                "url_for_pdf": "https://repository.example/best.pdf",
                "url": "https://repository.example/best",
            },
            "oa_locations": [
                {
                    "url_for_pdf": "https://repository.example/second.pdf",
                    "url": "https://repository.example/second",
                },
                {"url": "https://repository.example/landing-only"},
            ],
        }
        with (
            mock.patch.dict(os.environ, {"UNPAYWALL_EMAIL": "test@example.org"}),
            mock.patch.object(oa_transport, "request_json", return_value=response),
        ):
            result = oa_sources.unpaywall_lookup("10.1000/example", 5)

        self.assertEqual(
            result["urls"],
            [
                "https://repository.example/best.pdf",
                "https://repository.example/second.pdf",
                "https://repository.example/best",
                "https://repository.example/second",
                "https://repository.example/landing-only",
            ],
        )


if __name__ == "__main__":
    unittest.main()
