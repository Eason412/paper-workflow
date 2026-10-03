# Paper Workflow Setup

This manual is for Agents with file and terminal access. It links the repository's Skills into personal discovery directories and checks the runtimes needed for the selected tasks. Read the steps in order and execute only the dependency checks relevant to those tasks.

Available Skills: `oa-paper-fetch`, `course-report`, and `paper-figure`. Each complete `skills/<name>` directory is independently installable. The supplied installer links **all** directories under `skills/` into **both** Codex and Claude Code; it has no Skill-selection or host-selection option, so a single Skill or a single host uses the manual path at the end of step 2.1. Another host can use the same complete directories through its documented discovery mechanism.

Preserve existing checkout changes, licenses, and third-party notices. Setup does not authorize commits, pushes, paper downloads, paid calls, or changes to unrelated services. Existing explicit authorization covers only its stated scope. Obtain user consent before software installation, personal configuration changes, link replacement or backup, institutional login, and resource downloads; do not ask again for actions already authorized.

## 🧭 1. Stable Checkout

Use an existing checkout when supplied. Otherwise agree on a stable destination before cloning. A typical layout is `~/Projects/opensource/paper-workflow`; the author's checkouts use `~/Projects/opensource/<repo>`. This is a convention, not a required location. The destination must remain available because installation uses links to its contents.

After authorization for the destination and network access, cloning commands are:

macOS / Linux (POSIX shell):

```sh
REPO_DIR="$HOME/Projects/opensource/paper-workflow"
mkdir -p "$(dirname "$REPO_DIR")"
git clone https://github.com/Eason412/paper-workflow.git "$REPO_DIR"
cd "$REPO_DIR"
```

Windows (PowerShell):

```powershell
$RepoDir = Join-Path $HOME 'Projects\opensource\paper-workflow'
New-Item -ItemType Directory -Path (Split-Path $RepoDir -Parent) -Force | Out-Null
git clone https://github.com/Eason412/paper-workflow.git "$RepoDir"
if ($LASTEXITCODE -ne 0) { throw 'Clone failed' }
Set-Location -LiteralPath $RepoDir
```

Do not run `git clone` into an existing checkout. From its root, establish the actual path and inspect its contents instead:

```sh
REPO_DIR="$(pwd -P)"
git status --short
for name in oa-paper-fetch course-report paper-figure; do
  test -f "$REPO_DIR/skills/$name/SKILL.md" || echo "missing $name"
done
```

```powershell
$RepoDir = (Get-Location).Path
git status --short
foreach ($Name in 'oa-paper-fetch', 'course-report', 'paper-figure') {
    Get-Item -LiteralPath (Join-Path $RepoDir "skills\$Name\SKILL.md") -ErrorAction Stop
}
```

Read [AGENTS.md (Chinese)](AGENTS.md), [scripts/link-skills.sh](scripts/link-skills.sh), and the selected Skill specifications in the [catalog](README.en.md). Record the chosen path and tasks; for paper acquisition, distinguish OA-only, institutional CLI, and an existing authorized browser session.

**Success criteria:** the three Skill specifications and installer are present, the stable checkout path is recorded, and existing changes are preserved.

## 🔗 2. Installation Preview and Links

The destination directories are:

| Host | Discovery Directory | Backup Directory |
| --- | --- | --- |
| Codex | `${CODEX_HOME:-$HOME/.codex}/skills` | Sibling `skills-backup/` under the effective Codex home |
| Claude Code | `$HOME/.claude/skills` | `$HOME/.claude/skills-backup/` |

The installer uses absolute source paths. A symlink whose stored target exactly matches the source path is skipped. Another symlink is removed and replaced; its referent is not backed up. A real directory or file is moved to sibling `skills-backup/<name>-<YYYYMMDDHHMMSS>` before linking. Inspect local changes before replacement; an old link may refer to a separate working tree whose contents remain at that source.

### 2.1. macOS / Linux

The script is POSIX `sh`, with no Bash-specific syntax. From the recorded repository root, run the preview:

