#!/usr/bin/env python3
"""Prepare a Chinese Markdown course report for the ctexart template."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__:
    from . import report_assets, report_citations, report_metadata
else:
    import report_assets
    import report_citations
    import report_metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("latex"))
    parser.add_argument("--course", default="")
    parser.add_argument("--student-name", default="")
    parser.add_argument("--student-id", default="")
    parser.add_argument("--logo", default="")
    parser.add_argument("--no-cover", action="store_true")
    parser.add_argument("--allow-slide-draft", action="store_true", help="已废弃，无效果")
    parser.add_argument("--keep-repeated-citations", action="store_true")
    return parser.parse_args()


def scan_prepared_body(
    args: argparse.Namespace, body_lines: list[str], slide_draft: dict[str, object], warnings: list[str],
) -> tuple[str, dict[str, object]]:
    prepared_body = "\n".join(body_lines).strip() + "\n"
    prepared_body, citation_dedup = report_citations.dedupe_repeated_citations(prepared_body, args.keep_repeated_citations)
    prepared_body = prepared_body.strip() + "\n"
    qa = report_assets.scan_body(prepared_body, args.source.parent)
    qa["citation_dedup"] = citation_dedup
    qa["probable_slide_draft"] = slide_draft
    warnings.extend(report_assets.qa_warnings(qa, slide_draft))
    return prepared_body, qa


def prepare_report(args: argparse.Namespace) -> tuple[str, dict[str, str], dict[str, object]]:
    source = args.source
    front_matter_raw, body_text = report_metadata.parse_front_matter(source.read_text(encoding="utf-8"))
    front_matter = report_metadata.map_front_matter(front_matter_raw)
    lines = body_text.splitlines()
    slide_draft = report_metadata.detect_slide_draft(lines)
    no_abs_lines, metadata, warnings = report_metadata.extract_abstract(lines)
    body_lines, title, body_warnings = report_metadata.prepare_body(no_abs_lines)
    warnings.extend(body_warnings)
    if not title:
        title = front_matter.get("title") or source.stem
    cover = report_metadata.cover_metadata(
        front_matter, metadata, title,
        course=args.course, student_name=args.student_name, student_id=args.student_id, logo=args.logo, no_cover=args.no_cover,
    )
    for key in ("keywords_zh", "keywords_en"):
        count = report_metadata.keyword_count(metadata.get(key, ""))
        if count > 5:
            warnings.append(f"{key} 有 {count} 个关键词，超过最多 5 个的默认限制。")

    prepared_body, qa = scan_prepared_body(args, body_lines, slide_draft, warnings)
    logo_path, logo_exists, logo_inside_project = (
        report_assets.resolve_project_asset(args.logo, source.parent)
        if args.logo
        else ("", False, False)
    )
    if args.logo and not logo_exists:
        warnings.append(f"logo 文件不存在：{args.logo}")
    if args.logo and logo_exists and not logo_inside_project:
        warnings.append("logo 路径不是项目内相对路径；请改用项目目录内的相对路径，或通过 build_course_report.py 传入。")
    cover.update({"logo_exists": logo_exists, "logo_inside_project": logo_inside_project})
    return prepared_body, metadata, {"title": title, "cover": cover, "qa": qa, "warnings": warnings}


def write_prepared_report(
    out_dir: Path, prepared_body: str, metadata: dict[str, str], report: dict[str, object],
) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    body_path = out_dir / "report_body.md"
    metadata_path = out_dir / "metadata.yaml"
    report_path = out_dir / "prepare_report.json"
    body_path.write_text(prepared_body, encoding="utf-8")
    metadata_text = "---\n" + "".join(report_metadata.yaml_block(k, metadata.get(k, "")) for k in sorted(metadata)) + "---\n"
    metadata_path.write_text(metadata_text, encoding="utf-8")
    report_path.write_text(
        json.dumps(
            {"body": str(body_path), "metadata": str(metadata_path), **report},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    warnings = report["warnings"]
    return {
        "body": str(body_path),
        "metadata": str(metadata_path),
        "report": str(report_path),
        "warning_count": len(warnings),
        "warnings": warnings,
    }


def main() -> int:
    args = parse_args()
    prepared_body, metadata, report = prepare_report(args)
    summary = write_prepared_report(args.out_dir, prepared_body, metadata, report)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"prepare_course_report failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
