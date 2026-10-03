"""Validate prepared cover fields and Markdown/LaTeX QA before advancing the build."""

from __future__ import annotations




def prepare_warnings(report: dict[str, object]) -> list[str]:
    warnings = report.get("warnings", [])
    if not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings):
        raise RuntimeError("prepare warnings must be a list of strings")
    return warnings


def validate_prepare_qa(report: dict[str, object]) -> list[str]:
    failures: list[str] = []
    qa = report.get("qa", {})
    if not isinstance(qa, dict):
        return ["prepare QA is not an object"]
    cover = report.get("cover", {})
    if not isinstance(cover, dict):
        return ["cover QA is not an object"]
    if qa.get("missing_images"):
        failures.append("image files are missing")
    if qa.get("unsafe_image_paths"):
        failures.append("image paths are absolute, remote, or outside the source Markdown directory")
    if cover.get("logo_path") and cover.get("logo_exists") is not True:
        failures.append("logo file is missing")
    if cover.get("logo_path") and cover.get("logo_inside_project") is not True:
        failures.append("logo path is absolute, remote, or outside the source Markdown directory")
    if qa.get("captions_with_manual_numbers"):
        failures.append("figure captions contain manual numbers")
    if qa.get("missing_reference_entries"):
        failures.append("citations are missing reference-list entries")
    if qa.get("invalid_citation_markers"):
        failures.append("citation markers use invalid numeric syntax")
    return failures


def validate_cover_fields(report: dict[str, object]) -> list[str]:
    cover = report.get("cover", {})
    if not isinstance(cover, dict):
        return []
    if cover.get("enabled") is False or cover.get("thesis") is True:
        return []
    if all(cover.get(key) for key in ("course", "studentname", "studentid")):
        return []
    return ["course, student name, and student ID are required for a course cover"]


def validate_postprocess_qa(qa: dict[str, object], keep_reference_urls: bool = False) -> list[str]:
    failures: list[str] = []
    if qa.get("body_has_abstract_section") is not False:
        failures.append("body_has_abstract_section is not false")
    references_required = bool(qa.get("textsupcite_count") or qa.get("reference_labels"))
    if references_required and qa.get("references_section_found") is not True:
        failures.append("references section was not found after postprocessing")
    if qa.get("remaining_raw_citations_before_references") not in ([], None):
        failures.append("raw citation markers remain before references")
    if qa.get("remaining_unnumbered_display_math") != 0:
        failures.append("unnumbered display math remains")
    if qa.get("dangling_url_macro") is not False:
        failures.append("dangling URL macro remains")
    if qa.get("reference_urls") and not keep_reference_urls:
        failures.append("reference URLs remain")
    if qa.get("longtables_missing_caption") not in (0, None):
        failures.append("longtable captions are missing")
    if qa.get("longtables_missing_endfoot") not in (0, None):
        failures.append("longtable continuation footers are missing")
    if qa.get("longtables_missing_endlastfoot") not in (0, None):
        failures.append("longtable final-page footers are missing")
    if qa.get("longtables_missing_continued_caption") not in (0, None):
        failures.append("longtable continued captions are missing")
    if qa.get("longtable_headers_centered") is not True:
        failures.append("longtable headers are not centered")
    if qa.get("longtable_cells_centered") is not True:
        failures.append("longtable cells are not centered")
    if qa.get("longtable_columns_vertical_centered") is not True:
        failures.append("longtable columns are not vertically centered")
    if qa.get("table_captions_with_manual_numbers"):
        failures.append("manual table caption numbers remain")
    return failures
