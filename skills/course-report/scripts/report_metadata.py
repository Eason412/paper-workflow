"""Extract front matter, abstracts and report headings, and serialize template metadata."""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePath

if __package__:
    from . import markdown_context
else:
    import markdown_context


NUM_PREFIX_RE = re.compile(r"^(#{2,6})\s+(?:\d+(?:\.\d+)+\s+|\d+(?:\.\d+)*[.、]\s*)(.+?)\s*$")


KEYWORDS_ZH_RE = re.compile(r"^\s*(?:\*\*)?\s*关键词\s*(?:\*\*)?\s*[：:]\s*(.+?)\s*$", re.I)


KEYWORDS_EN_RE = re.compile(r"^\s*(?:\*\*)?\s*Keywords\s*(?:\*\*)?\s*[：:]\s*(.+?)\s*$", re.I)


SLIDE_PAGE_HEADING_RE = re.compile(r"^##\s*第\s*\d+\s*页\s*[｜|:：]")


SLIDE_FIELD_RE = re.compile(r"^(?:屏幕|讲|图)\s*[：:]")


FRONT_MATTER_KV_RE = re.compile(r"^\s*([^:：#][^:：]*?)\s*[:：]\s*(.*?)\s*$")


# 学位论文封面 front-matter 键 -> metadata.yaml 模板变量名。
# 同时接受英文键和中文键，便于直接照模板填写。
FRONT_MATTER_KEYS: dict[str, str] = {
    "title": "title",
    "题目": "title",
    "题名": "title",
    "subtitle": "subtitle",
    "副标题": "subtitle",
    "副题名": "subtitle",
    "cover": "cover_style",
    "cover_style": "cover_style",
    "封面": "cover_style",
    "classification": "classification",
    "分类号": "classification",
    "secrecy": "secrecy",
    "密级": "secrecy",
    "udc": "udc",
    "UDC": "udc",
    "degree_type": "degreetype",
    "学位类型": "degreetype",
    "论文级别": "degreetype",
    "author": "studentname",
    "作者": "studentname",
    "作者姓名": "studentname",
    "advisor": "advisor",
    "导师": "advisor",
    "指导教师": "advisor",
    "指导教师姓名": "advisor",
    "advisor_title": "advisortitle",
    "职称": "advisortitle",
    "degree_category": "degreecategory",
    "学位类别": "degreecategory",
    "discipline": "discipline",
    "学科名称": "discipline",
    "专业名称": "discipline",
    "discipline_label": "disciplinelabel",
    "学科标签": "disciplinelabel",
    "research_field": "researchfield",
    "研究方向": "researchfield",
    "submit_date": "submitdate",
    "论文提交时间": "submitdate",
    "提交时间": "submitdate",
    "course": "course",
    "课程名称": "course",
    "studentname": "studentname",
    "student_name": "studentname",
    "姓名": "studentname",
    "studentid": "studentid",
    "student_id": "studentid",
    "学号": "studentid",
}


