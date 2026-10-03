"""Identify protected Markdown blocks, tables and inline contexts without changing offsets."""

from __future__ import annotations

import re


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


LEADING_NUMBER_RE = re.compile(r"^(?:\d+(?:\.\d+)+\s+|\d+(?:\.\d+)*[.、]\s*)")


PIPE_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")


LINK_DEFINITION_RE = re.compile(r"^\s*\[[^\]]+\]:")


def normalize_heading(text: str) -> str:
    text = re.sub(r"[*_`#]", "", text)
    text = LEADING_NUMBER_RE.sub("", text)
    return re.sub(r"\s+", "", text).strip("：:")


def protected_line_indexes(lines: list[str]) -> set[int]:
    protected: set[int] = set()
    in_fence = False
    fence_marker = ""
    in_html_code = False
    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        lowered = stripped.lower()
        if in_html_code:
            protected.add(idx)
            if "</pre>" in lowered or "</code>" in lowered:
                in_html_code = False
            continue
        if lowered.startswith("<pre") or lowered.startswith("<code"):
            protected.add(idx)
            if "</pre>" not in lowered and "</code>" not in lowered:
                in_html_code = True
            continue
        fence = re.match(r"(`{3,}|~{3,})(.*)$", stripped)
        if fence:
            marker, suffix = fence.groups()
            protected.add(idx)
            if in_fence and marker[0] == fence_marker[0] and len(marker) >= len(fence_marker) and not suffix.strip():
                in_fence = False
                fence_marker = ""
            elif not in_fence:
                in_fence = True
                fence_marker = marker
            continue
        if in_fence or line.startswith("    ") or line.startswith("\t"):
            protected.add(idx)
    return protected


def pipe_cell_count(line: str) -> int:
    if "|" not in line:
        return 0
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    cells = [cell.strip() for cell in stripped.split("|")]
    return len(cells) if len(cells) >= 2 else 0


def is_pipe_row(line: str, expected_cells: int | None = None) -> bool:
    count = pipe_cell_count(line)
    if count < 2:
        return False
    return expected_cells is None or count == expected_cells


def is_pipe_separator(line: str, expected_cells: int | None = None) -> bool:
    if not PIPE_TABLE_SEPARATOR_RE.match(line):
        return False
    return is_pipe_row(line, expected_cells)


def find_pipe_tables(lines: list[str], protected: set[int] | None = None) -> list[dict[str, object]]:
    protected = protected or set()
    tables: list[dict[str, object]] = []
    idx = 1
    while idx < len(lines):
        if idx in protected or not is_pipe_separator(lines[idx]):
            idx += 1
            continue
        column_count = pipe_cell_count(lines[idx])
        header_idx = idx - 1
        if header_idx < 0 or header_idx in protected or not is_pipe_row(lines[header_idx], column_count):
            idx += 1
            continue
        end = idx
        while end + 1 < len(lines) and end + 1 not in protected and is_pipe_row(lines[end + 1], column_count):
            end += 1
        tables.append(
            {
                "start_line": header_idx + 1,
                "end_line": end + 1,
                "separator_line": idx + 1,
                "column_count": column_count,
            }
        )
        idx = end + 1
    return tables


def is_table_caption(line: str) -> bool:
    return bool(re.match(r"^\s*(?::|Table:)\s+\S+", line))


def build_table_line_set(lines: list[str]) -> set[int]:
    protected = protected_line_indexes(lines)
    table_lines: set[int] = set()
    for table in find_pipe_tables(lines, protected):
        start = int(table["start_line"]) - 1
        end = int(table["end_line"]) - 1
        table_lines.update(range(start, end + 1))
        for caption_idx, step in ((end + 1, 1), (start - 1, -1)):
            while 0 <= caption_idx < len(lines) and not lines[caption_idx].strip():
                caption_idx += step
            if 0 <= caption_idx < len(lines) and is_table_caption(lines[caption_idx]):
                table_lines.add(caption_idx)
    return table_lines


def mask_span(match: re.Match[str]) -> str:
    return " " * (match.end() - match.start())


def find_balanced_delimiter(text: str, opening: int, left: str, right: str) -> int | None:
    if opening >= len(text) or text[opening] != left:
        return None
    depth = 1
    quote = ""
    escaped = False
    position = opening + 1
    while position < len(text):
        char = text[position]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif quote:
            if char == quote:
                quote = ""
        elif left == "(" and char in {'"', "'"}:
            quote = char
        elif char == left:
            depth += 1
        elif char == right:
            depth -= 1
            if depth == 0:
                return position
        position += 1
    return None


