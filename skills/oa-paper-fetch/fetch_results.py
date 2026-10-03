"""Decorate results, migrate filenames, persist checkpoints, and write reports."""
from __future__ import annotations

import copy
from pathlib import Path

import paper_metadata
import store


def write_reports(results: list[dict], out_dir: Path) -> None:
    store.atomic_write_json(out_dir / "oa_fetch_results.json", results)
    fields = ["success", "source", "file", "pdf_url", "doi", "title",
              "expected_title",
              "year", "first_author",
              "source_id", "error", "institutional_error", "status",
              "canonical_id", "input_id", "duplicate_of", "pending_reason",
              "title_resolution_status", "title_resolution_reason", "resolved_doi",
              "citation_title", "publisher_title_match", "publisher_title_score",
              "renamed_from", "filename_error", "filename_metadata_error"]
    rows = []
    for result in results:
        meta = result.get("meta") or {}
        title_resolution = result.get("title_resolution") or {}
        rows.append({
                "success": result.get("success"),
                "source": result.get("source"),
                "file": result.get("file"),
                "pdf_url": result.get("pdf_url"),
                "doi": meta.get("doi"),
                "title": meta.get("title"),
                "expected_title": meta.get("expected_title"),
                "year": meta.get("year"),
                "first_author": meta.get("first_author"),
                "source_id": meta.get("source_id"),
                "error": result.get("error"),
                "institutional_error": (result.get("institutional") or {}).get("error"),
                "status": result.get("status"),
                "canonical_id": result.get("canonical_id"),
                "input_id": result.get("input_id") or meta.get("source_id"),
                "duplicate_of": result.get("duplicate_of"),
                "pending_reason": result.get("pending_reason"),
                "title_resolution_status": title_resolution.get("status"),
                "title_resolution_reason": title_resolution.get("reason"),
                "resolved_doi": title_resolution.get("selected_doi"),
                "citation_title": meta.get("citation_title"),
                "publisher_title_match": meta.get("publisher_title_match"),
                "publisher_title_score": meta.get("publisher_title_score"),
                "renamed_from": result.get("renamed_from"),
                "filename_error": result.get("filename_error"),
                "filename_metadata_error": result.get("filename_metadata_error"),
        })
    store.atomic_write_csv(out_dir / "oa_fetch_results.csv", fields, rows)


def _item_meta(item: dict) -> dict:
    return {
        "title": item.get("title"),
        "doi": item.get("doi"),
        "year": item.get("year"),
        "first_author": item.get("first_author"),
        "source_id": item.get("id"),
        "url": item.get("url"),
    }


def _decorate_result(result: dict, item: dict, out_dir: Path) -> dict:
    result = dict(result)
    result["meta"] = paper_metadata._merge_metadata(result.get("meta"), _item_meta(item))
    result.setdefault("canonical_id", item.get("canonical_id"))
    result.setdefault("input_id", item.get("id"))
    result.setdefault(
        "possible_title_duplicate_of", item.get("possible_title_duplicate_of")
    )
    if result.get("success"):
        result.setdefault("status", "downloaded")
    else:
        result.setdefault("status", "failed")
    if not result.get("target_file"):
        meta = result.get("meta") or {}
        filename = paper_metadata.metadata_filename(
            meta,
            paper_metadata.filename_fallback(item, meta),
            item.get("canonical_id"),
        )
        result["target_file"] = str(out_dir / filename)
    return result


def _prepare_filename_migration(
    result: dict, item: dict, out_dir: Path
) -> Path | None:
    """Link a verified PDF to its metadata-derived name without overwriting."""
    if not result.get("success") or not result.get("file"):
        return None
    source = Path(result["file"])
    if not store.verify_pdf(source):
        return None
    meta = result.get("meta") or {}
    filename = paper_metadata.metadata_filename(
        meta,
        paper_metadata.filename_fallback(item, meta),
        item.get("canonical_id"),
    )
    target = Path(out_dir) / filename
    if source == target:
        result["target_file"] = str(target)
        return None
    store.prepare_pdf_migration(source, target)
    result["target_file"] = str(target)
    result["renamed_from"] = source.name
    result["file"] = str(target)
    return source


def _persist_result(
    state: dict,
    out_dir: Path,
    item: dict,
    result: dict,
    migration_source: Path | None = None,
) -> None:
    canonical_id = item.get("canonical_id")
    records = state.setdefault("records", {})
    had_previous = canonical_id in records
    previous = copy.deepcopy(records.get(canonical_id)) if had_previous else None
    target = Path(result["file"]) if migration_source and result.get("file") else None
    try:
        store.record_result(state, item, result)
        store.save_state(out_dir, state)
    except OSError:
        if not had_previous:
            records.pop(canonical_id, None)
        else:
            records[canonical_id] = previous
        if migration_source and target:
            store.rollback_pdf_migration(migration_source, target)
            result["file"] = str(migration_source)
            result["target_file"] = str(migration_source)
            result.pop("renamed_from", None)
        raise
    if migration_source and target:
        store.finish_pdf_migration(migration_source, target)


def _enrich_manifest_title(item: dict, result: dict) -> None:
    title = (result.get("meta") or {}).get("title")
    if title and not item.get("title"):
        item["title"] = title


def _summary(results: list[dict], unique_total: int) -> dict:
    statuses = ("candidate", "downloaded", "exists", "duplicate", "failed", "pending")
    summary = {
        "total": len(results),
        "unique": unique_total,
        "succeeded": sum(1 for result in results if result.get("success")),
    }
    for status in statuses:
        summary[status] = sum(1 for result in results if result.get("status") == status)
    return summary


def _result_has_transport_failure(result: dict) -> bool:
    if result.get("success"):
        return False

    def is_transport_reason(value) -> bool:
        return isinstance(value, str) and (
            value == "landing_guard_error"
            or value.startswith(("network_", "read_"))
        )

    for attempt in result.get("attempts") or []:
        if isinstance(attempt, dict) and is_transport_reason(attempt.get("result")):
            return True
    institutional = result.get("institutional")
    return bool(
        isinstance(institutional, dict)
        and is_transport_reason(institutional.get("error"))
    )


def fill_duplicate_results(records: list[dict], ready: list[dict], results: list):
    winners = {
        record["canonical_id"]: results[record["input_index"]]
        for record in ready
        if results[record["input_index"]] is not None
    }
    for record in records:
        if record["manifest_status"] != "duplicate":
            continue
        winner = winners.get(record["duplicate_of"]) or {}
        results[record["input_index"]] = {
            "success": bool(winner.get("success")),
            "status": "duplicate",
            "duplicate_of": record["duplicate_of"],
            "canonical_id": record["canonical_id"],
            "input_id": record["id"],
            "source": winner.get("source"),
            "file": winner.get("file"),
            "pdf_url": winner.get("pdf_url"),
            "meta": paper_metadata._merge_metadata(_item_meta(record), winner.get("meta")),
            "error": None if winner.get("success") else "duplicate_source_unresolved",
        }