```sh
scripts/link-skills.sh --dry-run
```

Review the source, destination, replacement, and backup paths with the user; backup names take their timestamp from the actual run. The preview prints planned mutations as `would:` lines; existing matching links print `ok`. Preview output does not mean a link was created.

After user consent covering those paths and replacements, run:

```sh
scripts/link-skills.sh
```

The only documented option is `--dry-run`; there are no filtering options. Do not move an existing real installation manually to another backup layout when using this script. If a proposed timestamped backup already exists, wait for a new timestamp and repeat the preview before applying.

Verify the resulting entries independently of status messages:

After a script installation (not the single-Skill path below), run the check in a subshell so a failure does not close the Agent's shell:

```sh
(
for target in "${CODEX_HOME:-$HOME/.codex}/skills" "$HOME/.claude/skills"; do
  for skill in "$REPO_DIR"/skills/*/; do
    src=${skill%/}
    dest="$target/$(basename "$src")"
    test -L "$dest" || exit 1
    test "$(readlink "$dest")" = "$src" || exit 1
    test -f "$dest/SKILL.md" || exit 1
    printf '%s -> %s\n' "$dest" "$src"
  done
done
) && echo "all links ok"
```

**Success criteria:** the installer exits `0`, every personal entry has the intended target, and `SKILL.md` is readable through both hosts' links. Record any backup paths.

For a single Skill or a single host, skip the script and link by hand. Set `name` and `target`, inspect the destination, and present the result before changing anything:

```sh
name=oa-paper-fetch
target="$HOME/.claude/skills"   # or "${CODEX_HOME:-$HOME/.codex}/skills"
ls -ld "$target/$name" 2>/dev/null || echo "free    $target/$name"
```

After consent, clear the destination the same way the script does, then link and verify. An old symbolic link is removed; a real directory goes to the sibling `skills-backup/`:

```sh
mkdir -p "$target"
if [ -L "$target/$name" ]; then rm "$target/$name"
elif [ -e "$target/$name" ]; then
  backup="$(dirname "$target")/skills-backup"; mkdir -p "$backup"
  mv "$target/$name" "$backup/$name-$(date +%Y%m%d%H%M%S)"
fi
ln -s "$REPO_DIR/skills/$name" "$target/$name"
readlink "$target/$name" && test -f "$target/$name/SKILL.md"
```

Success means `readlink` prints the repository Skill path and `SKILL.md` is readable through the link.

### 2.2. Windows

For a single Skill or a single host, inspect the destination as in 2.1 and, after consent, create one junction: `New-Item -ItemType Junction -Path <target>\<name> -Target <checkout>\skills\<name>`. The function below installs every Skill into both hosts.

Native PowerShell does not execute POSIX `sh`. Use a directory junction for each complete Skill on a supported local Windows filesystem, or a symbolic link when Developer Mode or authorized elevation permits it. Junctions are directory reparse points rather than POSIX symbolic links; they suit local directories, while symbolic links support additional target types and locations. This procedure preserves shared source editing and honors `CODEX_HOME` without requiring a Unix shell.

The following function previews all sources and both destinations by default. It skips matching junctions or symbolic links, replaces old links, and backs up real entries to sibling `skills-backup/` before creating junctions. It also refuses to overwrite a backup with the same name.

