"""Read CSV, Markdown tables, and line-based paper manifests."""
from __future__ import annotations

import csv
import re
from pathlib import Path

import paper_metadata


def strip_cell(cell: str) -> str:
    return cell.strip().strip("`").strip()


def parse_markdown_table(path: Path) -> list[dict]:
    rows = []
    headers = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if "|" not in line:
            continue
        parts = [strip_cell(p) for p in line.strip().strip("|").split("|")]
        if not parts or all(re.fullmatch(r"-+", p.replace(":", "").strip()) for p in parts):
            continue
        if headers is None:
            headers = [p.lower() for p in parts]
            continue
        if len(parts) != len(headers):
            continue
        rec = dict(zip(headers, parts))
        title = rec.get("题名") or rec.get("title") or rec.get("paper") or rec.get("name")
        url = rec.get("链接") or rec.get("url") or rec.get("link")
        doi = rec.get("doi") or paper_metadata.extract_doi(url or "") or paper_metadata.extract_doi(title or "")
        ident = rec.get("标记") or rec.get("id") or rec.get("key")
        if title or url or doi:
            rows.append({"id": ident, "title": title, "url": url, "doi": doi})
    return rows


def parse_batch(path: Path) -> list[dict]:
    if path.suffix.lower() == ".md":
        return parse_markdown_table(path)
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as f:
            rows = []
            for rec in csv.DictReader(f):
                if not any(str(value or "").strip() for value in rec.values()):
                    continue
                lower = {k.lower(): v for k, v in rec.items() if k}
                title = lower.get("title") or rec.get("题名")
                url = lower.get("url") or lower.get("link") or rec.get("链接")
                doi = lower.get("doi") or paper_metadata.extract_doi(url or "") or paper_metadata.extract_doi(title or "")
                ident = lower.get("id") or lower.get("key") or rec.get("标记")
                rows.append({"id": ident, "title": title, "url": url, "doi": doi})
            return rows
    rows = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rows.append({"id": str(idx), "title": None if paper_metadata.extract_doi(line) or line.startswith("http") else line, "url": line if line.startswith("http") else None, "doi": paper_metadata.extract_doi(line)})
    return rows
