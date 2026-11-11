# Paper Workflow

[中文](README.md) | English

**Task-specific Skills for paper acquisition, research charts, and Chinese paper writing.** This repository contains three academic Agent Skills: `oa-paper-fetch`, `paper-figure`, and `paper-writing-zh`. A Skill is a task specification defined in `SKILL.md`, optionally accompanied by scripts and references.

Latest published release: [V0.1.0](https://github.com/Eason412/paper-workflow/releases/tag/V0.1.0) ([all versions and release notes](https://github.com/Eason412/paper-workflow/releases)); the `main` branch includes subsequent additions and removals. The former course-report layout Skill `course-report` has been archived; its complete contents remain in [release V0.1.0](https://github.com/Eason412/paper-workflow/tree/V0.1.0/skills/course-report).

> ⚠️ Dependencies vary by task. Institutional full-text access requires existing entitlement and personal authentication by the user. Paper acquisition does not support Sci-Hub or paywall bypasses.

Paper writing belongs in this repository; other writing and documentation Skills are maintained in the sister repository [doc-workflow](https://github.com/Eason412/doc-workflow) (Chinese).

## ✨ Features

- 📚 **OA-first acquisition with resumable batch downloads**: Accept DOIs, titles, links, and reference lists; download open-access PDFs first, reuse signed-in IEEE, Wiley, or ScienceDirect sessions when needed, and reuse verified downloads.
- 📊 **Argument-driven research charts**: Select charts around the research argument and data structure, with journal dimensions, readable type, Chinese fonts, colorblind-safe palettes, vector exports, and rendered visual inspection.
- ✍️ **Fact-preserving Chinese paper writing and revision**: Cover sentence collocations, topic-sentence flow, figure and table discussion, and front or back matter, with a fact-comparison script that checks numbers, citations, symbols, punctuation, and bilingual abstract figures after edits.

## 🧩 Skill Catalog

| Skill | Purpose | Entry Points |
| --- | --- | --- |
| `oa-paper-fetch` | Open access, entitled full text, batches, and resumption | [Task specification](skills/oa-paper-fetch/SKILL.md) · [Chinese guide](skills/oa-paper-fetch/README.zh-CN.md) · [English guide](skills/oa-paper-fetch/README.md) |
| `paper-figure` | Chart selection, dimensions, and export checks | [Task specification (Chinese)](skills/paper-figure/SKILL.md) · [Chart selection (Chinese)](skills/paper-figure/references/chart_selection.md) |
| `paper-writing-zh` | Drafting, revising, and fact-checking Chinese research and review papers | [Task specification (Chinese)](skills/paper-writing-zh/SKILL.md) · [Sentences and collocations (Chinese)](skills/paper-writing-zh/references/sentence.md) |

- **Standalone installation**: Each `skills/<name>` directory is a complete installation unit with its runtime resources.
- **Hosts**: Codex, Claude Code, and other Agents supporting `SKILL.md` can use these specifications; the host provides script execution, browser control, and image inspection capabilities.
- **Scope**: `paper-figure` targets data charts, and schematic, flow, and architecture diagrams are outside its scope; `paper-writing-zh` targets Chinese research papers, review papers, and theses, while non-paper Chinese writing belongs in `doc-workflow`.

## 🛠️ Runtime Requirements

| Skill | Base Requirements | Conditional Requirements |
| --- | --- | --- |
| `oa-paper-fetch` | uv, Python 3.12+; OA uses the standard library | Institutional CLI: Playwright 1.40+, Chrome or Chromium; existing session: browser-control tool |
| `paper-figure` | uv, Python, matplotlib, seaborn, image inspection tool | Chinese charts: Chinese fonts; PDF font checks: `pdffonts` |
| `paper-writing-zh` | Agent; text specification needs no extra packages | Revision fact-check script: uv, Python 3.9+ (standard library only) |

- **Python versions**: The standalone OA script in `oa-paper-fetch` supports Python 3.10+, while its uv project requires Python 3.12+; the fact-check script in `paper-writing-zh` uses the standard library only; `paper-figure` declares no fixed Python or plotting-library versions.
- **Dependency sources**: Dependency sources and validation steps are in [SETUP.md](SETUP.md).

## 🚀 Setup

- **Setup**: An Agent reads [SETUP.md](SETUP.md) to complete installation and the required dependency checks.
- **Afterward**: A new Agent session confirms Skill discovery.
- **User actions**: The user personally completes institutional account login, single sign-on, and multi-factor authentication.

| Setting | Location | Purpose |
| --- | --- | --- |
| Paper output and access preferences | `~/.oa-paper-fetch/config.json`, CLI arguments | Default output, access mode, and per-task choices |
| Chart specifications | Task request, plotting code | Research argument, journal, dimensions, fonts, and output format |
| Paper terminology and journal conventions | Per-paper glossary or symbol table in the project folder, task request | Fixed term translations, symbol definitions, and target journal figure/table style |

## 📁 Repository Structure

| Path | Purpose |
| --- | --- |
| `skills/<name>/SKILL.md` | Task entry point for each Skill |
| `skills/<name>/agents/openai.yaml` | Codex display metadata |
| `skills/<name>/references/` | Workflow, chart-selection, and writing references |
| `skills/paper-writing-zh/scripts/` | Fact-comparison script for paper revisions |
| `skills/oa-paper-fetch/*.py` | Acquisition, identity resolution, configuration, and recovery state |
| `skills/<name>/tests/` (where present), `tests/` | Skill regressions and repository hygiene checks |
| [scripts/link-skills.sh](scripts/link-skills.sh) | Link installation for personal Skill entries |
| [SETUP.md](SETUP.md) | Agent setup and validation manual |
| [AGENTS.md](AGENTS.md), [CONTRIBUTING.md](CONTRIBUTING.md) | Project rules and contribution requirements (Chinese) |
| [.github/workflows/](.github/workflows/) | Paper-fetch and paper-writing check configurations |

The author edits Skills directly in the local checkout, then validates, commits, and pushes changes. Linked installations share this source with personal Skill entries. Rerun the installation script after adding a Skill.

## 🤝 Contributions

Compatibility fixes, feature improvements, and documentation revisions are welcome. Before opening a PR:

- **Scope**: A PR addresses one problem and includes the affected Skill, a minimal reproduction, expected and actual results, and validation records.
- **Behavior changes**: Update the matching tests and documentation.
- **Privacy and attribution**: Remove personal and authentication data from samples and logs, and preserve Skill licenses and attribution.

Full requirements are in [CONTRIBUTING.md (Chinese)](CONTRIBUTING.md).

## 📄 Licensing and Attribution

Licenses are defined by files within individual Skill directories. There is no collection-wide root `LICENSE`.

| Skill | License | Copyright Attribution |
| --- | --- | --- |
| `oa-paper-fetch` | [MIT](skills/oa-paper-fetch/LICENSE) | Eason412 |
| `paper-figure` | [MIT](skills/paper-figure/LICENSE) | Haojae |
| `paper-writing-zh` | [MIT](skills/paper-writing-zh/LICENSE) | Eason412 |