```powershell
function Set-PaperWorkflowLinks {
    param([switch]$Apply)
    $CodexBase = if ([string]::IsNullOrEmpty($env:CODEX_HOME)) {
        Join-Path $HOME '.codex'
    } else {
        $env:CODEX_HOME
    }
    $Targets = @(
        (Join-Path $CodexBase 'skills'),
        (Join-Path $HOME '.claude\skills')
    )
    $Stamp = Get-Date -Format yyyyMMddHHmmss
    $Sources = Get-ChildItem -LiteralPath (Join-Path $RepoDir 'skills') -Directory
    foreach ($Target in $Targets) {
        $Target = [IO.Path]::GetFullPath($Target)
        if ($Apply) {
            New-Item -ItemType Directory -Path $Target -Force | Out-Null
        } else {
            Write-Output "would: create directory $Target if absent"
        }
        foreach ($Source in $Sources) {
            $Dest = Join-Path $Target $Source.Name
            $Existing = Get-Item -LiteralPath $Dest -Force -ErrorAction SilentlyContinue
            $IsLink = $null -ne $Existing -and
                (($Existing.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)
            if ($IsLink -and $Existing.LinkType -notin @('Junction', 'SymbolicLink')) {
                throw "Unsupported reparse point: $Dest"
            }
            $OldTarget = if ($IsLink) { @($Existing.Target)[0] } else { $null }
            if ($IsLink -and $OldTarget -eq $Source.FullName) {
                Write-Output "ok      $Dest"
                continue
            }
            if ($IsLink) {
                Write-Output "relink  $Dest (was $OldTarget)"
                if ($Apply) {
                    if ($Existing.PSIsContainer) {
                        [IO.Directory]::Delete($Dest)
                    } else {
                        [IO.File]::Delete($Dest)
                    }
                }
            } elseif ($null -ne $Existing) {
                $BackupRoot = Join-Path (Split-Path $Target -Parent) 'skills-backup'
                $Backup = Join-Path $BackupRoot "$($Source.Name)-$Stamp"
                if ($null -ne (Get-Item -LiteralPath $Backup -Force -ErrorAction SilentlyContinue)) {
                    throw "Backup already exists: $Backup"
                }
                Write-Output "backup  $Dest -> $Backup"
                if ($Apply) {
                    New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
                    Move-Item -LiteralPath $Dest -Destination $Backup -ErrorAction Stop
                }
            }
            if ($Apply) {
                New-Item -ItemType Junction -Path $Dest -Target $Source.FullName -ErrorAction Stop | Out-Null
            } else {
                Write-Output "would: junction $Dest -> $($Source.FullName)"
            }
        }
    }
}
Set-PaperWorkflowLinks
```

After user approval of the preview:

```powershell
Set-PaperWorkflowLinks -Apply
```

For an approved symbolic-link installation, replace `-ItemType Junction` in the creation line with `-ItemType SymbolicLink`, preview again, and apply. Obtain consent before enabling Developer Mode or elevating the process. Avoid a copied installation because it would stop sharing edits with the checkout.

Inspect each result using its actual previewed destination:

```powershell
$CodexBase = if ([string]::IsNullOrEmpty($env:CODEX_HOME)) { Join-Path $HOME '.codex' } else { $env:CODEX_HOME }
foreach ($Target in @((Join-Path $CodexBase 'skills'), (Join-Path $HOME '.claude\skills'))) {
    Get-ChildItem -LiteralPath (Join-Path $RepoDir 'skills') -Directory | ForEach-Object {
        $Dest = Join-Path $Target $_.Name
        Get-Item -LiteralPath $Dest -Force -ErrorAction Stop | Format-List FullName, LinkType, Target
        Get-Item -LiteralPath (Join-Path $Dest 'SKILL.md') -ErrorAction Stop
    }
}
```

**Success criteria:** every entry has `LinkType` `Junction` or `SymbolicLink`, `Target` matches the checkout's Skill directory, and each specification is readable. Record backups. This is a native Windows equivalent, not a Windows execution mode implemented by the repository script.

## 🛠️ 3. Runtime Selection and Installation Consent

Link installation does not require every Skill's runtime. Check only the dependencies for selected tasks. Git is needed for cloning and checkout maintenance; POSIX `sh` or PowerShell is needed for the corresponding installation procedure. No single Python environment is required for the collection.

Inspect available tools:

```sh
command -v uv pandoc tectonic xelatex pdffonts
```

```powershell
Get-Command uv, pandoc, tectonic, xelatex, pdffonts -ErrorAction SilentlyContinue
```

Check an existing Python without downloads:

