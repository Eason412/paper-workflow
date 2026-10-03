"""Query OA metadata providers and preserve their candidate URL ordering."""
from __future__ import annotations

import os
import re
import urllib.parse
import xml.etree.ElementTree as ET

import manifest as manifest_tools
import oa_transport
import paper_metadata

CROSSREF_TITLE_MIN_SCORE = 0.62


def crossref_title_to_doi(title: str, timeout: int) -> dict | None:
    query = urllib.parse.urlencode({"query.title": title, "rows": "5"})
    data = oa_transport.request_json(f"https://api.crossref.org/works?{query}", timeout)
    items = (((data or {}).get("message") or {}).get("items") or [])
    best = None
    for item in items:
        candidate_title = " ".join(item.get("title") or [])
        doi = item.get("DOI")
        if not candidate_title or not doi:
            continue
        score = paper_metadata.title_score(title, candidate_title)
        candidate = {
            "doi": manifest_tools.normalize_doi(doi),
            "title": candidate_title,
            "score": score,
            "year": (((item.get("published-print") or item.get("published-online") or {}).get("date-parts") or [[None]])[0][0]),
            "first_author": ((item.get("author") or [{}])[0].get("family")),
            "url": item.get("URL"),
        }
        if best is None or score > best["score"]:
            best = candidate
    return best if best and best["score"] >= CROSSREF_TITLE_MIN_SCORE else None


def _arxiv_entry_metadata(entry: ET.Element) -> dict:
    ns = {"a": "http://www.w3.org/2005/Atom"}
    found_title = re.sub(
        r"\s+",
        " ",
        entry.findtext("a:title", default="", namespaces=ns) or "",
    ).strip()
    found_id = entry.findtext("a:id", default="", namespaces=ns) or ""
    arxiv_id = paper_metadata.extract_arxiv_id(found_id)
    if not arxiv_id:
        return {}
    authors = entry.findall("a:author", ns)
    first_author = None
    if authors:
        first_author = paper_metadata._author_family(
            authors[0].findtext("a:name", default="", namespaces=ns)
        )
    published = entry.findtext("a:published", default="", namespaces=ns) or ""
    year = int(published[:4]) if re.fullmatch(r"\d{4}", published[:4]) else None
    published_doi = entry.findtext(
        "{http://arxiv.org/schemas/atom}doi", default=""
    )
    doi = paper_metadata.extract_doi(published_doi) or f"10.48550/arXiv.{paper_metadata._arxiv_base_id(arxiv_id)}"
    urls = []
    for link in entry.findall("a:link", ns):
        href = link.get("href") or ""
        if not href:
            continue
        if link.get("title") == "pdf" or link.get("type") == "application/pdf":
            parsed = urllib.parse.urlsplit(href)
            if (parsed.hostname or "").lower() in {"arxiv.org", "export.arxiv.org"}:
                path = parsed.path
                if path.startswith("/pdf/") and not path.lower().endswith(".pdf"):
                    path += ".pdf"
                href = urllib.parse.urlunsplit(("https", "arxiv.org", path, parsed.query, ""))
            urls.append(href)
    if not urls:
        urls.append(f"https://arxiv.org/pdf/{arxiv_id}.pdf")
    return {
        "title": found_title or None,
        "doi": doi,
        "year": year,
        "first_author": first_author,
        "urls": urls,
        "arxiv_id": arxiv_id,
    }


def arxiv_id_lookup(arxiv_id: str | None, timeout: int) -> dict:
    if not arxiv_id:
        return {}
    root = oa_transport._request_arxiv_feed({"id_list": arxiv_id}, timeout)
    if root is None:
        return {}
    ns = {"a": "http://www.w3.org/2005/Atom"}
    requested = paper_metadata._arxiv_base_id(arxiv_id).casefold()
    for entry in root.findall("a:entry", ns):
        candidate = _arxiv_entry_metadata(entry)
        found = candidate.get("arxiv_id")
        if found and paper_metadata._arxiv_base_id(found).casefold() == requested:
            candidate["score"] = 1.0
            return candidate
    return {}


def arxiv_title_lookup(title: str | None, timeout: int) -> dict:
    if not title:
        return {}
    root = oa_transport._request_arxiv_feed(
        {
            "search_query": f'all:"{title}"',
            "start": "0",
            "max_results": "5",
        },
        timeout,
    )
    if root is None:
        return {}
    ns = {"a": "http://www.w3.org/2005/Atom"}
    best = None
    for entry in root.findall("a:entry", ns):
        candidate = _arxiv_entry_metadata(entry)
        score = paper_metadata.title_score(title, candidate.get("title") or "")
        if score < 0.55:
            continue
        candidate["score"] = score
        if best is None or score > best["score"]:
            best = candidate
    return best or {}


