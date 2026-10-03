"""Paper identifiers, comparable titles, and metadata-derived filenames."""
from __future__ import annotations

import difflib
import html
import re
import urllib.parse
from pathlib import Path

import manifest as manifest_tools
import store

DOI_RE = manifest_tools.DOI_RE
ARXIV_ID_PATTERN = r"(?:\d{4}\.\d{4,5}|[a-z][a-z0-9.-]*/\d{7})(?:v\d+)?"
ARXIV_RE = re.compile(
    rf"(?:https?://(?:export\.)?arxiv\.org/(?:abs|pdf)/|arxiv\s*:\s*)"
    rf"(?P<id>{ARXIV_ID_PATTERN})(?:\.pdf)?",
    re.I,
)
ARXIV_ID_RE = re.compile(rf"^{ARXIV_ID_PATTERN}$", re.I)


def normalize_title(text: str) -> str:
    return manifest_tools.normalize_title(text)


def _comparison_title(text: str | None) -> str:
    value = html.unescape(str(text or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    return normalize_title(value)


def title_score(a: str, b: str) -> float:
    return difflib.SequenceMatcher(
        None, _comparison_title(a), _comparison_title(b)
    ).ratio()


def extract_doi(text: str | None) -> str | None:
    return manifest_tools.extract_doi(text)


def extract_arxiv_id(text: str | None) -> str | None:
    if not text:
        return None
    value = str(text).strip()
    match = ARXIV_RE.search(value)
    if match:
        return match.group("id")
    doi_match = re.search(rf"10\.48550/arxiv\.(?P<id>{ARXIV_ID_PATTERN})", value, re.I)
    if doi_match:
        return doi_match.group("id")
    value = re.sub(r"\.pdf$", "", value, flags=re.I)
    match = ARXIV_ID_RE.fullmatch(value)
    if not match:
        return None
    return match.group(0)


def extract_arxiv_pdf(text: str | None) -> str | None:
    arxiv_id = extract_arxiv_id(text)
    if not arxiv_id:
        return None
    return f"https://arxiv.org/pdf/{arxiv_id}.pdf"


def _arxiv_base_id(arxiv_id: str) -> str:
    return re.sub(r"v\d+$", "", arxiv_id, flags=re.I)


def clean_filename(text: str, max_len: int = 150) -> str:
    text = re.sub(r"[\\/:*?\"<>|]+", "_", text)
    text = re.sub(r"\s+", "_", text.strip())
    text = re.sub(r"_+", "_", text).strip("._")
    return (text or "paper")[:max_len]


def metadata_filename(
    meta: dict, fallback: str, canonical_id: str | None = None
) -> str:
    if canonical_id:
        return store.build_filename(meta, fallback, canonical_id)
    year = str(meta.get("year") or "unknown")
    title = meta.get("title") or fallback or "paper"
    first_author = meta.get("first_author") or "unknown"
    suffix = ".pdf"
    stem = clean_filename(
        f"{year}_{first_author}_{title}", max_len=store.MAX_FILENAME_BYTES
    )
    available = store.MAX_FILENAME_BYTES - len(suffix.encode("utf-8"))
    if len(stem.encode("utf-8")) > available:
        stem = (
            stem.encode("utf-8")[:available]
            .decode("utf-8", "ignore")
            .rstrip("._")
            or "paper"
        )
    return stem + suffix


def _merge_metadata(preferred: dict | None, fallback: dict | None) -> dict:
    """Merge non-empty metadata while keeping ``preferred`` authoritative."""
    merged = {
        key: value
        for key, value in (fallback or {}).items()
        if value not in (None, "")
    }
    for key, value in (preferred or {}).items():
        if value not in (None, ""):
            merged[key] = value
    return merged


def filename_fallback(item: dict, meta: dict | None = None) -> str:
    """Return the most descriptive stable fallback available without guessing."""
    meta = meta or {}
    for value in (meta.get("title"), item.get("title")):
        if value:
            return str(value)
    arxiv_id = extract_arxiv_id(meta.get("url")) or extract_arxiv_id(item.get("url"))
    if arxiv_id:
        return f"arXiv_{arxiv_id.replace('/', '_')}"
    doi = meta.get("doi") or item.get("doi")
    if doi:
        return f"DOI_{doi}"
    url = meta.get("url") or item.get("url")
    if url:
        parsed = urllib.parse.urlsplit(str(url))
        path = urllib.parse.unquote(parsed.path).rstrip("/")
        ieee = re.search(r"/document/(\d+)$", path, re.I)
        elsevier = re.search(r"/pii/([A-Z0-9]+)(?:/.*)?$", path, re.I)
        if ieee:
            return f"IEEE_{ieee.group(1)}"
        if elsevier:
            return f"Elsevier_{elsevier.group(1)}"
        basename = Path(path).name
        basename = re.sub(r"\.pdf$", "", basename, flags=re.I)
        if basename:
            return basename
        if parsed.hostname:
            return parsed.hostname
    return str(item.get("id") or "paper")


def _author_family(name: str | None) -> str | None:
    value = re.sub(r"\s+", " ", str(name or "")).strip()
    if not value:
        return None
    if "," in value:
        return value.split(",", 1)[0].strip() or None
    return value.split()[-1] or None
