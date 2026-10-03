"""Run OA acquisition, verified-file reuse, and durable per-paper checkpoints."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import fetch_results
import oa_resolution
import paper_metadata
import store


class OaBatch:
    """Keep serial OA scheduling and checkpoint errors local to one run."""

    def __init__(self, args, settings: dict, records: list[dict], state: dict):
        self.args = args
        self.settings = settings
        self.records = records
        self.state = state
        self.out_dir = settings["output_dir"]
        self.results: list[dict | None] = [None] * len(records)
        self.transport_error = False
        self.network_items = 0

    def run(self) -> tuple[list[dict | None], bool]:
        for record in self.records:
            index = record["input_index"]
            migration_source: Path | None = None
            if record["manifest_status"] == "invalid":
                self.results[index] = {
                    "success": False,
                    "status": "failed",
                    "error": f"invalid_manifest_row:{record['validation_error']}",
                    "meta": fetch_results._item_meta(record),
                    "canonical_id": None,
                    "input_id": record["id"],
                }
                continue
            if record["manifest_status"] == "duplicate":
                continue

            if self.args.format == "text":
                label = (
                    record.get("title") or record.get("doi")
                    or record.get("url") or record.get("id")
                )
                print(f"[{index + 1}/{len(self.records)}] {label}", file=sys.stderr)

            recorded_path = store.recorded_pdf_path(
                self.out_dir, self.state, record["canonical_id"]
            )
            if (
                not self.args.overwrite
                and not self.args.dry_run
                and recorded_path
                and store.verify_pdf(recorded_path)
            ):
                result = self.resume_record(record, recorded_path)
                migration_source = self.migrate_result(result, record)
            else:
                result = self.fetch_record(record, recorded_path)
                if recorded_path and result.get("success") and not self.args.dry_run:
                    migration_source = self.migrate_result(result, record)
            self.checkpoint_record(record, result, migration_source)
        return self.results, self.transport_error

    def wait_for_network_item(self) -> None:
        if self.network_items and self.settings["oa_delay"]:
            time.sleep(self.settings["oa_delay"])
        self.network_items += 1

    def resume_record(self, record: dict, recorded_path: Path) -> dict:
        previous = (self.state.get("records") or {}).get(record["canonical_id"]) or {}
        meta = paper_metadata._merge_metadata(
            fetch_results._item_meta(record), previous.get("meta")
        )
        result = {
            "success": True,
            "status": "exists",
            "source": previous.get("source"),
            "file": str(recorded_path),
            "pdf_url": None,
            "meta": meta,
            "attempts": [],
            "sources": [],
        }
        if previous.get("naming_version") != store.NAMING_VERSION:
            self.wait_for_network_item()
            try:
                preview = oa_resolution.resolve_item(
                    dict(record),
                    self.out_dir,
                    self.settings["timeout"],
                    False,
                    True,
                )
                result["meta"] = paper_metadata._merge_metadata(meta, preview.get("meta"))
                result["sources"] = preview.get("sources") or []
            except Exception as exc:
                result["filename_metadata_error"] = f"{type(exc).__name__}: {exc}"
        result = fetch_results._decorate_result(result, record, self.out_dir)
        return result

    def fetch_record(self, record: dict, recorded_path: Path | None) -> dict:
        self.wait_for_network_item()
        work_item = dict(record)
        if recorded_path:
            work_item["_state_filename"] = recorded_path.name
        try:
            result = oa_resolution.resolve_item(
                work_item,
                self.out_dir,
                self.settings["timeout"],
                self.args.overwrite,
                self.args.dry_run,
            )
            result = fetch_results._decorate_result(result, record, self.out_dir)
        except Exception as exc:
            self.transport_error = True
            result = fetch_results._decorate_result(
                {
                    "success": False,
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                    "meta": fetch_results._item_meta(record),
                },
                record,
                self.out_dir,
            )
        return result

    def migrate_result(self, result: dict, record: dict) -> Path | None:
        try:
            return fetch_results._prepare_filename_migration(result, record, self.out_dir)
        except OSError as exc:
            self.transport_error = True
            result["filename_error"] = f"{type(exc).__name__}: {exc}"
            result["target_file"] = result.get("file")
        return None

    def checkpoint_record(self, record: dict, result: dict, migration_source: Path | None) -> None:
        index = record["input_index"]
        fetch_results._enrich_manifest_title(record, result)
        self.results[index] = result
        if not self.args.dry_run:
            try:
                fetch_results._persist_result(
                    self.state,
                    self.out_dir,
                    record,
                    result,
                    migration_source=migration_source,
                )
            except OSError as exc:
                self.transport_error = True
                print(f"Could not save run state: {exc}", file=sys.stderr)
        if self.args.format == "text":
            print(("  OK " if result.get("success") else "  MISS ") +
                  str(result.get("file") or result.get("error") or result.get("pdf_url")),
                  file=sys.stderr)