# 触发学位论文封面的 front-matter 字段（任一非空即切换到学位论文版式）。
THESIS_TRIGGER_KEYS = ("degreetype", "advisor", "degreecategory", "discipline", "researchfield")


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Split a leading YAML-style ``--- ... ---`` block from the Markdown body.

    Only flat ``key: value`` pairs are supported; values are read as plain
    strings so users can fill the thesis-cover template without YAML knowledge.
    """
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    for idx in range(1, len(lines)):
        if lines[idx].strip() in {"---", "..."}:
            data: dict[str, str] = {}
            for number, raw in enumerate(lines[1:idx], start=2):
                if not raw.strip() or raw.lstrip().startswith("#"):
                    continue
                if raw.startswith((" ", "\t")):
                    raise ValueError(f"front matter line {number}: nested/indented fields are not supported")
                match = FRONT_MATTER_KV_RE.match(raw)
                if not match:
                    raise ValueError(f"front matter line {number}: expected single-line key: value")
                key = match.group(1).strip()
                value = match.group(2).strip()
                if value.startswith(('"', "'")):
                    quoted = re.fullmatch(r'''("(?:\\.|[^"\\])*"|'(?:''|[^'])*')\s*(?:#.*)?''', value)
                    if not quoted:
                        raise ValueError(f"front matter line {number}: unpaired quote or trailing content")
                    token = quoted.group(1)
                    try:
                        value = json.loads(token) if token.startswith('"') else token[1:-1].replace("''", "'")
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"front matter line {number}: invalid quoted string") from exc
                else:
                    value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
                    if value in {"|", ">", "|-", ">-", "|+", ">+"} or value.startswith(("[", "{")):
                        raise ValueError(f"front matter line {number}: only single-line string values are supported")
                if key:
                    data[key] = value
            return data, "\n".join(lines[idx + 1 :])
    raise ValueError("front matter: missing closing --- delimiter")


def map_front_matter(raw: dict[str, str]) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for key, value in raw.items():
        target = FRONT_MATTER_KEYS.get(key)
        if target and value:
            mapped.setdefault(target, value)
    return mapped


def clean_keyword_value(value: str) -> str:
    return value.strip().strip("*").strip()


def detect_slide_draft(lines: list[str]) -> dict[str, object]:
    """Detect page-by-page PPT drafts that are not course-report sources."""
    protected = markdown_context.protected_line_indexes(lines)
    visible_lines = [line for idx, line in enumerate(lines) if idx not in protected]
    page_heading_count = sum(1 for line in visible_lines if SLIDE_PAGE_HEADING_RE.match(line.strip()))
    slide_field_count = sum(1 for line in visible_lines if SLIDE_FIELD_RE.match(line.strip()))
    detected = page_heading_count >= 3 and slide_field_count >= 6
    return {
        "detected": detected,
        "page_heading_count": page_heading_count,
        "slide_field_count": slide_field_count,
    }


def strip_outer_title_marks(text: str) -> str:
    text = text.strip()
    if text.startswith("《") and text.endswith("》"):
        return text[1:-1].strip()
    return text


def yaml_block(key: str, value: str | PurePath) -> str:
    if isinstance(value, PurePath):
        value = value.as_posix()
    value = value.rstrip()
    if not value:
        return f"{key}: ''\n"
    if "\n" not in value:
        # Pandoc may resolve numeric-looking block scalars as numbers; quoted
        # strings preserve identifiers such as student IDs, including zeroes.
        return f"{key}: {json.dumps(value, ensure_ascii=False)}\n"
    lines = value.splitlines()
    indented = "\n".join(f"  {line}" if line else "" for line in lines)
    return f"{key}: |-\n{indented}\n"


def extract_abstract_content(
    section_lines: list[tuple[int, str]], protected: set[int], metadata: dict[str, str],
) -> str:
    body_lines: list[str] = []
    for index, line in section_lines:
        if index in protected:
            body_lines.append(line)
            continue
        if line.strip() in {r"\newpage", r"\clearpage"}:
            continue
        zh_kw = KEYWORDS_ZH_RE.match(line)
        en_kw = KEYWORDS_EN_RE.match(line)
        if zh_kw:
            metadata["keywords_zh"] = clean_keyword_value(zh_kw.group(1))
            continue
        if en_kw:
            metadata["keywords_en"] = clean_keyword_value(en_kw.group(1))
            continue
        body_lines.append(line)

    return "\n".join(body_lines).strip()


def extract_abstract(lines: list[str]) -> tuple[list[str], dict[str, str], list[str]]:
    metadata: dict[str, str] = {}
    warnings: list[str] = []
    output: list[str] = []
    i = 0
    protected = markdown_context.protected_line_indexes(lines)

    while i < len(lines):
        match = markdown_context.HEADING_RE.match(lines[i]) if i not in protected else None
        if not match:
            output.append(lines[i])
            i += 1
            continue

        level, heading = match.groups()
        kind = markdown_context.normalize_heading(heading)
        is_zh_abs = level == "##" and kind == "摘要"
        is_en_abs = level == "##" and kind.lower() == "abstract"
        if not (is_zh_abs or is_en_abs):
            output.append(lines[i])
            i += 1
            continue

        section_lines: list[tuple[int, str]] = []
        i += 1
        while i < len(lines):
            next_heading = markdown_context.HEADING_RE.match(lines[i]) if i not in protected else None
            if next_heading and next_heading.group(1) == "##":
                break
            section_lines.append((i, lines[i]))
            i += 1

        body = extract_abstract_content(section_lines, protected, metadata)
        if is_zh_abs:
            metadata["abstract_zh"] = body
        else:
            metadata["abstract_en"] = body

    if "abstract_zh" not in metadata:
        warnings.append("未找到中文摘要，前置摘要页将为空。")
    if "abstract_en" not in metadata:
        warnings.append("未找到英文 Abstract，英文摘要页将为空。")

    return output, metadata, warnings


def prepare_body(lines: list[str]) -> tuple[list[str], str | None, list[str]]:
    title: str | None = None
    output: list[str] = []
    warnings: list[str] = []

    protected = markdown_context.protected_line_indexes(lines)
    for idx, line in enumerate(lines):
        if idx in protected:
            output.append(line)
            continue
        match = markdown_context.HEADING_RE.match(line)
        if match and match.group(1) == "#" and title is None:
            title = strip_outer_title_marks(match.group(2))
            continue

        num_match = NUM_PREFIX_RE.match(line)
        if num_match:
            output.append(f"{num_match.group(1)} {num_match.group(2).strip()}")
            continue

        output.append(line)

    if title is None:
        warnings.append("未找到一级标题，将使用输入文件名作为封面题目。")
    return output, title, warnings


def keyword_count(value: str) -> int:
    if not value:
        return 0
    parts = re.split(r"[；;,，]", value)
    return len([p for p in parts if p.strip()])


def cover_metadata(
    front_matter: dict[str, str], metadata: dict[str, str], title: str,
    *, course: str, student_name: str, student_id: str, logo: str, no_cover: bool,
) -> dict[str, object]:
    """按优先级填封面字段（命令行参数优先于 front-matter，front-matter 优先于空默认值），返回封面摘要。"""
    course = course or front_matter.get("course", "")
    studentname = student_name or front_matter.get("studentname", "")
    studentid = student_id or front_matter.get("studentid", "")
    thesis_cover = (
        front_matter.get("cover_style", "").strip().lower() == "thesis"
        or any(front_matter.get(key) for key in THESIS_TRIGGER_KEYS)
    )
    metadata.update(
        {
            "title": title,
            "subtitle": front_matter.get("subtitle", ""),
            "course": course,
            "studentname": studentname,
            "studentid": studentid,
            "logo": Path(logo).as_posix() if logo else "",
            "cover_disabled": "yes" if no_cover else "",
            "thesis_cover": "yes" if thesis_cover and not no_cover else "",
            "classification": front_matter.get("classification", ""),
            "secrecy": front_matter.get("secrecy", ""),
            "udc": front_matter.get("udc", ""),
            "degreetype": front_matter.get("degreetype", ""),
            "advisor": front_matter.get("advisor", ""),
            "advisortitle": front_matter.get("advisortitle", ""),
            "degreecategory": front_matter.get("degreecategory", ""),
            "discipline": front_matter.get("discipline", ""),
            "disciplinelabel": front_matter.get("disciplinelabel", "") or "学科名称",
            "researchfield": front_matter.get("researchfield", ""),
            "submitdate": front_matter.get("submitdate", ""),
        }
    )
    return {
        "enabled": not no_cover,
        "thesis": thesis_cover and not no_cover,
        "course": course,
        "studentname": studentname,
        "studentid": studentid,
        "logo_path": logo,
    }
