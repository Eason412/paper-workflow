#!/usr/bin/env python3
"""Legal open-access paper PDF CLI, preferences, and batch orchestration."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import config as paper_config
import fetch_inputs
import fetch_results
import institutional_retry
import manifest as manifest_tools
import oa_batch
import oa_transport
import store

DEFAULT_PROFILE_DIR = paper_config.DEFAULT_PROFILE_DIR


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.version:
        print(oa_transport.VERSION)
        return 0
    settings, cli_values, config_path = load_run_settings(parser, args)
    exit_code = handle_preferences_and_login(parser, args, settings, cli_values, config_path)
    if exit_code is not None:
        return exit_code
    records, exit_code = read_input_records(parser, args)
    if exit_code is not None:
        return exit_code
    ready = manifest_tools.fetchable(records)
    if args.manifest_out:
        return write_manifest_preflight(args, records, ready)
    out_dir = settings["output_dir"]
    state = prepare_run_state(out_dir, records)
    if state is None:
        return 4
    results, transport_error = oa_batch.OaBatch(args, settings, records, state).run()
    if settings["institutional"] and not args.dry_run:
        retry = institutional_retry.InstitutionalRetry(args, settings, ready, results, state)
        exit_code = retry.run()
        if exit_code is not None:
            return exit_code
        transport_error = transport_error or retry.transport_error
    fetch_results.fill_duplicate_results(records, ready, results)
    return finish_run(args, out_dir, state, records, ready, results, transport_error)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download legal open-access academic PDFs.")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--doi")
    group.add_argument("--title")
    group.add_argument("--url")
    group.add_argument("--batch", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--timeout", type=int, default=None)
    parser.add_argument("--oa-delay", type=float, default=None,
                        help="seconds between OA paper items (0 to 60; default: 1)")
    parser.add_argument("--config", type=Path, default=paper_config.DEFAULT_CONFIG_PATH,
                        help=f"preferences file (default: {paper_config.DEFAULT_CONFIG_PATH})")
    parser.add_argument("--save-config", action="store_true",
                        help="save explicitly provided non-sensitive preferences")
    parser.add_argument("--manifest-out", type=Path,
                        help="normalize and deduplicate --batch to CSV without network access")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--version", action="store_true")

    inst = parser.add_argument_group("institutional (SSO) fetch")
    inst_mode = inst.add_mutually_exclusive_group()
    inst_mode.add_argument("--institutional", dest="institutional", action="store_true",
                           help="after OA fails, retry via a logged-in browser session (IEEE/Wiley/Elsevier)")
    inst_mode.add_argument("--oa-only", dest="institutional", action="store_false",
                           help="disable a configured institutional fallback for this run")
    parser.set_defaults(institutional=None)
    inst.add_argument("--institutional-login", action="store_true",
                      help="open a browser to sign in via institutional SSO once, then exit")
    inst.add_argument("--browser-profile", type=Path, default=None,
                      help=f"persistent browser profile dir (default: {DEFAULT_PROFILE_DIR})")
    inst.add_argument("--inst-delay", type=float, default=None,
                      help="base seconds between institutional requests (minimum: 4)")
    inst.add_argument("--inst-jitter", type=float, default=None,
                      help="added random delay in seconds (0 to 10)")
    inst.add_argument("--max-institutional", type=int, default=None,
                      help="institutional attempts per run (1 to 30)")
    inst.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="reuse an established institutional profile without a visible window",
    )
    return parser


def _config_cli_values(args) -> dict:
    return {
        "output_dir": args.out,
        "oa_delay": args.oa_delay,
        "timeout": args.timeout,
        "institutional": args.institutional,
        "browser_profile": args.browser_profile,
        "inst_delay": args.inst_delay,
        "inst_jitter": args.inst_jitter,
        "max_institutional": args.max_institutional,
        "headless": args.headless,
    }


def load_run_settings(parser, args):
    config_path = args.config.expanduser()
    cli_values = _config_cli_values(args)
    try:
        file_values = paper_config.load_config(config_path)
        settings = paper_config.resolve_config(file_values, cli_values)
    except paper_config.ConfigError as exc:
        parser.error(str(exc))

    from institutional_fetch import validate_institutional_options
    try:
        validate_institutional_options(
            settings["inst_delay"],
            settings["inst_jitter"],
            settings["max_institutional"],
        )
    except ValueError as exc:
        parser.error(str(exc))
    return settings, cli_values, config_path


def handle_preferences_and_login(parser, args, settings, cli_values, config_path):
    provided_config = {
        key: value for key, value in cli_values.items() if value is not None
    }
    if args.save_config:
        if not provided_config:
            parser.error("--save-config requires at least one preference option")
        try:
            saved = paper_config.save_config(config_path, provided_config)
        except (paper_config.ConfigError, OSError) as exc:
            print(f"Could not save config {config_path}: {exc}", file=sys.stderr)
            return 4
        has_input = bool(args.doi or args.title or args.url or args.batch)
        if not has_input and not args.institutional_login:
            print(json.dumps({"ok": True, "config": str(config_path), "saved": saved},
                             ensure_ascii=False, indent=2))
            return 0
        print(f"[config] saved non-sensitive preferences to {config_path}", file=sys.stderr)

    if args.institutional_login:
        if args.headless is True:
            parser.error("--institutional-login cannot be combined with --headless")
        from institutional_fetch import login
        return login(str(settings["browser_profile"]))
    return None


def read_input_records(parser, args):
    if not (args.doi or args.title or args.url or args.batch):
        parser.error(
            "one of --doi/--title/--url/--batch is required "
            "(or use --institutional-login/--save-config)"
        )
    if args.manifest_out and not args.batch:
        parser.error("--manifest-out requires --batch")

    if args.batch:
        batch_path = args.batch.expanduser()
        if not batch_path.exists():
            print(f"Batch file not found: {batch_path}", file=sys.stderr)
            return None, 3
        try:
            items = fetch_inputs.parse_batch(batch_path)
        except (OSError, UnicodeError, csv.Error) as exc:
            print(f"Could not read batch file {batch_path}: {exc}", file=sys.stderr)
            return None, 4
    else:
        items = [{"doi": args.doi, "title": args.title, "url": args.url, "id": None}]
    if not items:
        print("No papers found in input.", file=sys.stderr)
        return None, 3

    records = manifest_tools.normalize_items(items)
    return records, None


def write_manifest_preflight(args, records, ready):
    try:
        target = manifest_tools.write_manifest_csv(records, args.manifest_out.expanduser())
    except OSError as exc:
        print(f"Could not write manifest: {exc}", file=sys.stderr)
        return 4
    manifest_summary = {
        "total": len(records),
        "ready": len(ready),
        "duplicate": sum(r["manifest_status"] == "duplicate" for r in records),
        "invalid": sum(r["manifest_status"] == "invalid" for r in records),
    }
    print(json.dumps({"ok": bool(ready), "summary": manifest_summary,
                      "manifest": str(target), "records": records},
                     ensure_ascii=False, indent=2))
    return 0 if ready else 3


def prepare_run_state(out_dir: Path, records: list[dict]) -> dict | None:
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest_tools.write_manifest_csv(
            records, out_dir / "oa_fetch_manifest.csv"
        )
    except OSError as exc:
        print(f"Could not prepare output directory or manifest: {exc}", file=sys.stderr)
        return None

    try:
        state = store.load_state(out_dir)
    except (OSError, ValueError) as exc:
        print(f"Could not load run state: {exc}", file=sys.stderr)
        return None
    state["manifest_sha256"] = manifest_tools.manifest_sha256(records)
    return state


def finish_run(args, out_dir, state, records, ready, results, transport_error):
    if any(result is None for result in results):
        print("Internal error: not every manifest row received a result.", file=sys.stderr)
        return 4
    final_results = [result for result in results if result is not None]
    transport_error = transport_error or any(
        fetch_results._result_has_transport_failure(result) for result in final_results
    )
    pending = [
        (record, final_results[record["input_index"]])
        for record in records
        if final_results[record["input_index"]].get("status") == "pending"
    ]
    try:
        normalized_manifest_path = manifest_tools.write_manifest_csv(
            records, out_dir / "oa_fetch_manifest.csv"
        )
        state["manifest_sha256"] = manifest_tools.manifest_sha256(records)
        if not args.dry_run:
            pending_path = store.write_pending_csv(out_dir, pending)
            store.save_state(out_dir, state)
        fetch_results.write_reports(final_results, out_dir)
    except OSError as exc:
        print(f"Could not write result reports: {exc}", file=sys.stderr)
        return 4

    summary = fetch_results._summary(final_results, len(ready))
    ok = summary["failed"] == 0 and summary["pending"] == 0
    reports = {
        "json": str(out_dir / "oa_fetch_results.json"),
        "csv": str(out_dir / "oa_fetch_results.csv"),
        "manifest": str(normalized_manifest_path),
    }
    if not args.dry_run:
        reports["state"] = str(out_dir / store.STATE_FILENAME)
    if pending and not args.dry_run:
        reports["pending"] = str(pending_path)
    payload = {"ok": ok, "summary": summary, "results": final_results, "reports": reports}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if transport_error:
        return 4
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
