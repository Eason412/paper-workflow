#!/usr/bin/env python3
"""Postprocess Pandoc LaTeX for the course-report template."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REF_SENTINEL = "% COURSE_REPORT_REFERENCES_BEGIN"
REF_MARKER = r"\section*{\centering\zihao{3}\songti\bfseries 参考文献}"
REF_HEADING_RE = re.compile(
    r"(?:\\clearpage\s*)?\\section\*?\{(?:\\centering\\zihao\{3\}\\songti\\bfseries\s*)?参考文献\}",
    re.S,
)
RAW_CITATION_TEX_RE = re.compile(r"\{\[\}([\d,\-\s]+?)\{\]\}")
LONGTABLE_RE = re.compile(r"\\begin\{longtable\}.*?\\end\{longtable\}", re.S)


def split_references(tex: str) -> tuple[str, str]:
    sentinel_block = re.compile(
        rf"^{re.escape(REF_SENTINEL)}\s*\n\s*\\phantomsection\s*\n\s*{re.escape(REF_MARKER)}",
        re.M,
    )
    sentinel_matches = list(sentinel_block.finditer(tex))
    if sentinel_matches:
        pos = sentinel_matches[-1].start()
    else:
        heading_matches = list(REF_HEADING_RE.finditer(tex))
        if not heading_matches:
            return tex, ""
        pos = heading_matches[-1].start()
    return tex[:pos], tex[pos:]


def convert_citations(body: str) -> str:
    citation_group = re.compile(r"(?:\{\[\}([\d,\-\s，、–—]+)\{\]\}\s*)+")

    def repl(match: re.Match[str]) -> str:
        nums = re.findall(r"\{\[\}([\d,\-\s，、–—]+)\{\]\}", match.group(0))
        cleaned = ",".join(
            part.strip().replace(" ", "").replace("，", ",").replace("、", ",").replace("–", "-").replace("—", "-")
            for part in nums
            if part.strip()
        )
        return r"\textsupcite{" + cleaned + "}"

    return citation_group.sub(repl, body)


def number_display_math(body: str) -> str:
    pattern = re.compile(r"\\\[(.*?)\\\]", re.S)

    def repl(match: re.Match[str]) -> str:
        content = match.group(1).strip()
        if not content:
            return match.group(0)
        if r"\begin{" in content or r"\tag{" in content:
            return match.group(0)
        return "\\begin{equation}\n" + content + "\n\\end{equation}"

    return pattern.sub(repl, body)


def center_longtable_headers(tex: str) -> str:
    def center_plain_header_row(row: str) -> str:
        if r"\begin{minipage}" in row or r"\multicolumn" in row:
            return row
        line = row.rstrip()
        if not line.endswith(r"\\") or "&" not in line:
            return row
        cells = [cell.strip() for cell in line[:-2].split("&")]
        centered = " & ".join(r"\multicolumn{1}{c}{" + cell + "}" for cell in cells) + r" \\"
        return centered + ("\n" if row.endswith("\n") else "")

    def center_plain_headers(block: str) -> str:
        def row_repl(match: re.Match[str]) -> str:
            return match.group(1) + center_plain_header_row(match.group(2)) + match.group(3)

        return re.sub(
            r"(\\toprule\\noalign\{\}\n)(.*?\\\\\n)(\\midrule\\noalign\{\})",
            row_repl,
            block,
            flags=re.S,
        )

    def repl(match: re.Match[str]) -> str:
        block = match.group(0)
        if r"\endfirsthead" not in block and r"\endhead" not in block:
            return block
        head_end_positions = [
            pos
            for pos in (block.find(r"\endfirsthead"), block.find(r"\endhead"))
            if pos != -1
        ]
        data_start = min(head_end_positions) if head_end_positions else len(block)
        return (
            block[:data_start].replace(r"\begin{minipage}[b]{\linewidth}\raggedright", r"\begin{minipage}[b]{\linewidth}\centering")
            + block[data_start:]
        )

    centered = LONGTABLE_RE.sub(repl, tex)
    return LONGTABLE_RE.sub(lambda match: center_plain_headers(match.group(0)), centered)


def center_longtable_cells(tex: str) -> str:
    def center_simple_column_spec(match: re.Match[str]) -> str:
        return match.group(1) + re.sub(r"[lcr]", "c", match.group(2)) + match.group(3)

    def repl(match: re.Match[str]) -> str:
        block = match.group(0)
        block = re.sub(
            r">\{\\(?:raggedright|raggedleft|centering)\\arraybackslash\}p\{",
            lambda _: r">{\centering\arraybackslash}m{",
            block,
        )
        block = re.sub(
            r"(\\begin\{longtable\}\[\]\{@\{\})([lcr]+)(@\{\}\})",
            center_simple_column_spec,
            block,
            count=1,
        )
        block = re.sub(
            r"\\begin\{minipage\}\[[btc]\]\{\\linewidth\}\\(?:raggedright|raggedleft|centering)",
            lambda _: r"\begin{minipage}[c]{\linewidth}\centering",
            block,
        )
        block = re.sub(r"\\multicolumn\{1\}\{[lcr]\}\{", r"\\multicolumn{1}{c}{", block)
        return block

    return LONGTABLE_RE.sub(repl, tex)


def add_longtable_continuations(tex: str) -> str:
    def repl(match: re.Match[str]) -> str:
        block = match.group(0)
        caption_match = re.search(r"\\caption\{([^{}]+)\}\\tabularnewline", block)
        if not caption_match:
            return block
        caption = caption_match.group(1)
        if r"\endfoot" not in block:
            block = block.replace(
                r"\endhead",
                "\\endhead\n\\bottomrule\\noalign{}\n\\endfoot",
                1,
            )
        if r"\endlastfoot" not in block:
            block = block.replace(
                r"\endfoot",
                "\\endfoot\n\\bottomrule\\noalign{}\n\\endlastfoot",
                1,
            )
        if "（续表）" not in block:
            block = block.replace(
                r"\endfirsthead",
                "\\endfirsthead\n\\caption[]{" + caption + "（续表）}\\tabularnewline",
                1,
            )
        return block

    return LONGTABLE_RE.sub(repl, tex)


def _read_braced(text: str, opening: int) -> tuple[str, int] | None:
    if opening >= len(text) or text[opening] != "{":
        return None
    depth = 1
    escaped = False
    position = opening + 1
    while position < len(text):
        char = text[position]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[opening + 1 : position], position + 1
        position += 1
    return None


def _strip_reference_link_commands(refs: str) -> str:
    output: list[str] = []
    position = 0
    while position < len(refs):
        if refs.startswith(r"\href{", position):
            target = _read_braced(refs, position + len(r"\href"))
            if target and target[0].startswith(("http://", "https://")):
                label = _read_braced(refs, target[1])
                if label:
                    output.append(label[0])
                    position = label[1]
                    continue
        if refs.startswith(r"\url{", position):
            target = _read_braced(refs, position + len(r"\url"))
            if target and target[0].startswith(("http://", "https://")):
                position = target[1]
                continue
        output.append(refs[position])
        position += 1
    return "".join(output)


def _remove_bare_url(match: re.Match[str]) -> str:
    url = match.group(0)
    trailing = ""
    while url and url[-1] in ".,;:!?，。；：、)］]":
        trailing = url[-1] + trailing
        url = url[:-1]
    return trailing


def clean_reference_tail(refs: str) -> str:
    if not refs:
        return refs
    refs = refs.replace(REF_SENTINEL + "\n", "")
    refs = refs.replace(REF_MARKER + "\n\\addcontentsline", REF_MARKER + "\n\\phantomsection\n\\addcontentsline")
    refs = _strip_reference_link_commands(refs)
    refs = re.sub(r"https?://[^\s{}\\]+", _remove_bare_url, refs)
    refs = re.sub(r"[ \t]+([,.;:!?，。；：、])", r"\1", refs)
    return refs


def qa_report(tex: str, body: str, refs: str) -> dict[str, object]:
    longtables = re.findall(r"\\begin\{longtable\}.*?\\end\{longtable\}", tex, flags=re.S)
    # 官方规范: 一级 TOC 条目(章/致谢/参考文献/附录)用 4 号加粗, 子级用小 4 号。
    # 一级条目样式来自 \l@section 引用的 \reporttocsectionfont, 子级来自 \reporttocfont。
    section_toc_def = re.search(
        r"\\renewcommand\*?\\l@section.*?(?=\\renewcommand\*?\\l@subsection)",
        tex,
        flags=re.S,
    )
    section_toc_text = section_toc_def.group(0) if section_toc_def else ""
    sub_font_body_match = re.search(r"\\newcommand\{\\reporttocfont\}\{([^\n]*)\}", tex)
    sub_font_body = sub_font_body_match.group(1) if sub_font_body_match else ""
    section_font_body_match = re.search(r"\\newcommand\{\\reporttocsectionfont\}\{([^\n]*)\}", tex)
    section_font_body = section_font_body_match.group(1) if section_font_body_match else ""
    sub_size_match = re.search(r"\\zihao\{([^}]+)\}", sub_font_body)
    toc_sub_font_size = sub_size_match.group(1) if sub_size_match else None
    section_styles_l1 = r"\reporttocsectionfont" in section_toc_text
    section_size_match = re.search(r"\\zihao\{([^}]+)\}", section_font_body)
    toc_section_font_size = section_size_match.group(1) if (section_size_match and section_styles_l1) else None
    toc_section_is_bold = bool(r"\bfseries" in section_font_body and section_styles_l1)
    toc_font_sizes = {size for size in (toc_sub_font_size, toc_section_font_size) if size}
    cover_uses_makebox = bool(r"\newcommand{\coverfield}" in tex and r"\makebox[\textwidth][c]" in tex)
    # \coverthesisfields 出现一次是宏定义；标题页再调用一次说明渲染了学位论文封面。
    thesis_cover_rendered = len(re.findall(r"\\coverthesisfields\b", tex)) >= 2
    course_cover_rendered = len(re.findall(r"\\coverfields\b", tex)) >= 2
    return {
        "references_section_found": bool(refs),
        "body_has_abstract_section": bool(re.search(r"\\section\{(?:摘要|Abstract)\}", body)),
        "remaining_raw_citations_before_references": RAW_CITATION_TEX_RE.findall(body),
        "remaining_unnumbered_display_math": len(re.findall(r"\\\[", body)),
        "equation_count": len(re.findall(r"\\begin\{equation\}", tex)),
        "textsupcite_count": len(re.findall(r"\\textsupcite\{", body)),
        "reference_labels": re.findall(r"\{\[\}(\d+)\{\]\}", refs),
        "reference_urls": re.findall(r"https?://\S+", refs),
        "dangling_url_macro": bool(re.search(r"\\url\{\s*(?:[,.;，。；、)]|\n|$)", refs)),
        "longtable_count": len(longtables),
        "booktabs_longtable_count": len(
            [
                table
                for table in longtables
                if all(rule in table for rule in (r"\toprule", r"\midrule", r"\bottomrule"))
            ]
        ),
        "longtables_missing_caption": sum(1 for table in longtables if r"\caption{" not in table),
        "longtables_missing_endfoot": sum(1 for table in longtables if r"\endfoot" not in table),
        "longtables_missing_endlastfoot": sum(1 for table in longtables if r"\endlastfoot" not in table),
        "longtables_missing_continued_caption": sum(1 for table in longtables if "（续表）" not in table),
        "longtable_headers_centered": all(
            (
                r"\begin{minipage}[b]{\linewidth}\centering" in table
                or r"\begin{minipage}[c]{\linewidth}\centering" in table
                or r"\multicolumn{1}{c}{" in table
            )
            for table in longtables
        ),
        "longtable_cells_centered": all(
            not re.search(
                r"\\raggedright|\\raggedleft|\\begin\{longtable\}\[\]\{@\{\}[lr]|\\multicolumn\{1\}\{[lr]\}\{",
                table,
            )
            for table in longtables
        ),
        "longtable_columns_vertical_centered": all(
            not re.search(
                r">\{\\(?:raggedright|raggedleft|centering)\\arraybackslash\}p\{|\\begin\{minipage\}\[[bt]\]\{\\linewidth\}",
                table,
            )
            for table in longtables
        ),
        "table_captions_with_manual_numbers": re.findall(r"\\caption\{[表Table\s]*\d+(?:\.\d+)?[^}]*\}", tex),
        "toc_section_font_size": toc_section_font_size,
        "toc_section_is_bold": toc_section_is_bold,
        "toc_sub_font_size": toc_sub_font_size,
        "toc_entry_font_sizes": sorted(toc_font_sizes),
        "toc_uses_shared_numwidth": bool(r"\reporttocnumwidth" in tex),
        "toc_page_width_configured": bool(re.search(r"\\def\\@pnumwidth\{[^}]+\}.*?\\def\\@tocrmarg\{[^}]+\}", tex, flags=re.S)),
        "titlepage_uses_top_fill_before_logo": bool(re.search(r"\\begin\{titlepage\}.*?\\vspace\*\{\\fill\}.*?\\includegraphics", tex, flags=re.S)),
        "cover_fields_use_centered_tabular": bool(r"\newcommand{\coverfields}" in tex and r"\begin{center}" in tex) or cover_uses_makebox,
        "cover_fields_use_makebox_centering": cover_uses_makebox,
        "cover_fields_have_underlines": bool(r"\underline{\makebox[\covervaluewidth][c]" in tex),
        "thesis_cover_rendered": thesis_cover_rendered,
        "course_cover_rendered": course_cover_rendered,
        "cover_course_field_wrap_enabled": bool(
            re.search(r"\\newcommand\{\\covercoursefield\}[^\n]*\\begin\{minipage\}", tex)
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tex", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--qa", type=Path, default=Path("latex/postprocess_qa.json"))
    args = parser.parse_args()

    tex = args.tex.read_text(encoding="utf-8")
    body, refs = split_references(tex)
    refs = clean_reference_tail(refs)
    processed = add_longtable_continuations(center_longtable_cells(center_longtable_headers(body + refs)))
    out = args.tex if args.in_place or args.output is None else args.output
    out.write_text(processed, encoding="utf-8")
    if args.qa:
        args.qa.parent.mkdir(parents=True, exist_ok=True)
        args.qa.write_text(json.dumps(qa_report(processed, body, refs), ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
