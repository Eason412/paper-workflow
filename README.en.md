# Paper Workflow

[中文](README.md) | English

**Task-specific Skills for paper acquisition, course reports, and research charts.** This repository contains three academic Agent Skills: `oa-paper-fetch`, `course-report`, and `paper-figure`. A Skill is a task specification defined in `SKILL.md`, optionally accompanied by scripts, templates, and references.

> ⚠️ Dependencies vary by task. Institutional full-text access requires existing entitlement and personal authentication by the user. Paper acquisition does not support Sci-Hub or paywall bypasses.

Writing and documentation Skills are maintained in the sister repository [doc-workflow](https://github.com/Eason412/doc-workflow) (Chinese).

## ✨ Features

- 📚 **OA-first acquisition with resumable batch downloads**: Accept DOIs, titles, links, and reference lists; download open-access PDFs first, reuse signed-in IEEE, Wiley, or ScienceDirect sessions when needed, and reuse verified downloads.
- 🖨️ **Complete course report layout**: Convert course reports written in Chinese Markdown into PDFs with covers, abstracts, contents, numbered figures, tables, and equations, and a reference list, with Markdown and LaTeX structural checks and a final inspection workflow.
- 📊 **Argument-driven research charts**: Select charts around the research argument and data structure, with journal dimensions, readable type, Chinese fonts, colorblind-safe palettes, vector exports, and rendered visual inspection.

## 🧩 Skill Catalog

| Skill | Purpose | Entry Points |
| --- | --- | --- |
| `oa-paper-fetch` | Open access, entitled full text, batches, and resumption | [Task specification](skills/oa-paper-fetch/SKILL.md) · [Chinese guide](skills/oa-paper-fetch/README.zh-CN.md) · [English guide](skills/oa-paper-fetch/README.md) |
| `course-report` | PDF layout and checks for Chinese course reports | [Task specification (Chinese)](skills/course-report/SKILL.md) · [User guide (Chinese)](skills/course-report/README.md) |
| `paper-figure` | Chart selection, dimensions, and export checks | [Task specification (Chinese)](skills/paper-figure/SKILL.md) · [Chart selection (Chinese)](skills/paper-figure/references/chart_selection.md) |

Each `skills/<name>` directory is a complete installation unit with its runtime resources. Codex, Claude Code, and other Agents supporting `SKILL.md` can use these specifications; the host provides script execution, browser control, and image inspection capabilities.

`course-report` targets course reports and assignments; its thesis-style option adapts only the cover field layout. `paper-figure` targets data charts; schematic, flow, and architecture diagrams are outside its scope.

## 🛠️ Runtime Requirements

| Skill | Base Requirements | Conditional Requirements |
| --- | --- | --- |
| `oa-paper-fetch` | uv, Python 3.12+; OA uses the standard library | Institutional CLI: Playwright 1.40+, Chrome or Chromium; existing session: browser-control tool |
| `course-report` | uv, Python 3.10+, Pandoc; no third-party Python packages | PDF: Tectonic or XeLaTeX, Latin and Chinese fonts; additional QA: Poppler, qpdf |
| `paper-figure` | uv, Python, matplotlib, seaborn, image inspection tool | Chinese charts: Chinese fonts; PDF font checks: `pdffonts` |

The standalone OA script in `oa-paper-fetch` supports Python 3.10+, while its uv project requires Python 3.12+. `course-report` needs Pandoc even for LaTeX-only output; it prefers Tectonic when both compilers are available, and the first compilation may download TeX resources. `paper-figure` declares no fixed Python or plotting-library versions. Dependency sources and validation steps are in [SETUP.md](SETUP.md).

## 🚀 Setup

An Agent should read [SETUP.md](SETUP.md) to complete installation and the required dependency checks. Open a new Agent session afterward and confirm Skill discovery. The user personally completes institutional account login, single sign-on, and multi-factor authentication.

| Setting | Location | Purpose |
| --- | --- | --- |
| Paper output and access preferences | `~/.oa-paper-fetch/config.json`, CLI arguments | Default output, access mode, and per-task choices |
| Report cover and citations | Source Markdown metadata, build arguments | Course, name, student ID, cover mode, and citation retention |
| Chart specifications | Task request, plotting code | Research argument, journal, dimensions, fonts, and output format |

## 📁 Repository Structure

| Path | Purpose |
| --- | --- |
| `skills/<name>/SKILL.md` | Task entry point for each Skill |
| `skills/<name>/agents/openai.yaml` | Codex display metadata |
| `skills/<name>/references/` | Workflow, layout, and chart-selection references |
| `skills/course-report/scripts/`, `assets/`, `examples/` | Report builds, templates, and samples |
| `skills/oa-paper-fetch/*.py` | Acquisition, identity resolution, configuration, and recovery state |
| `skills/<name>/tests/` (where present), `tests/` | Skill regressions and repository hygiene checks |
| [scripts/link-skills.sh](scripts/link-skills.sh) | Link installation for personal Skill entries |
| [SETUP.md](SETUP.md) | Agent setup and validation manual |
| [AGENTS.md](AGENTS.md), [CONTRIBUTING.md](CONTRIBUTING.md) | Project rules and contribution requirements (Chinese) |
| [.github/workflows/](.github/workflows/) | Paper-fetch regression and report PDF build configurations |

The author edits Skills directly in the local checkout, then validates, commits, and pushes changes. Linked installations share this source with personal Skill entries. Rerun the installation script after adding a Skill.

## 🤝 Contributions

PRs should address one problem and include the affected Skill, a minimal reproduction, expected and actual results, and validation records. Behavioral changes require matching tests and documentation. Remove personal and authentication data from samples and logs, and preserve Skill licenses and third-party attribution. Full requirements are in [CONTRIBUTING.md (Chinese)](CONTRIBUTING.md).

## 📄 Licensing and Attribution

Licenses are defined by files within individual Skill directories. There is no collection-wide root `LICENSE`.

| Skill | License | Copyright Attribution |
| --- | --- | --- |
| `oa-paper-fetch` | [MIT](skills/oa-paper-fetch/LICENSE) | Eason412 |
| `course-report` | [MIT](skills/course-report/LICENSE) | Eason412 |
| `paper-figure` | [MIT](skills/paper-figure/LICENSE) | Haojae |

The `course-report` emblem and official formatting materials are covered separately in [THIRD_PARTY_NOTICES.md](skills/course-report/THIRD_PARTY_NOTICES.md). Rights to those names, marks, and materials remain with their respective rightsholders.
