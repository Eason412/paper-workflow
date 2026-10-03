"""Resolve one paper's identity and try OA candidates serially or in preview mode."""
from __future__ import annotations

import time
import urllib.parse
from pathlib import Path

import oa_sources
import oa_transport
import paper_metadata
import title_identity


def direct_candidates(url: str | None) -> list[str]:
    if not url:
        return []
    arxiv_pdf = paper_metadata.extract_arxiv_pdf(url)
    if arxiv_pdf:
        return [arxiv_pdf]
    parsed = urllib.parse.urlparse(url)
    if parsed.path.lower().endswith(".pdf"):
        return [url]
    return []


def resolve_item(item: dict, out_dir: Path, timeout: int, overwrite: bool, dry_run: bool) -> dict:
    resolver = ItemResolver(item, out_dir, timeout, overwrite, dry_run)
    resolver.collect_direct_candidates()
    resolver.resolve_arxiv_metadata()
    resolver.resolve_title_metadata()
    resolver.prepare_destination()
    if resolver.title_resolution and resolver.title_resolution.get("status") != "confirmed":
        return resolver.blocked_identity_result()
    if dry_run:
        return resolver.preview_result()
    return resolver.download_candidates()


class ItemResolver:
    """Carry one paper's evidence and destination through serial OA steps."""

    def __init__(self, item: dict, out_dir: Path, timeout: int, overwrite: bool, dry_run: bool):
        self.item = item
        self.out_dir = out_dir
        self.timeout = timeout
        self.overwrite = overwrite
        self.dry_run = dry_run
        self.original_title = self.item.get("title") or ""
        self.original_url = self.item.get("url") or ""
        self.doi = (
            self.item.get("doi")
            or paper_metadata.extract_doi(self.original_url)
            or paper_metadata.extract_doi(self.original_title)
        )
        self.title = self.original_title
        self.sources = []
        self.meta: dict = {
            "title": self.title,
            "doi": self.doi,
            "source_id": self.item.get("id"),
            "url": self.original_url,
        }
        self.candidates: list[tuple[str, str, dict]] = []
        self.title_resolution = None

    def collect_direct_candidates(self) -> None:
        for u in direct_candidates(self.original_url):
            self.candidates.append(("direct", u, {}))
        for u in direct_candidates(self.title):
            self.candidates.append(("direct", u, {}))
        self.arxiv_id = (
            paper_metadata.extract_arxiv_id(self.original_url)
            or paper_metadata.extract_arxiv_id(self.title)
            or paper_metadata.extract_arxiv_id(self.doi)
        )
        arxiv_pdf = paper_metadata.extract_arxiv_pdf(self.arxiv_id)
        if arxiv_pdf:
            self.candidates.append(("arxiv", arxiv_pdf, {}))

    def resolve_arxiv_metadata(self) -> None:
        if self.arxiv_id:
            ax = oa_sources.arxiv_id_lookup(self.arxiv_id, self.timeout)
            self.sources.append({
                "source": "arxiv_id",
                "result": bool(ax),
                "score": ax.get("score") if ax else None,
            })
            if ax:
                for key in ("title", "year", "first_author"):
                    if ax.get(key):
                        self.meta[key] = ax[key]
                if ax.get("doi") and not self.meta.get("doi"):
                    self.meta["doi"] = ax["doi"]
                for u in ax.get("urls") or []:
                    self.candidates.append(("arxiv_id", u, ax))
            self.doi = self.doi or self.meta.get("doi")
            self.title = self.title or self.meta.get("title") or ""

    def resolve_title_metadata(self) -> None:
        if not self.arxiv_id and not self.doi and self.title:
            self.title_resolution = title_identity.resolve_title_identity(
                self.title, self.timeout
            )
            self.sources.extend(self.title_resolution.get("lookups") or [])
            self.sources.append({
                "source": "title_resolution",
                "result": self.title_resolution.get("status") == "confirmed",
                "status": self.title_resolution.get("status"),
                "reason": self.title_resolution.get("reason"),
                "selected_doi": self.title_resolution.get("selected_doi"),
            })
            if self.title_resolution.get("status") == "confirmed":
                self.doi = self.title_resolution.get("selected_doi")
                accepted_alias_dois = set(
                    self.title_resolution.get("accepted_alias_dois") or []
                )
                selected = self.title_resolution.get("selected") or {}
                for key in ("title", "year", "first_author"):
                    if selected.get(key):
                        self.meta[key] = selected[key]
                self.meta["doi"] = self.doi
                self.title = self.meta.get("title") or self.title
                for found in self.title_resolution.get("candidates") or []:
                    if (
                        found.get("doi") != self.doi
                        and found.get("doi") not in accepted_alias_dois
                    ):
                        continue
                    for url in found.get("urls") or []:
                        self.candidates.append(
                            (found.get("source") or "title_resolution", url, found)
                        )

    def prepare_destination(self) -> None:
        self.canonical_id = self.item.get("canonical_id") or (
            f"doi:{self.doi}"
            if self.doi
            else f"legacy:{self.title or self.original_url or self.item.get('id') or 'paper'}"
        )
        self.state_filename = self.item.get("_state_filename")

        self.dest = self.refresh_destination()
        self.identity = {
            "canonical_id": self.canonical_id,
            "input_id": self.item.get("id"),
            "possible_title_duplicate_of": self.item.get("possible_title_duplicate_of"),
            "target_file": str(self.dest),
        }

    def blocked_identity_result(self) -> dict:
        ambiguous = self.title_resolution.get("status") == "ambiguous"
        error = (
            "title_resolution_ambiguous"
            if ambiguous
            else "title_resolution_unresolved"
        )
        blocked = {
            "success": False,
            "status": "pending" if ambiguous else "failed",
            "source": None,
            "pdf_url": None,
            "file": None,
            "meta": self.meta,
            "sources": self.sources,
            "attempts": [],
            "error": error,
            "title_resolution": self.title_resolution,
            **self.identity,
        }
        if ambiguous:
            blocked["pending_reason"] = error
        if self.dry_run:
            blocked["dry_run"] = True
        return blocked

    def iter_source_metadata(self):
        if not self.arxiv_id:
            for source_name, lookup in (
                ("openalex", lambda: oa_sources.openalex_lookup(
                    self.doi, self.title, self.timeout
                )),
                ("unpaywall", lambda: oa_sources.unpaywall_lookup(self.doi, self.timeout) if self.doi else {}),
                ("semantic_scholar", lambda: oa_sources.semantic_scholar_lookup(
                    self.doi, self.timeout
                ) if self.doi else {}),
            ):
                found = lookup()
                self.sources.append({
                    "source": source_name,
                    "result": bool(found),
                    "skipped": found.get("skipped") if isinstance(found, dict) else None,
                })
                if not found:
                    continue
                for key in ("title", "year", "first_author", "doi"):
                    if found.get(key) and not self.meta.get(key):
                        self.meta[key] = found[key]
                yield source_name, found

    def preview_result(self) -> dict:
        # Dry-run retains the complete candidate list and source evidence.
        for source_name, found in self.iter_source_metadata():
            for url in found.get("urls") or []:
                self.candidates.append((source_name, url, found))
        self.seen = set()
        self.candidates = [
            (s, u, m)
            for s, u, m in self.candidates
            if not (u in self.seen or self.seen.add(u))
        ]
        self.dest = self.refresh_destination()
        self.identity["target_file"] = str(self.dest)
        public_candidates = [
            (source, url, metadata)
            for source, url, metadata in self.candidates
            if oa_transport.safe_url(url)
        ]
        return {
            "success": bool(public_candidates),
            "status": "candidate" if public_candidates else "failed",
            "dry_run": True,
            "file": str(self.dest) if public_candidates else None,
            "pdf_url": public_candidates[0][1] if public_candidates else None,
            "source": public_candidates[0][0] if public_candidates else None,
            "meta": self.meta,
            "sources": self.sources,
            "candidates": [
                {"source": source, "url": url}
                for source, url, _ in public_candidates
            ],
            "title_resolution": self.title_resolution,
            **self.identity,
        }

    def download_candidates(self) -> dict:
        # Query one OA index and try its URLs before querying the next index.
        # Stop after success, preserving source-serial acquisition.
        self.seen = set()
        self.attempts = []

        for source, url, _ in self.candidates:
            result = self.attempt_candidate(source, url)
            if result:
                return result

        for source_name, found in self.iter_source_metadata():
            self.dest = self.refresh_destination()
            self.identity["target_file"] = str(self.dest)
            for url in found.get("urls") or []:
                result = self.attempt_candidate(source_name, url)
                if result:
                    return result

        return {
            "success": False,
            "status": "failed",
            "source": None,
            "pdf_url": None,
            "file": None,
            "meta": self.meta,
            "sources": self.sources,
            "attempts": self.attempts,
            "error": "no_open_access_pdf_downloaded",
            "title_resolution": self.title_resolution,
            **self.identity,
        }

    def refresh_destination(self) -> Path:
        if self.state_filename and Path(self.state_filename).name == self.state_filename:
            filename = self.state_filename
        else:
            filename = paper_metadata.metadata_filename(
                self.meta,
                paper_metadata.filename_fallback(self.item, self.meta),
                self.canonical_id,
            )
        return self.out_dir / filename

    def attempt_candidate(self, source: str, url: str) -> dict | None:
        if not url or url in self.seen:
            return None
        self.seen.add(url)
        ok, reason = oa_transport.download_pdf(
            url, self.dest, self.timeout, self.overwrite
        )
        self.attempts.append({"source": source, "url": url, "result": reason})
        if ok:
            return {
                "success": True,
                "status": "exists" if reason == "exists" else "downloaded",
                "source": source,
                "pdf_url": url,
                "file": str(self.dest),
                "meta": self.meta,
                "sources": self.sources,
                "attempts": self.attempts,
                "title_resolution": self.title_resolution,
                **self.identity,
            }
        time.sleep(0.5)
        return None
