# OA Paper Fetch

**English** | [简体中文](README.zh-CN.md)

Paper identity resolution, open-access discovery, and entitled institutional PDF acquisition. Supports exact titles, DOIs, URLs, Markdown, CSV, and line-based lists, with batch processing, browser-session reuse, bibliographic filenames, and resumable failures.

The default output is `~/Desktop/Papers`. CLI version: `0.5.0`. The OA layer requires Python 3.10+ and uses only the standard library.

## Installation and entrypoints

See [Paper Workflow](../../README.md#安装) for installation and shared maintenance. This directory is the complete Skill unit; retain all five Python modules and supporting resources.

From the collection root, enter the Skill directory. Run subsequent commands there:

```bash
cd skills/oa-paper-fetch
python3 oa_fetch.py --help
```

Example Codex request:

```text
Use $oa-paper-fetch to download the papers in this reference list to the requested directory.
Try open access first, then use my configured institutional access for unresolved items.
```

Codex uses [SKILL.md](SKILL.md) as the canonical workflow and `agents/openai.yaml` for Skill metadata. Keep one installation entry pointing to this directory.

## Open-access acquisition

```bash
python3 oa_fetch.py --url "https://arxiv.org/abs/1706.03762" --format text
```

Successful PDFs and reports are saved to the default directory. Use `--out` for one run or `--save-config` to persist an explicitly requested default.

OA candidates include direct PDFs, arXiv, OpenAlex, Unpaywall, and Semantic Scholar. Unpaywall can use an existing local `UNPAYWALL_EMAIL`.

## Batch manifests and identity

CSV fields are shown below; leave unknown values empty:

```csv
id,title,doi,url
ref-001,Exact Full Paper Title,,
ref-002,,10.xxxx/yyyy,
```

Replace the absolute path placeholders with actual input and output locations:

```bash
python3 oa_fetch.py --batch "/absolute/references.csv" --out "/absolute/papers" --format text
```

Markdown tables and one-item-per-line text are also supported. DOI and URL matches are hard duplicates; matching titles alone remain separate possible duplicates. Repeated input IDs receive collision-free suffixes.

Title resolution queries arXiv, Crossref, and OpenAlex. Crossref candidate discovery uses `0.62`; multi-source identity confirmation uses `0.85` and requires at least two independent sources supporting one DOI. Institutional publisher-title verification separately uses `0.93`. One exact match is insufficient. Ambiguous or unresolved identities do not proceed to institutional acquisition.

Offline manifest preflight performs normalization and deduplication only:

```bash
python3 oa_fetch.py --batch "/absolute/references.csv" --manifest-out "/absolute/oa_fetch_manifest.csv"
```

`--manifest-out` requires `--batch` and makes no metadata or PDF requests.

## Browser login and session reuse

### Optional dependencies

Only institutional access requires Playwright and Chromium:

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
```

### Initial login and session refresh

```bash
python3 oa_fetch.py --institutional-login
```

A visible browser opens IEEE Xplore, Wiley Online Library, and Elsevier ScienceDirect. The user selects institutional access and completes SSO/MFA, then presses Enter in the terminal.

The browser persists login state, including browser-managed cookies, in the isolated local `~/.oa-paper-fetch/profile` directory. It does not attach to the daily browser profile. The tool does not inspect or export cookies, enter credentials or verification codes, or bypass access controls. Keep this profile out of Git and synchronized backups.

### Entitled institutional acquisition

```bash
python3 oa_fetch.py --batch "/absolute/references.csv" --out "/absolute/papers" --institutional --format text
```

OA runs first. Only unresolved items with eligible identities enter institutional fallback. Supported publishers are IEEE Xplore, Wiley Online Library, and Elsevier ScienceDirect.

Valid sessions are reusable across runs. `--headless` is for reusing an established valid session; initial login and repair require a visible browser. Missing profiles return `profile_missing_login_required`; expired sessions return `login_refresh_required`.

## Preferences and batch limits

Non-sensitive preferences are stored in `~/.oa-paper-fetch/config.json`. Precedence is explicit run arguments, saved preferences, then built-in defaults. Save standing choices only on user request:

```bash
python3 oa_fetch.py --institutional --inst-delay 4 --inst-jitter 3 --max-institutional 30 --save-config
```

Use `--oa-only` to override institutional fallback for one run. Common options follow; see `--help` for the complete interface:

| Option | Default and range |
| --- | --- |
| `--out` | `~/Desktop/Papers`, or a saved directory |
| `--oa-delay` | 1 second; 0–60 seconds |
| `--timeout` | 30 seconds; 5–300 seconds |
| `--inst-delay` | 4 seconds; 4–86400 seconds |
| `--inst-jitter` | 3 seconds; 0–10 seconds |
| `--max-institutional` | 30 attempts; 1–30 |
| `--browser-profile` | `~/.oa-paper-fetch/profile` |
| `--dry-run` | Candidate discovery and result reports; no PDFs, resume state, or institutional fallback |

Acquisition is serial. The institutional phase stops after three HTTP 4xx, challenge, or login-block responses since the last successful PDF. Reaching the cap returns `institutional_cap_reached`; additional institutional batches are not started automatically.

## State and resume

Rerun the same manifest in the same output directory to resume. Verified files return `exists`; missing or invalid files are fetched again. Download and resume use the same lightweight validation: more than 5 bytes and a `%PDF` prefix.

Filenames follow `year_first-author_full-title_stable-hash.pdf`, retaining an 8-character identity suffix and a 240-byte UTF-8 limit. Naming migrations use a non-overwriting hard link and persisted state; failures retain the original file.

`oa_fetch_pending.csv` is generated when explicit continuation is needed. Refresh expired login before resuming; wait for a new continuation request after reaching the cap:

```bash
python3 oa_fetch.py --batch "/absolute/papers/oa_fetch_pending.csv" --out "/absolute/papers" --institutional
```

Run one job at a time per output directory. Structurally invalid or unsupported-version state files remain unchanged and produce exit `4`, rather than being silently reset.

| Status / reason | Meaning or action |
| --- | --- |
| `candidate` | Dry-run candidate; not downloaded |
| `downloaded` / `exists` | Acquired this run / existing file verified |
| `duplicate` | Duplicate DOI or URL |
| `failed` / `pending` | Failed acquisition / further action needed |
| `title_resolution_ambiguous` | Conflicting candidate DOIs; clarify identity |
| `title_resolution_unresolved` | Supply a DOI, article URL, or exact title |
| `publisher_title_mismatch` | Publisher title differs from the expected title |
| `publisher_title_unverifiable` | Publisher page lacks a verifiable title |
| `profile_missing_login_required` / `login_refresh_required` | Initial login / session refresh |
| `institutional_cap_reached` | Institutional attempt cap reached |

## Outputs and exit codes

Normal paper runs reaching final reporting emit one JSON payload to stdout; progress goes to stderr. Help, version, and visible login use interactive text. Early failures may exit before JSON is produced.

Outputs include PDFs, `oa_fetch_manifest.csv`, `oa_fetch_results.json`, `oa_fetch_results.csv`, `oa_fetch_state.json`, and conditional `oa_fetch_pending.csv`. Reports preserve identity resolution, candidates, acquisition attempts, and failure reasons.

Exit codes: `0` success or usable preflight; `1` failed/pending items; `2` invalid arguments/configuration; `3` missing, empty, or unusable input; `4` transport or persistence failure.

## Development and feedback

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile oa_fetch.py institutional_fetch.py config.py manifest.py store.py
python3 oa_fetch.py --version
```

Offline tests use temporary directories and mocked responses. Real institutional login and downloads require the user's authorized environment. See [AGENTS.md](AGENTS.md) for maintenance rules and [SKILL.md](SKILL.md) for the download workflow.

Submit issues and PRs to [Paper Workflow](https://github.com/Eason412/paper-workflow/issues) with a minimal reproduction, expected/actual results, and redacted logs. License: [MIT](LICENSE).
