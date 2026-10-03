# Recovery, naming and identity evidence

Read this for filename migrations, interrupted runs, damaged state, identity
evidence or mixed pending reasons. Ordinary downloads use the backend directly.

## Filenames and metadata

The backend names PDFs `year_first-author_full-title_stable-hash.pdf`. The
canonical identity supplies an 8-character suffix, retained even with complete
metadata; filenames are limited to 240 UTF-8 bytes. Do not rename them manually.

Exact arXiv Atom records provide title, publication year and first author for
arXiv URLs/DOIs. Entitled publisher pages provide `citation_title`, first
`citation_author`, publication date and DOI. When an expected title exists,
a missing/normalization-empty page title is `publisher_title_unverifiable` and
a disagreement is `publisher_title_mismatch`; neither requests a PDF. Preserve
a rejected page title as `citation_title`, not as the task's expected `title`.

An explicit DOI/URL without an expected title is not blocked merely by missing
bibliographic fields. Use non-invented fallbacks: known title, arXiv ID, DOI,
PII/IEEE document ID or URL basename. A different existing target is never
overwritten: report `filename_error` and retain the PDF at its existing name.

## Identity and manifest evidence

The backend assigns missing IDs and resolves suffix collisions. DOI/URL matches
are hard duplicates; equal title-only rows are flagged, not merged. Source-derived
titles for anchored DOI/arXiv/publisher records may fill empty manifest titles.
Resolved DOI values and candidate evidence remain in result/state files, not
rewritten as original input DOI values.

Title resolution queries arXiv, Crossref and OpenAlex. Two independent sources
must support one DOI with strong title agreement; one exact match is insufficient.
An exact-title `10.48550/arXiv.*` DOI can alias a publisher DOI only with that
publisher DOI independently corroborated by two sources. Preserve the arXiv OA
URL and alias; two publisher DOIs always conflict. Lower similarity thresholds
are discovery only. Candidate title, DOI, source, score, year and first author
remain in JSON. Do not use an accompanying URL to bypass blocked resolution.

## PDF verification and migrations

Downloads and resume use the same lightweight check: a `%PDF` prefix and more
than five bytes. This rejects HTML and empty/truncated signatures, not arbitrary
invalid PDF structure. The 80 MiB limit is a file-size check, not a hard transfer
memory limit; institutional responses are disposed individually.

Old state without the current naming version may make one metadata-only refresh.
Verify the old PDF, create the new name via a non-overwriting same-directory hard
link, persist state, then remove the old name. A failed state write rolls back the
new link and retains the old PDF. A resumed same-inode migration may finish; a
different target never replaces the source. Without hard-link support, retain
the old name and report the migration error, not a copying/deleting fallback.
`renamed_from` means migration, not another download. Later resumes return
`exists` without another metadata lookup.

## State and checkpoints

Institutional results are checkpointed individually after metadata and filename
processing. After interruption, reuse completed checkpoints. A checkpoint-write
failure stops subsequent institutional requests and exits `4`; retain persisted
state and original files, repair storage, then resume. Do not reset state.

Unreadable, malformed or unsupported-version state exits `4` without replacing
the state file. Valid older records missing newer optional fields remain usable.
Use one writer per output directory. PDF, manifest, configuration, state and
reports use atomic writes; default sensitive local directories stay outside Git.

## Pending and transport decisions

Report pending rows and reasons. Login reasons require a visible refresh and user
confirmation; identity reasons require clarified identity. The cap requires a new
continuation request. If one pending CSV mixes login-refresh and cap reasons,
refresh login first, then rerun that same CSV once after confirmation; splitting
is unnecessary and the new run still has a 30-attempt cap. Do not append runs
automatically or retry an unchanged identity failure.

`publisher_not_allowed` does not expand scope. `unsafe_landing_redirect` and
`unsafe_pdf_url` prohibit manual retrieval of the rejected target.
`landing_guard_error` remains failed and exits `4`: repair Playwright/Chromium
with authorization, never disable the guard. Repeated landing/PDF HTTP 4xx or
login/challenge responses require visible login repair; do not loop credentials.
The authorized browser handoff is described separately in
[browser workflow](browser-workflow.md); it is not a guard bypass.

## Output and evidence

Outputs are PDFs, `oa_fetch_manifest.csv`, `oa_fetch_results.json`,
`oa_fetch_results.csv`, `oa_fetch_state.json`, and conditional
`oa_fetch_pending.csv`. Dry-run writes manifest/results but no PDFs, state or
pending file; an existing pending file remains untouched. Progress goes to
stderr, final result JSON to stdout; help, version and login use text.

When relevant report `renamed_from`, `filename_error` and
`filename_metadata_error`, and verify the reported path. JSON preserves the
full `title_resolution` object; flat CSV exposes `title_resolution_status`,
`title_resolution_reason` and `resolved_doi`. Publisher evidence includes
`expected_title`, `citation_title`, `publisher_title_match` and
`publisher_title_score`. Detailed candidates stay in JSON, not the flat CSV.
