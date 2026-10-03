"""Select institutional fallback items and checkpoint streamed browser results."""
from __future__ import annotations

import sys
from pathlib import Path

import fetch_results
import paper_metadata

pending_login_errors = {
    "profile_missing_login_required",
    "not_pdf_login_or_challenge",
    "landing_login_or_challenge",
    "aborted_after_repeated_blocks",
}


def build_retry_items(ready: list[dict], results: list, out_dir: Path) -> list[dict]:
    retry = []
    for record in ready:
        index = record["input_index"]
        result = results[index]
        if result is None or result.get("success"):
            continue
        if result.get("error") in {
            "title_resolution_ambiguous", "title_resolution_unresolved",
        }:
            continue
        meta = result.get("meta") or {}
        doi = meta.get("doi") or record.get("doi")
        url = record.get("url")
        if not (doi or url):
            continue
        title = meta.get("title") or record.get("title")
        target_file = result.get("target_file")
        if not target_file:
            filename = paper_metadata.metadata_filename(
                meta,
                title or doi or record.get("id") or "paper",
                record.get("canonical_id"),
            )
            target_file = str(out_dir / filename)
        retry.append({
            "idx": index,
            "id": record.get("id"),
            "canonical_id": record.get("canonical_id"),
            "doi": doi,
            "title": title,
            "expected_title": record.get("title"),
            "year": meta.get("year"),
            "first_author": meta.get("first_author"),
            "url": url,
            "dest": target_file,
        })
    return retry


class InstitutionalRetry:
    """Merge browser results once and persist each institutional checkpoint."""

    def __init__(self, args, settings: dict, ready: list[dict], results: list, state: dict):
        self.args = args
        self.settings = settings
        self.results = results
        self.state = state
        self.out_dir = settings["output_dir"]
        self.retry = build_retry_items(ready, results, self.out_dir)
        self.records_by_index = {record["input_index"]: record for record in ready}
        self.handled_indices = set()
        self.transport_error = False

    def run(self) -> int | None:
        if not self.retry:
            return None
        import institutional_fetch
        try:
            if not institutional_fetch.profile_available(self.settings["browser_profile"]):
                inst_results = [
                    {
                        "idx": item["idx"],
                        "success": False,
                        "error": "profile_missing_login_required",
                    }
                    for item in self.retry
                ]
                print("[institutional] login profile is missing; run --institutional-login",
                      file=sys.stderr)
                for inst_result in inst_results:
                    self.handle_result(inst_result)
            else:
                print(f"[institutional] retrying {len(self.retry)} item(s) via logged-in browser",
                      file=sys.stderr)
                inst_results = institutional_fetch.fetch_batch(
                    self.retry,
                    profile_dir=str(self.settings["browser_profile"]),
                    delay=self.settings["inst_delay"],
                    jitter=self.settings["inst_jitter"],
                    headless=self.settings["headless"],
                    max_items=self.settings["max_institutional"],
                    timeout=self.settings["timeout"],
                    overwrite=self.args.overwrite,
                    on_item_result=self.handle_result,
                )
                for inst_result in (inst_results or []):
                    idx = inst_result.get("idx")
                    if idx not in self.handled_indices:
                        self.handle_result(inst_result)
        except OSError as exc:
            print(f"Institutional batch stopped: {exc}", file=sys.stderr)
            return 4
        return None

    def handle_result(self, inst_result: dict) -> None:
        index = inst_result.get("idx")
        if index is None or not (0 <= index < len(self.results)):
            return
        if index in self.handled_indices:
            return
        self.handled_indices.add(index)
        prev = self.results[index]
        if prev is None:
            return
        self.apply_result_status(prev, inst_result)
        record = self.records_by_index.get(index)
        if record:
            fetch_results._enrich_manifest_title(record, prev)
            migration_source = None
            if inst_result.get("success"):
                migration_source = self.migrate_result(prev, record)
            # 检查点失败由批次边界处理；停止后续请求，保留原 PDF 与已落盘状态。
            fetch_results._persist_result(
                self.state,
                self.out_dir,
                record,
                prev,
                migration_source=migration_source,
            )

    def apply_result_status(self, prev: dict, inst_result: dict) -> None:
        prev["meta"] = paper_metadata._merge_metadata(
            inst_result.get("meta"), prev.get("meta")
        )
        error = inst_result.get("error")
        prev["institutional"] = {
            "success": inst_result.get("success"),
            "error": error,
            "pdf_url": inst_result.get("pdf_url"),
        }
        if inst_result.get("success"):
            prev.update({
                "success": True,
                "status": "exists" if inst_result.get("note") == "exists" else "downloaded",
                "source": inst_result.get("source", "institutional"),
                "pdf_url": inst_result.get("pdf_url"),
                "file": inst_result.get("file"),
                "error": None,
                "pending_reason": None,
            })
        elif error == "institutional_cap_reached":
            prev.update(status="pending", pending_reason=error)
        elif error == "profile_missing_login_required":
            prev.update(status="pending", pending_reason=error)
        elif error in {
            "publisher_title_mismatch",
            "publisher_title_unverifiable",
        }:
            prev.update(status="pending", pending_reason=error, error=error)
        elif error in pending_login_errors or str(error or "").startswith("http_4"):
            prev.update(status="pending", pending_reason="login_refresh_required")
        else:
            prev.update(status="failed")

    def migrate_result(self, result: dict, record: dict) -> Path | None:
        try:
            return fetch_results._prepare_filename_migration(result, record, self.out_dir)
        except OSError as exc:
            self.transport_error = True
            result["filename_error"] = f"{type(exc).__name__}: {exc}"
            result["target_file"] = result.get("file")
        return None