```sh
uv --version
uv run --offline --no-python-downloads --no-project python -c "import sys; print(sys.version)"
```

Before installing a missing dependency, present the concrete platform-appropriate command, write locations, and download requirements for consent. Use uv for Python and packages, with isolated environments rather than system Python. An approved missing Python 3.12 can be installed with `uv python install 3.12`. Pandoc, TeX engines, fonts, and Poppler need platform-appropriate installations; do not assume that a package manager is already available.

The OA project environment is `skills/oa-paper-fetch/.venv`; uv also maintains interpreter and package caches. Playwright downloads Chromium separately, and a first Tectonic compilation may download TeX resources. Use `--offline --no-python-downloads` on subsequent uv commands when downloads are outside the authorization. A missing uncached requirement is a gap to report, not a reason to download silently.

**Success criteria:** each selected task has a known dependency list and an available runtime or an approved installation plan. Linked Skills that are not used need no dependencies.

## 🔎 4. Task Dependency Checks

Set the directory for each subsection from the stable checkout, not a presumed host path. For example:

```sh
SKILL_DIR="$REPO_DIR/skills/oa-paper-fetch"
```

```powershell
$SKILL_DIR = Join-Path $RepoDir 'skills\oa-paper-fetch'
```

Change the Skill name before each subsection. The single-line `uv` and tool commands below work in either shell with that variable. Check each native command's exit code (`$?` in POSIX shell, `$LASTEXITCODE` in PowerShell); stop the affected check on failure. Temporary sample outputs belong outside the checkout and should be removed after inspection.

### 4.1. oa-paper-fetch

Sources: [SKILL.md](skills/oa-paper-fetch/SKILL.md), [English guide](skills/oa-paper-fetch/README.md), [project metadata](skills/oa-paper-fetch/pyproject.toml), and [browser workflow](skills/oa-paper-fetch/references/browser-workflow.md).

| Mode | Dependencies | Access Scope |
| --- | --- | --- |
| OA-only | uv project Python 3.12+; standard library only | Open-access acquisition |
| Institutional CLI | OA runtime, Playwright 1.40+, system Chrome or Playwright Chromium | Entitled IEEE, Wiley, ScienceDirect content |
| Existing browser session | Agent browser-control and download capabilities | Authorized session on the same three platforms |

The standalone OA script supports Python 3.10+, but the supplied uv project requires Python 3.12+. No third-party package is needed for OA-only mode. Check the project runtime and CLI without querying papers:

```sh
uv run --project "$SKILL_DIR" python -c "import sys; print(sys.version); assert sys.version_info >= (3, 12)"
uv run --project "$SKILL_DIR" python "$SKILL_DIR/oa_fetch.py" --help
```

Only for an authorized institutional CLI setup:

```sh
uv sync --project "$SKILL_DIR" --extra institutional
uv run --project "$SKILL_DIR" --extra institutional python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(channel='chrome', headless=True); print(b.version); b.close(); p.stop()"
```

The CLI prefers the system Chrome channel and falls back to Playwright's bundled Chromium. If the Chrome check fails, install and check the fallback after consent:

```sh
uv run --project "$SKILL_DIR" --extra institutional python -m playwright install chromium
uv run --project "$SKILL_DIR" --extra institutional python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(headless=True); print(b.version); b.close(); p.stop()"
```

These launches use a temporary browser context, not an authenticated publisher profile. Missing Linux browser system libraries require a concrete approved installation before retrying. An existing browser-tool session is separate from the CLI's isolated profile; it does not require transferring authentication or installing Playwright merely to reuse that browser.

**Success criteria:** for OA-only and institutional CLI modes, Python meets the project requirement and CLI help exits `0`; institutional CLI additionally launches system Chrome or Playwright Chromium. For existing-session mode, the Agent can control the signed-in browser and save a downloaded file to a chosen directory; acquiring a real paper belongs to a separately authorized fetch task. Publisher access remains unverified until that workflow.

### 4.2. course-report

