"""Locate reference sections and collect, normalize and deduplicate numeric citations."""

from __future__ import annotations

import re

if __package__:
    from . import markdown_context
else:
    import markdown_context


CITATION_RE = re.compile(r"(?<!\{)[\[［]([\d,\-\s，、–—]+)[\]］]")


REFERENCE_LABEL_RE = re.compile(r"(?m)^\s*(?:[\[［](\d+)[\]］]|(\d+)[.、])\s+")


def is_reference_heading(line: str) -> bool:
    match = markdown_context.HEADING_RE.match(line)
    if not match:
        return False
    kind = markdown_context.normalize_heading(match.group(2)).lower()
    return kind in {"参考文献", "references", "reference"}


def extract_reference_numbers(text: str) -> list[int]:
    numbers: set[int] = set()
    lines = text.splitlines()
    protected = markdown_context.protected_line_indexes(lines)
    for idx, line in enumerate(markdown_context.comment_context_lines(lines, protected)):
        if idx in protected or markdown_context.LINK_DEFINITION_RE.match(line):
            continue
        match = REFERENCE_LABEL_RE.match(line)
        if match:
            number = match.group(1) or match.group(2)
            if number:
                numbers.add(int(number))
    return sorted(numbers)


def split_reference_section(body: str) -> tuple[str, str]:
    lines = body.splitlines()
    bounds = reference_section_bounds(lines)
    if bounds is None:
        return body, ""
    start, end = bounds
    return "\n".join(lines[:start] + lines[end:]), "\n".join(lines[start:end])


def reference_section_bounds(lines: list[str]) -> tuple[int, int] | None:
    protected = markdown_context.protected_line_indexes(lines)
    visible = markdown_context.comment_context_lines(lines, protected)
    candidates = [idx for idx, line in enumerate(visible) if idx not in protected and is_reference_heading(line)]
    for idx in reversed(candidates):
        level = len(markdown_context.HEADING_RE.match(visible[idx]).group(1))
        end = len(lines)
        for next_idx in range(idx + 1, len(lines)):
            heading = markdown_context.HEADING_RE.match(visible[next_idx]) if next_idx not in protected else None
            if heading and len(heading.group(1)) <= level:
                end = next_idx
                break
        if extract_reference_numbers("\n".join(lines[idx + 1:end])) or idx >= int(len(lines) * 0.75):
            return idx, end
    return None


def parse_numeric_marker(marker: str) -> tuple[list[int], bool]:
    normalized = marker.replace("，", ",").replace("、", ",").replace("–", "-").replace("—", "-")
    numbers: set[int] = set()
    parts = re.split(r"\s*,\s*", normalized)
    if not parts or any(not part.strip() for part in parts):
        return [], False
    for part in parts:
        part = part.strip()
        if re.fullmatch(r"\d+", part):
            number = int(part)
            if number <= 0:
                return [], False
            numbers.add(number)
            continue
        range_match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
        if not range_match:
            return [], False
        start, end = map(int, range_match.groups())
        if not (0 < start <= end <= start + 50):
            return [], False
        numbers.update(range(start, end + 1))
    return sorted(numbers), True


def expand_numeric_markers(markers: list[str]) -> list[int]:
    numbers: set[int] = set()
    for marker in markers:
        parsed, valid = parse_numeric_marker(marker)
        if valid:
            numbers.update(parsed)
    return sorted(numbers)


def format_citation_marker(numbers: list[int]) -> str:
    if not numbers:
        return ""
    unique_numbers = sorted(set(numbers))
    ranges: list[str] = []
    start = prev = unique_numbers[0]
    for number in unique_numbers[1:]:
        if number == prev + 1:
            prev = number
            continue
        ranges.append(f"{start}-{prev}" if start != prev else str(start))
        start = prev = number
    ranges.append(f"{start}-{prev}" if start != prev else str(start))
    return "[" + ",".join(ranges) + "]"


def replace_citations_in_line(line: str, replace_match, masked: str | None = None) -> str:
    if markdown_context.LINK_DEFINITION_RE.match(line):
        return line
    if masked is None:
        masked = markdown_context.mask_inline_context(line)
    pieces: list[str] = []
    pos = 0
    for match in CITATION_RE.finditer(masked):
        pieces.append(line[pos : match.start()])
        original = re.match(CITATION_RE, line[match.start() : match.end()])
        if original:
            pieces.append(replace_match(original))
        else:
            pieces.append(line[match.start() : match.end()])
        pos = match.end()
    pieces.append(line[pos:])
    return "".join(pieces)