def mask_markdown_links_and_images(text: str) -> str:
    masked = list(text)
    position = 0
    while position < len(text):
        start = position
        if text.startswith("![", position):
            label_open = position + 1
        elif text[position] == "[":
            label_open = position
        else:
            position += 1
            continue
        label_close = find_balanced_delimiter(text, label_open, "[", "]")
        if label_close is None:
            position += 1
            continue
        target_open = label_close + 1
        end: int | None = None
        if target_open < len(text) and text[target_open] == "(":
            target_close = find_balanced_delimiter(text, target_open, "(", ")")
            if target_close is not None:
                end = target_close + 1
        elif target_open < len(text) and text[target_open] == "[":
            target_close = find_balanced_delimiter(text, target_open, "[", "]")
            if target_close is not None:
                label = text[label_open + 1 : label_close]
                target = text[target_open + 1 : target_close]
                consecutive_numeric_citations = bool(
                    re.fullmatch(r"[\d,\-\s，、–—]+", label)
                    and re.fullmatch(r"[\d,\-\s，、–—]+", target)
                )
                if not consecutive_numeric_citations:
                    end = target_close + 1
        if end is None:
            position = label_close + 1
            continue
        masked[start:end] = " " * (end - start)
        position = end
    return "".join(masked)


def mask_inline_context(line: str) -> str:
    masked = re.sub(r"`[^`]*`", mask_span, line)
    masked = mask_markdown_links_and_images(masked)
    def mask_reference_link(match: re.Match[str]) -> str:
        label = match.group(1).strip()
        if re.fullmatch(r"[\d,\-\s，、–—]+", label):
            return match.group(0)
        return " " * (match.end() - match.start())

    masked = re.sub(r"!?\[([^\]]+)\]\[[^\]]*\]", mask_reference_link, masked)
    return mask_math_context(masked)


MATH_CONTEXT_RE = re.compile(
    r"(?<!\\)(?:"
    r"\$\$(?:\\.|[^\\])*?\$\$"
    r"|\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]"
    r"|\$(?![\s$])(?:\\.|(?!\n[ \t]*\n)[^$\\])*?(?<!\s)\$(?!\d)"
    r")"
)


def mask_math_context(text: str) -> str:
    """Hide math without changing offsets or lines used by citation diagnostics."""
    return MATH_CONTEXT_RE.sub(lambda match: re.sub(r"[^\n]", " ", match.group(0)), text)


def mask_html_comments(text: str) -> str:
    """Hide HTML comment spans without changing offsets or line counts.

    Scan before generic inline masking: a backtick inside a comment must not
    pair with one in later prose and hide the comment terminator. Code spans,
    math and escaped openings remain literal to this comment scan.
    """
    masked = list(text)
    position = 0
    while position < len(text):
        # 按起始位置判定语义：已进入代码/公式时，内部的注释符只作为字面内容。
        math = MATH_CONTEXT_RE.match(text, position)
        if math:
            position = math.end()
            continue
        if text[position] == "\\":
            position += 2
            continue
        if text[position] == "`":
            marker = re.match(r"`+", text[position:]).group(0)
            close = re.search(r"(?<!`)" + re.escape(marker) + r"(?!`)", text[position + len(marker):])
            if close:
                position += len(marker) + close.end()
                continue
        if not text.startswith("<!--", position):
            position += 1
            continue
        end = text.find("-->", position + 4)
        if end == -1:
            end = len(text)
        else:
            end += 3
        for idx in range(position, end):
            if text[idx] != "\n":
                masked[idx] = " "
        position = end
    return "".join(masked)


def comment_context_lines(lines: list[str], protected: set[int]) -> list[str]:
    # 先屏蔽已确认的块级结构，再识别注释；注释不能参与后续反引号或数学配对。
    context = "\n".join(
        " " * len(line) if idx in protected else line
        for idx, line in enumerate(lines)
    )
    return mask_html_comments(context).split("\n")


def citation_context_lines(lines: list[str], protected: set[int]) -> list[str]:
    context = "\n".join(mask_inline_context(line) for line in comment_context_lines(lines, protected))
    return mask_math_context(context).split("\n")
