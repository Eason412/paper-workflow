"""Resolve report-local images and assemble Markdown asset and citation QA."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

if __package__:
    from . import markdown_context, report_citations
else:
    import markdown_context, report_citations


def is_url_path(path: str) -> bool:
    parsed = urlparse(path)
    return parsed.scheme in {"http", "https"}


def resolve_project_asset(path: str, source_dir: Path) -> tuple[str, bool, bool]:
    cleaned = path.strip().strip("<>")
    if not is_url_path(cleaned):
        cleaned = cleaned.split("#", 1)[0].replace(r"\ ", " ")
    if not cleaned or is_url_path(cleaned):
        return cleaned, False, False
    candidate = Path(cleaned)
    if candidate.is_absolute():
        return cleaned, candidate.exists(), False
    resolved = source_dir / candidate
    try:
        resolved_path = resolved.resolve()
        inside_project = resolved_path.relative_to(source_dir.resolve()) is not None
    except ValueError:
        inside_project = False
    return cleaned, resolved.exists(), inside_project


def scan_pipe_tables(lines: list[str]) -> dict[str, object]:
    protected = markdown_context.protected_line_indexes(lines)
    tables = markdown_context.find_pipe_tables(lines, protected)
    # Caption validity belongs to Pandoc's parsed tables, not a Markdown regex.
    return {"pipe_table_count": len(tables)}


def markdown_image_destination(raw_target: str) -> str:
    target = raw_target.strip()
    if not target:
        return ""
    if target.startswith("<"):
        end = target.find(">")
        destination = target[1:end] if end != -1 else target[1:]
    else:
        escaped = False
        end = len(target)
        for idx, char in enumerate(target):
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char.isspace():
                end = idx
                break
        destination = target[:end]
    if not is_url_path(destination):
        destination = destination.split("#", 1)[0]
    return destination.replace(r"\ ", " ")


def extract_markdown_images(text: str) -> list[tuple[str, str]]:
    images: list[tuple[str, str]] = []
    def reference_key(label: str) -> str:
        return " ".join(label.split()).casefold()

    definitions: dict[str, str] = {}
    for definition in re.finditer(r"(?m)^ {0,3}\[([^\]]+)\]:[ \t]*(?:\n[ \t]*)?(.+)$", text):
        definitions.setdefault(reference_key(definition.group(1)), markdown_image_destination(definition.group(2)))

    opener = re.compile(r"(?<!\\)!\[")
    pos = 0
    while True:
        match = opener.search(text, pos)
        if not match:
            break
        label_end = markdown_context.find_balanced_delimiter(text, match.end() - 1, "[", "]")
        if label_end is None:
            pos = match.end()
            continue
        caption = text[match.end():label_end]
        pos = label_end + 1
        if text[pos:pos + 1] == "(":
            target_end = markdown_context.find_balanced_delimiter(text, pos, "(", ")")
            if target_end is not None:
                images.append((caption, markdown_image_destination(text[pos + 1:target_end])))
                pos = target_end + 1
            continue

        # Full, collapsed and shortcut references all use the same asset QA.
        key = caption
        spacing = re.match(r"[ \t]*(?:\n[ \t]*)?", text[pos:])
        target_start = pos + len(spacing.group(0)) if spacing else pos
        if text[target_start:target_start + 1] == "[":
            target_end = markdown_context.find_balanced_delimiter(text, target_start, "[", "]")
            if target_end is not None:
                key = text[target_start + 1:target_end] or caption
                pos = target_end + 1
        destination = definitions.get(reference_key(key))
        if destination is not None:
            images.append((caption, destination))
    return images


def scan_body(body: str, source_dir: Path) -> dict[str, object]:
    lines = body.splitlines()
    protected = markdown_context.protected_line_indexes(lines)
    scan_text = "\n".join("" if idx in protected else line for idx, line in enumerate(lines))
    markdown_image_items = extract_markdown_images(scan_text)
    markdown_images = [item[1] for item in markdown_image_items]
    html_images = re.findall(r"<img\b[^>]*\bsrc=['\"]([^'\"]+)['\"]", scan_text, flags=re.I)
    images = markdown_images + html_images
    image_items = []
    for image in images:
        path, exists, inside_project = resolve_project_asset(image, source_dir)
        image_items.append({"path": path, "exists": exists, "inside_project": inside_project})

    captions_with_numbers = [caption for caption, _ in markdown_image_items if re.match(r"\s*[图表]\s*\d+", caption)]
    table_qa = scan_pipe_tables(lines)
    body_before_refs, reference_section = report_citations.split_reference_section(body)
    citations = report_citations.collect_body_citations(body_before_refs)
    invalid_citations = report_citations.collect_invalid_body_citations(body_before_refs)
    references = report_citations.extract_reference_numbers(reference_section)

    return {
        "image_count": len(image_items),
        "images": image_items,
        "missing_images": [item["path"] for item in image_items if not item["exists"]],
        "unsafe_image_paths": [item["path"] for item in image_items if not item["inside_project"]],
        "captions_with_manual_numbers": captions_with_numbers,
        **table_qa,
        "references_section_found": bool(reference_section),
        "citation_numbers": citations,
        "invalid_citation_markers": invalid_citations,
        "reference_numbers": references,
        "missing_reference_entries": [n for n in citations if n not in references],
        "unused_reference_entries": [n for n in references if n not in citations],
    }


def qa_warnings(qa: dict[str, object], slide_draft: dict[str, object]) -> list[str]:
    """把正文扫描结果整理成给用户看的警告，顺序固定。"""
    warnings: list[str] = []
    if slide_draft["detected"]:
        warnings.append(
            "输入看起来是逐页讲稿或幻灯片内容稿（如“第 X 页”“屏幕：”“讲：”“图：”），"
            "已按原稿转换，请检查是否需要课程报告结构。"
        )
    if qa["missing_images"]:
        warnings.append("存在缺失图片：" + ", ".join(qa["missing_images"]))
    if qa["captions_with_manual_numbers"]:
        warnings.append("图片或表格 caption 含手写编号，可能与 LaTeX 自动编号重复。")
    if qa["missing_reference_entries"]:
        warnings.append("正文引用缺少参考文献条目：" + ", ".join(map(str, qa["missing_reference_entries"])))
    if qa["invalid_citation_markers"]:
        warnings.append("存在非法引用格式：" + ", ".join(qa["invalid_citation_markers"]))
    if qa["unused_reference_entries"]:
        warnings.append("存在未被正文引用的参考文献条目，请确认是否保留：" + ", ".join(map(str, qa["unused_reference_entries"])))
    return warnings
