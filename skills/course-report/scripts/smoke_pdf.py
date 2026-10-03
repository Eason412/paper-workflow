"""Inspect rendered PDF structure, page size, fonts, images and longtable continuation text."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

if __package__:
    from . import smoke_runtime
else:
    import smoke_runtime


def inspect_pdf_geometry(pdf_path: Path, result: dict[str, object]) -> None:
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo:
        inspected = smoke_runtime.run([pdfinfo, str(pdf_path)], pdf_path.parent)
        if inspected.returncode == 0:
            pages = re.search(r"(?m)^Pages:\s+(\d+)", inspected.stdout)
            size = re.search(r"(?m)^Page size:\s+([\d.]+)\s+x\s+([\d.]+)\s+pts", inspected.stdout)
            result["page_count"] = int(pages.group(1)) if pages else None
            if size:
                width, height = map(float, size.groups())
                result["a4_portrait"] = abs(width - 595.28) <= 2 and abs(height - 841.89) <= 2


def inspect_pdf_assets(pdf_path: Path, result: dict[str, object]) -> None:
    pdffonts = shutil.which("pdffonts")
    if pdffonts:
        inspected = smoke_runtime.run([pdffonts, str(pdf_path)], pdf_path.parent)
        if inspected.returncode == 0:
            flags = [
                match
                for line in inspected.stdout.splitlines()
                if (match := re.search(r"\s+(yes|no)\s+(yes|no)\s+(yes|no)\s+\d+\s+\d+\s*$", line, re.I))
            ]
            result["embedded_fonts"] = bool(flags) and all(match.group(1).lower() == "yes" for match in flags)

    pdfimages = shutil.which("pdfimages")
    if pdfimages:
        inspected = smoke_runtime.run([pdfimages, "-list", str(pdf_path)], pdf_path.parent)
        if inspected.returncode == 0:
            result["image_count"] = sum(
                1 for line in inspected.stdout.splitlines() if re.match(r"^\s*\d+\s+\d+\s+\w+", line)
            )


def inspect_pdf_continuations(pdf_path: Path, result: dict[str, object]) -> None:
    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        inspected = smoke_runtime.run([pdftotext, str(pdf_path), "-"], pdf_path.parent)
        if inspected.returncode == 0:
            result["continued_table_text"] = inspected.stdout.count("LONGTABLEQA") > 1
            table_pages = [
                page
                for page in inspected.stdout.split("\f")
                if re.search(r"ROW\s+\d{2}", page)
            ]
            if len(table_pages) > 1:
                # ASCII only: CJK glyphs may extract differently across fonts and poppler versions.
                result["continued_table_pages_valid"] = all(
                    re.search(r"1[.]1\s*LONGTABLEQA", page) for page in table_pages[1:]
                )
                result["continued_table_page_heads"] = [
                    " ".join(page.split())[:80] for page in table_pages[1:]
                ]


def inspect_pdf(pdf_path: Path) -> dict[str, object]:
    result: dict[str, object] = {
        "header_valid": False,
        "page_count": None,
        "a4_portrait": None,
        "embedded_fonts": None,
        "image_count": None,
        "continued_table_text": None,
        "continued_table_pages_valid": None,
        "qpdf_check": None,
    }
    if not pdf_path.is_file():
        return result
    with pdf_path.open("rb") as handle:
        result["header_valid"] = handle.read(5) == b"%PDF-"

    inspect_pdf_geometry(pdf_path, result)
    inspect_pdf_assets(pdf_path, result)
    inspect_pdf_continuations(pdf_path, result)
    qpdf = shutil.which("qpdf")
    if qpdf:
        inspected = smoke_runtime.run([qpdf, "--check", str(pdf_path)], pdf_path.parent)
        result["qpdf_check"] = inspected.returncode == 0
    return result