def collect_body_citations(body_before_refs: str) -> list[int]:
    lines = body_before_refs.splitlines()
    protected = markdown_context.protected_line_indexes(lines)
    table_lines = markdown_context.build_table_line_set(lines)
    context = markdown_context.citation_context_lines(lines, protected | table_lines)
    markers: list[str] = []
    for idx, line in enumerate(lines):
        if idx in protected or idx in table_lines or markdown_context.LINK_DEFINITION_RE.match(line):
            continue
        markers.extend(CITATION_RE.findall(context[idx]))
    return expand_numeric_markers(markers)


def collect_invalid_body_citations(body_before_refs: str) -> list[str]:
    lines = body_before_refs.splitlines()
    protected = markdown_context.protected_line_indexes(lines)
    table_lines = markdown_context.build_table_line_set(lines)
    context = markdown_context.citation_context_lines(lines, protected | table_lines)
    invalid: list[str] = []
    for idx, line in enumerate(lines):
        if idx in protected or idx in table_lines or markdown_context.LINK_DEFINITION_RE.match(line):
            continue
        for marker in CITATION_RE.finditer(context[idx]):
            _, valid = parse_numeric_marker(marker.group(1))
            rendered = line[marker.start() : marker.end()]
            if not valid and rendered not in invalid:
                invalid.append(rendered)
    return invalid


class CitationDeduplicator:
    """Track first occurrences and diagnostic events while rewriting one marker."""

    def __init__(self, keep_repeated_citations: bool) -> None:
        self.keep_repeated_citations = keep_repeated_citations
        self.seen: set[int] = set()
        self.events: list[dict[str, object]] = []
        self.removed_marker_count = 0
        self.rewritten_marker_count = 0
        self.normalized_marker_count = 0
        self.removed_numbers: list[int] = []

    def remove_repeated_numbers(self, match: re.Match[str], line_number: int) -> str:
        marker = match.group(0)
        numbers = expand_numeric_markers([match.group(1)])
        if not numbers:
            return marker
        if self.keep_repeated_citations:
            return marker
        new_numbers = [number for number in numbers if number not in self.seen]
        repeated_numbers = [number for number in numbers if number in self.seen]
        self.seen.update(numbers)
        if not repeated_numbers:
            return marker
        self.removed_numbers.extend(repeated_numbers)
        self.events.append(
            {
                "line": line_number,
                "marker": marker,
                "removed_numbers": repeated_numbers,
                "kept_numbers": new_numbers,
            }
        )
        if not new_numbers:
            self.removed_marker_count += 1
            return ""
        self.rewritten_marker_count += 1
        return format_citation_marker(new_numbers)

    def normalize_marker(self, match: re.Match[str], line_number: int) -> str:
        marker = match.group(0)
        numbers = expand_numeric_markers([match.group(1)])
        normalized = format_citation_marker(numbers)
        replaced = self.remove_repeated_numbers(match, line_number)
        if replaced == marker and normalized and marker != normalized:
            self.normalized_marker_count += 1
            return normalized
        return replaced

    def report(self) -> dict[str, object]:
        return {
            "removed_marker_count": self.removed_marker_count,
            "rewritten_marker_count": self.rewritten_marker_count,
            "normalized_marker_count": self.normalized_marker_count,
            "removed_numbers": self.removed_numbers,
            "events": self.events,
        }


def dedupe_repeated_citations(body: str, keep_repeated_citations: bool = False) -> tuple[str, dict[str, object]]:
    lines = body.splitlines()
    protected = markdown_context.protected_line_indexes(lines)
    bounds = reference_section_bounds(lines)
    if bounds:
        protected.update(range(*bounds))
    table_lines = markdown_context.build_table_line_set(lines)
    context = markdown_context.citation_context_lines(lines, protected | table_lines)
    deduplicator = CitationDeduplicator(keep_repeated_citations)
    out_lines: list[str] = []
    for idx, line in enumerate(lines):
        if bounds and idx == bounds[1]:
            deduplicator.seen.clear()
        if idx in protected or idx in table_lines or markdown_context.LINK_DEFINITION_RE.match(line):
            out_lines.append(line)
            continue
        replaced_line = replace_citations_in_line(
            line, lambda match: deduplicator.normalize_marker(match, idx + 1), context[idx],
        )
        if replaced_line != line:
            replaced_line = re.sub(r"[ \t]+([，。；：、,.!?;:])", r"\1", replaced_line)
        out_lines.append(replaced_line)
    deduped_body = "\n".join(out_lines)
    return deduped_body, deduplicator.report()
