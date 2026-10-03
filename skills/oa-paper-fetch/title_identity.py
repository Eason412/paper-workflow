"""Confirm title identities from independent sources and auditable arXiv aliases."""
from __future__ import annotations

import manifest as manifest_tools
import oa_sources
import paper_metadata

TITLE_CONFIRM_MIN_SCORE = 0.85


def _title_resolution_candidate(
    source: str, found: dict | None, input_title: str
) -> dict | None:
    if not found:
        return None
    candidate_title = str(found.get("title") or "").strip()
    doi = manifest_tools.normalize_doi(found.get("doi"))
    raw_score = found.get("score")
    try:
        score = float(raw_score) if raw_score is not None else None
    except (TypeError, ValueError):
        score = None
    if score is None and candidate_title:
        score = paper_metadata.title_score(input_title, candidate_title)
    return {
        "source": source,
        "doi": doi,
        "title": candidate_title or None,
        "score": score,
        "year": found.get("year"),
        "first_author": found.get("first_author"),
        "urls": list(found.get("urls") or []),
    }


def _is_exact_arxiv_alias(candidate: dict, input_title: str) -> bool:
    doi = str(candidate.get("doi") or "")
    return (
        candidate.get("source") == "arxiv_title"
        and doi.startswith("10.48550/arxiv.")
        and (
            paper_metadata._comparison_title(candidate.get("title"))
            == paper_metadata._comparison_title(input_title)
        )
    )


def resolve_title_identity(title: str, timeout: int) -> dict:
    """Resolve a title to one DOI only when independent evidence is safe."""
    candidates, lookup_evidence = _collect_title_evidence(title, timeout)
    identity_qualified, accepted_alias_dois = _group_title_identities(candidates, title)
    status, reason, selected_doi, selected = _select_title_identity(
        identity_qualified, candidates, title
    )
    return {
        "status": status,
        "reason": reason,
        "input_title": title,
        "selected_doi": selected_doi,
        "accepted_alias_dois": accepted_alias_dois,
        "selected": selected,
        "candidates": candidates,
        "lookups": lookup_evidence,
    }


def _collect_title_evidence(title: str, timeout: int):
    lookups = (
        ("arxiv_title", oa_sources.arxiv_title_lookup(title, timeout)),
        ("crossref_title", oa_sources.crossref_title_to_doi(title, timeout)),
        ("openalex_title", oa_sources.openalex_lookup(None, title, timeout)),
    )
    candidates = []
    lookup_evidence = []
    for source, found in lookups:
        candidate = _title_resolution_candidate(source, found, title)
        lookup_evidence.append({
            "source": source,
            "result": candidate is not None,
            "score": candidate.get("score") if candidate else None,
            "doi": candidate.get("doi") if candidate else None,
            "title": candidate.get("title") if candidate else None,
        })
        if candidate:
            candidates.append(candidate)
    return candidates, lookup_evidence


def _group_title_identities(candidates: list[dict], title: str):
    qualified: dict[str, list[dict]] = {}
    for candidate in candidates:
        candidate_doi = candidate.get("doi")
        candidate_score = candidate.get("score")
        if (
            candidate_doi
            and candidate_score is not None
            and candidate_score >= TITLE_CONFIRM_MIN_SCORE
        ):
            qualified.setdefault(candidate_doi, []).append(candidate)

    # An arXiv repository DOI and the later publisher DOI can identify the
    # same exact-title work. Treat the arXiv DOI as an auditable alias only
    # when at least two independent sources corroborate one publisher DOI.
    # One source is not enough, and multiple publisher DOIs always conflict.
    identity_qualified = qualified
    accepted_alias_dois: list[str] = []
    if len(qualified) > 1:
        arxiv_aliases = {
            candidate_doi: group
            for candidate_doi, group in qualified.items()
            if all(_is_exact_arxiv_alias(candidate, title) for candidate in group)
        }
        publisher_groups = {
            candidate_doi: group
            for candidate_doi, group in qualified.items()
            if candidate_doi not in arxiv_aliases
        }
        if len(publisher_groups) == 1 and len(arxiv_aliases) == len(qualified) - 1:
            publisher_group = next(iter(publisher_groups.values()))
            if len({candidate["source"] for candidate in publisher_group}) >= 2:
                identity_qualified = publisher_groups
                accepted_alias_dois = sorted(arxiv_aliases)
    return identity_qualified, accepted_alias_dois


def _select_title_identity(identity_qualified: dict, candidates: list[dict], title: str):
    status = "unresolved"
    reason = "no_candidates"
    selected_doi = None
    selected = None
    if len(identity_qualified) > 1:
        status = "ambiguous"
        reason = "conflicting_dois"
    elif len(identity_qualified) == 1:
        only_doi, group = next(iter(identity_qualified.items()))
        exact = any(
            paper_metadata._comparison_title(candidate.get("title"))
            == paper_metadata._comparison_title(title)
            for candidate in group
        )
        independent_sources = {candidate["source"] for candidate in group}
        if len(independent_sources) >= 2:
            status = "confirmed"
            reason = "exact_title" if exact else "multiple_sources_same_doi"
        else:
            status = "ambiguous"
            reason = "insufficient_confirmation"
        if status == "confirmed":
            selected_doi = only_doi
            selected = max(
                group, key=lambda candidate: candidate.get("score") or 0.0
            )
    elif candidates:
        status = "ambiguous"
        reason = "insufficient_confirmation"
    return status, reason, selected_doi, selected