Sources: [SKILL.md (Chinese)](skills/course-report/SKILL.md), [guide (Chinese)](skills/course-report/README.md), [build script](skills/course-report/scripts/build_course_report.py), [template](skills/course-report/assets/templates/ctexart-course-report.tex), and [smoke checks](skills/course-report/scripts/run_smoke_tests.py).

| Output / Check | Dependencies | Role |
| --- | --- | --- |
| LaTeX and structural QA | uv, Python 3.10+, Pandoc; no third-party Python packages | Every build mode |
| PDF compilation | Tectonic or XeLaTeX with the template's TeX packages | Tectonic takes precedence on PATH |
| Font rendering | Usable Latin and Chinese fonts | Template font selection and fallback |
| Additional PDF QA | Poppler tools and qpdf | Optional build inspection; required by full CI QA |

```sh
uv run --no-project python -c "import sys; print(sys.version); assert sys.version_info >= (3, 10)"
pandoc --version
uv run --no-project "$SKILL_DIR/scripts/build_course_report.py" --help
```

For PDF output, check `tectonic --version`, or `xelatex --version` if Tectonic is absent. XeLaTeX needs the template's packages, including `ctex` and `fontspec`. The template tries Times New Roman, Liberation Serif, then DejaVu Serif for Latin text; Chinese fallbacks include Songti SC, Noto CJK, and Fandol. A compiler version alone does not confirm fonts or TeX resources.

After approval for any first-run resource downloads, build the bundled sample outside the repository:

```sh
SETUP_TMP="$(mktemp -d)"
cp "$SKILL_DIR/examples/minimal_report.md" "$SETUP_TMP/report.md"
uv run --no-project "$SKILL_DIR/scripts/build_course_report.py" "$SETUP_TMP/report.md" --no-cover --pdf "$SETUP_TMP/report.pdf"
test -s "$SETUP_TMP/report.pdf"
```

```powershell
$SETUP_TMP = Join-Path ([IO.Path]::GetTempPath()) "paper-workflow-setup-$([guid]::NewGuid())"
New-Item -ItemType Directory -Path $SETUP_TMP | Out-Null
Copy-Item -LiteralPath (Join-Path $SKILL_DIR 'examples\minimal_report.md') -Destination (Join-Path $SETUP_TMP 'report.md')
uv run --no-project "$SKILL_DIR/scripts/build_course_report.py" "$SETUP_TMP/report.md" --no-cover --pdf "$SETUP_TMP/report.pdf"
if ($LASTEXITCODE -ne 0) { throw 'Report build failed' }
Get-Item -LiteralPath (Join-Path $SETUP_TMP 'report.pdf') -ErrorAction Stop
```

Read stdout warnings and `latex/prepare_report.json` and `latex/postprocess_qa.json` under the temporary directory. Inspect the PDF for readable Chinese, abstracts, contents, body, and references. A rendered page can be inspected through the Agent's image tool; with Poppler available:

```sh
pdftoppm -f 1 -singlefile -png "$SETUP_TMP/report.pdf" "$SETUP_TMP/report-first"
```

For an explicitly selected LaTeX-only setup, append `--skip-compile` to the build command and inspect `course_report.tex` and the QA files instead of checking `report.pdf`. Report PDF compilation as unverified. Full smoke QA also uses `pdfinfo`, `pdffonts`, `pdfimages`, `pdftotext`, and `qpdf`; these are not all prerequisites for an ordinary build.

**Success criteria:** the selected build exits `0` and QA files are readable. PDF readiness additionally requires a nonempty compiled PDF and visual confirmation of usable fonts and layout. Record unavailable inspection separately.

### 4.3. paper-figure

Sources: [SKILL.md (Chinese)](skills/paper-figure/SKILL.md), [chart selection (Chinese)](skills/paper-figure/references/chart_selection.md), and [journal specifications (Chinese)](skills/paper-figure/references/journal_specs.md).

