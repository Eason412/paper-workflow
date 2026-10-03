---
name: oa-paper-fetch
description: "查找并下载学术论文 PDF（DOI、标题、链接或参考文献列表），先走开放获取，必要时复用你已登录的 IEEE、Wiley、ScienceDirect 会话，支持批量和断点续传。不用于 Sci-Hub 或绕过付费墙。"
---

# OA Paper Fetch

## Purpose and boundaries

Use `oa_fetch.py` only for the requested papers or subset. Match existing
manifests, results and verified PDFs; resume only requested unresolved identities.

- OA first; a verified PDF ends acquisition for that paper.
- Institutional access is limited to entitled IEEE Xplore, Wiley Online Library
  and Elsevier ScienceDirect content; never silently expand the allowlist.
- The user handles credentials and SSO/MFA. Do not read, enter or transfer secrets,
  cookies or storage state, or bypass login, CAPTCHA, paywalls or anti-bot controls;
  never use Sci-Hub or shared credentials.
- Preserve source identity; do not invent metadata or bypass identity failures
  by selecting a similar candidate or switching routes.

## Paths, commands and offline preflight

Resolve `SKILL_DIR` to this file's absolute directory. Adapt Bash syntax to the
actual shell; resolve input/output paths independently of the working directory.

```bash
uv run --project "$SKILL_DIR" python "$SKILL_DIR/oa_fetch.py" --oa-only --doi "10.xxxx/yyyy"
uv run --project "$SKILL_DIR" python "$SKILL_DIR/oa_fetch.py" --oa-only --batch "/absolute/references.csv"
```

These examples force OA-only; authorized fallback is described below.
Choose one selector: `--doi`, `--title`, `--url` or `--batch` (CSV, Markdown
table or line list). Pass `--out` for a specified destination; otherwise use
saved preferences or `~/Desktop/Papers`. More options: `--help`.

For conversation/attachment references, prepare a UTF-8 CSV outside the repository
with `id,title,doi,url`; copy known fields and leave others empty. Each row needs
a title, DOI or URL; report missing identities separately. Reuse supported files.

Normalize and deduplicate offline, without metadata queries or downloads:

```bash
uv run --project "$SKILL_DIR" python "$SKILL_DIR/oa_fetch.py" --batch "/absolute/references.csv" --manifest-out "/absolute/oa_fetch_manifest.csv"
```

Report invalid/duplicate rows, not downloads. `--dry-run` queries candidates
and writes reports, but no PDFs/state/pending or institutional requests.

Plain OA needs no third-party packages. Only authorized institutional setup uses:

```bash
uv sync --project "$SKILL_DIR" --extra institutional
uv run --project "$SKILL_DIR" --extra institutional python -m playwright install chromium
```

## Source identity and blocked papers

Explicit DOI or supported URL anchors identity; metadata cannot substitute
another paper. Do not infer author/year from URLs, journal names or memory.
Title-only input goes to backend confirmation: two independent sources must
corroborate one DOI, not merely the highest-scoring match.

For `title_resolution_ambiguous`, `title_resolution_unresolved`,
`publisher_title_mismatch` or `publisher_title_unverifiable`, retain evidence
and request a DOI, supported article URL or corrected exact title. Do not
download candidates or bypass the decision through another route.

## Preferences and institutional authorization

Precedence: current arguments, saved `~/.oa-paper-fetch/config.json`, defaults.
Use `--save-config` only for an explicit default-setting request, never to save
one-run output, pace or access choices. `--oa-only` overrides saved institutional
access for this run.

For authorized school access use `--institutional` or the authorized saved choice.
CLI institutional runs need
`uv run --project "$SKILL_DIR" --extra institutional python "$SKILL_DIR/oa_fetch.py"`
plus input/output options. Only unresolved eligible OA items enter fallback.
Use existing `UNPAYWALL_EMAIL` without exposing its value in chat or logs.

## Session isolation, login and browser handoff

CLI profile `~/.oa-paper-fetch/profile` is separate from ordinary Chrome;
Chrome login does not prove CLI login. Do not inspect, copy, synchronize,
upload or commit profile contents.

For missing/expired CLI login:

```bash
uv run --project "$SKILL_DIR" --extra institutional python "$SKILL_DIR/oa_fetch.py" --institutional-login
```

The user completes SSO/MFA visibly and presses Enter in the terminal;
do not operate authentication fields. `--headless` only reuses working profiles.

An available browser tool may use the user's authorized session directly.
Read [browser workflow](references/browser-workflow.md) for saving/verification;
validate one paper before continuing. Never transfer authentication to the CLI.

`not_pdf_browser_download_required` means ScienceDirect returned ordinary HTML,
not a PDF or necessarily a login failure. Select it from `institutional.error`
in the result JSON: it is `failed`, not in the pending CSV. With browser
authorization, try the same session's normal PDF flow once, verify and record
the outcome separately. CLI browser-download events are not implemented.

Keep retrieval serial. Institutional limits are minimum 4-second base delay,
jitter 0–10 seconds and 30 attempts per run across both routes. Count interactive
attempts including earlier CLI attempts; route switches or chained runs cannot
reset the cap.

## Resume, stopping decisions and reporting

Same canonical manifest and output directory means resume; verified successes
return `exists`, unresolved items retry. `--overwrite` needs a replacement
request. Let the backend name files; never redownload merely for naming.
Read [recovery and naming](references/recovery-naming.md) for migration,
checkpoints, damaged state or mixed pending reasons.

Persistence failure exits `4`: retain files/state and repair storage before
resume. Never delete/reset unreadable, malformed or unsupported-version state.
The PDF signature gate is lightweight, not full PDF validation.

- Identity block: clarify identity, do not retry unchanged evidence.
- Missing/expired login: visible user refresh before resume. CLI stops after
  three blocks since the last verified PDF; browser challenges stop immediately.
- `institutional_cap_reached`: retain/report pending and await a new request;
  never append institutional batches automatically.
- Rejected URL, redirect or guard: leave unresolved, never retrieve manually
  or disable guards to bypass rejection. Guard errors need transport repair.
- No OA or entitled PDF: preserve failure for manual retrieval.

Inspect stdout JSON and `oa_fetch_results.json`; report counts/paths for
`downloaded`, `exists`, `duplicate`, `failed`, `pending`, unresolved reasons
and relevant naming/storage errors. `candidate` is dry-run evidence, not a
download. Verify renamed paths before claiming success. Exit codes: `0`
resolved/usable preflight, `1` failed/pending, `2` CLI/config error, `3`
unavailable input, `4` transport/persistence failure; early errors may lack JSON.