def openalex_lookup(doi: str | None, title: str | None, timeout: int) -> dict:
    score = None
    if doi:
        encoded = urllib.parse.quote(f"https://doi.org/{doi}", safe="")
        url = f"https://api.openalex.org/works/{encoded}"
    elif title:
        query = urllib.parse.urlencode({"search": title, "per-page": "3"})
        url = f"https://api.openalex.org/works?{query}"
    else:
        return {}
    data = oa_transport.request_json(url, timeout)
    if not data:
        return {}
    if "results" in data:
        best = None
        for item in data.get("results") or []:
            score = paper_metadata.title_score(title or "", item.get("title") or "")
            if best is None or score > best[0]:
                best = (score, item)
        if not best or best[0] < 0.55:
            return {}
        score = best[0]
        data = best[1]
    authorships = data.get("authorships") or []
    first_author = None
    if authorships:
        first_author = paper_metadata._author_family(
            (authorships[0].get("author") or {}).get("display_name")
        )
    urls = _openalex_urls(data)
    return {
        "doi": manifest_tools.normalize_doi(data.get("doi")) or doi,
        "title": data.get("title") or title,
        "year": data.get("publication_year"),
        "first_author": first_author,
        "urls": urls,
        "score": score,
    }


def _openalex_urls(data: dict) -> list[str]:
    urls = []
    locations = []

    def add_location(location: dict | None) -> None:
        if location and location.get("is_oa") is not False:
            locations.append(location)

    add_location(data.get("best_oa_location"))
    # OpenAlex's primary location is the version-of-record location, not
    # necessarily an OA copy.  Do not turn an explicitly closed work into a
    # sequence of predictable paywall/landing-page requests.  Missing
    # ``is_oa`` remains backward compatible with older or mocked responses.
    open_access = data.get("open_access") or {}
    if open_access.get("is_oa") is not False:
        add_location(data.get("primary_location"))
    # Prefer actual PDF endpoints across locations before trying a landing
    # page fallback.  A landing page can still expose a public PDF, but it is
    # a slower and less reliable candidate than an advertised PDF URL.
    for url_key in ("pdf_url", "landing_page_url"):
        for loc in locations:
            u = loc.get(url_key)
            if u and u not in urls:
                urls.append(u)
    oa_url = open_access.get("oa_url")
    if open_access.get("is_oa") is not False and oa_url and oa_url not in urls:
        urls.append(oa_url)
    return urls

def unpaywall_lookup(doi: str, timeout: int) -> dict:
    email = os.environ.get("UNPAYWALL_EMAIL", "").strip()
    if not email:
        return {"skipped": "UNPAYWALL_EMAIL not set"}
    encoded = urllib.parse.quote(doi, safe="")
    data = oa_transport.request_json(f"https://api.unpaywall.org/v2/{encoded}?email={urllib.parse.quote(email)}", timeout)
    if not data:
        return {}
    urls = []
    locations = [data.get("best_oa_location") or {}]
    locations.extend(data.get("oa_locations") or [])
    # Unpaywall documents ``url_for_pdf`` as the direct PDF copy and ``url``
    # as a landing-page fallback.  Try every direct copy before page URLs so a
    # stale landing page cannot delay a usable repository PDF.
    for url_key in ("url_for_pdf", "url"):
        for loc in locations:
            u = loc.get(url_key)
            if u and u not in urls:
                urls.append(u)
    z_authors = data.get("z_authors") or []
    first_author = None
    if z_authors:
        first_author = z_authors[0].get("family") or z_authors[0].get("given")
    return {
        "title": data.get("title"),
        "year": data.get("year"),
        "first_author": first_author,
        "urls": urls,
    }


def semantic_scholar_lookup(doi: str, timeout: int) -> dict:
    encoded = urllib.parse.quote(f"DOI:{doi}", safe=":")
    fields = "title,year,authors,openAccessPdf,externalIds,url"
    data = oa_transport.request_json(f"https://api.semanticscholar.org/graph/v1/paper/{encoded}?fields={fields}", timeout)
    if not data:
        return {}
    urls = []
    oa = data.get("openAccessPdf") or {}
    if oa.get("url"):
        urls.append(oa["url"])
    arxiv = (data.get("externalIds") or {}).get("ArXiv")
    if arxiv:
        urls.append(f"https://arxiv.org/pdf/{arxiv}.pdf")
    authors = data.get("authors") or []
    first_author = None
    if authors:
        first_author = paper_metadata._author_family(authors[0].get("name"))
    return {
        "title": data.get("title"),
        "year": data.get("year"),
        "first_author": first_author,
        "urls": urls,
    }