This Skill provides a workflow and references; the Agent writes matplotlib or seaborn code for the task. There is no bundled plotting CLI or pinned Python/library version. Use uv's temporary dependencies, usable fonts, and an image inspection tool. PDF font inspection needs `pdffonts`, supplied by Poppler.

After dependency-download consent, check imports and available font names:

```sh
uv run --no-project --with matplotlib --with seaborn python -c "import matplotlib,seaborn; from matplotlib import font_manager as fm; print(matplotlib.__version__,seaborn.__version__); print(sorted({f.name for f in fm.fontManager.ttflist}))"
```

For PDF delivery only, also check `pdffonts -v`.

Select actual installed Latin fonts and, for Chinese labels, Chinese fonts. Do not assume the example font names exist. The task's target journal instructions determine final dimensions and export requirements; the bundled reference is a starting point, not confirmation of current publisher rules.

Validate with a small chart in a temporary directory: use the chosen fonts, render a PNG, and inspect text, labels, legend, and margins. For PDF delivery, also export a PDF and run `pdffonts` on it; confirm embedded fonts and no Type 3 fonts. Use temporary dependencies in the actual plotting command as specified by the Skill:

```sh
uv run --no-project --with matplotlib --with seaborn python "$PLOT_SCRIPT"
```

Set `PLOT_SCRIPT` (or `$PLOT_SCRIPT` in PowerShell) to the actual Agent-created script. Do not claim a rendered check from import success alone.

**Success criteria:** plotting imports succeed, the required fonts are present, and a sample renders with readable labels at final dimensions. PDF readiness additionally includes successful font inspection. No journal-compliance claim is established by setup alone.

## 🔐 5. Institutional Authentication

Skip this step for OA-only or non-acquisition tasks. Authentication requires the user's entitled account and explicit authorization. No Sci-Hub, shared credentials, or paywall bypasses are supported.

For institutional CLI access, set `SKILL_DIR` back to `oa-paper-fetch` and open visible login:

```sh
uv run --project "$SKILL_DIR" --extra institutional python "$SKILL_DIR/oa_fetch.py" --institutional-login
```

The user completes institutional login, single sign-on, and multi-factor authentication, then presses Enter in the terminal. The CLI stores its session in `~/.oa-paper-fetch/profile`, separate from ordinary Chrome. Do not inspect, copy, export, synchronize, or commit authentication data. `--headless` only reuses an already valid session.

For an existing authorized browser session, follow the [browser workflow](skills/oa-paper-fetch/references/browser-workflow.md) in that same session. Authentication does not transfer between this route and the CLI. Do not operate credential or verification fields. Paper downloads require their own task authorization; setup alone does not request one. Acquisition details and limitations belong in the [Skill guide](skills/oa-paper-fetch/README.md).

**Success criteria:** the user has completed the chosen login procedure, or the need for login is recorded. Login completion is distinct from verified entitlement and a saved paper PDF.

## ✅ 6. Discovery and Maintenance

Open a new Agent session and confirm that each installed Skill is discovered. For another host, use its documented discovery or reload procedure; a readable directory alone does not prove native discovery.

Retain the checkout at its recorded path. Changes through personal links modify the repository directly. The author edits these sources locally, validates the affected Skill, then commits and pushes; maintenance requirements are in [AGENTS.md (Chinese)](AGENTS.md) and [CONTRIBUTING.md (Chinese)](CONTRIBUTING.md). Setup itself does not perform those Git operations.

After adding, renaming or removing a Skill, rerun `scripts/link-skills.sh --dry-run`, obtain approval for newly proposed changes, then run `scripts/link-skills.sh`, which also removes links into this checkout that no longer resolve; on Windows, repeat the equivalent preview and apply procedure. Moving the checkout requires recreating links to its new stable path. Do not delete `skills-backup/` entries without separate authorization.

**Success criteria:** report checkout and link paths, backup paths, native discovery, selected dependency checks, any sample-rendering results, and unresolved gaps. Distinguish filesystem installation, dependency readiness, visual checks, login completion, and actual paper acquisition.
