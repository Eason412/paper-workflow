---
name: md-course-report-to-pdf
description: Convert Chinese Markdown course reports, class papers, or homework reports into polished LaTeX/PDF deliverables using Pandoc, ctexart, Tectonic, local images, Chinese/English font rules, cover pages, table of contents, chapter pagination, GB/T 7714-style references, and final PDF QA.
---

# Markdown Course Report To PDF

Follow this workflow to turn one Chinese Markdown course report into a polished PDF using the bundled scripts and template. Resolve `SKILL_DIR` to the absolute directory containing this loaded `SKILL.md`, regardless of installation location. Read `references/format-qa.md` only when changing layout/reference rules, debugging QA failures, or handling tables/citations beyond the quick path.

## Workflow

1. **Inputs**
   - Identify the source `.md`, image folder, and desired output paths. If title, abstract, or keywords live in separate files, merge or confirm them before running the preprocessor.
   - Before conversion, ask for or explicitly confirm the cover fields: course name, student name, and student ID. These fields differ across users and reports; do not silently reuse values from a previous run unless the user explicitly asks to reuse them.
   - If the user says they do not need a cover, pass `--no-cover` and do not ask for course name, student name, student ID, or logo.
   - **Thesis cover (optional):** if the user wants a 学位论文-style cover instead of the course cover, put `cover: thesis` in a YAML front matter block at the very top of the source `.md`, then add any needed fields from `degree_type`/`classification`/`secrecy`/`udc`/`author`/`advisor`/`advisor_title`/`degree_category`/`discipline`/`research_field`/`submit_date`; see `examples/学位论文模板.md` and README「学位论文封面」. Without `cover: thesis`, only `degree_type`, `advisor`, `degree_category`, `discipline`, or `research_field` automatically triggers the thesis layout; the other fields are supplementary. Once triggered, the wrapper renders the 附件 2.1 layout and does not require `--course/--student-name/--student-id`. Empty fields show as blank underlines. Leave 书脊/封二/声明 out of scope.
   - Do not ask for or render a completion date on the cover unless a school-provided template explicitly requires it.
   - If `assets/njust_logo.png` is present locally, the wrapper uses it as the default logo. Otherwise pass `--logo` for a real logo, or omit it to render the cover without a logo.
   - Check Markdown/HTML image links with `grep -nE '^!\[|<img'`.
   - Keep image paths relative to the Markdown/LaTeX project root.
   - Treat Markdown `#` as the report title and Markdown `##` as body section headings after the title. For this numbered template, prefer headings without manual numeric prefixes, so LaTeX can generate section, figure, table, and equation numbers consistently.
   - Do not feed page-by-page lecture notes or slide drafts directly into this course-report path. If the source contains many headings such as `## 第 1 页｜...` plus `屏幕：` / `讲：` / `图：`, first rewrite it into a formal report with abstract, chapter sections, body prose, figures/tables, and references. Only pass `--allow-slide-draft` when the user explicitly wants a raw slide-note PDF.
   - Extract Chinese and English abstracts from the source into template metadata (`abstract_zh`, `keywords_zh`, `abstract_en`, `keywords_en`) and remove those abstract sections from the generated body. The final order must be cover, abstracts, TOC, then body.
   - Keep level-1 chapter headings short and summary-style; avoid long sentence headings unless the source/template requires them.
   - Enforce user/school limits such as keyword count before conversion.

2. **Plan and verify references when requested**
   - Search official sources and academic databases/pages before adding references; do not invent titles, authors, years, DOI, URLs, or journal details.
   - Use concise GB/T 7714 numeric entries unless the school provides a stricter bibliography template. Keep rendered entries short; hide raw URLs/DOI URLs unless explicitly required.
   - Keep each reference number at its first meaningful appearance in normal body prose. Later repeated citations to the same reference should be removed unless the user explicitly wants dense citation reminders; code blocks, Markdown links, image captions, pipe tables, and the reference list itself must not decide the first citation position.
   - After rewriting, verify that cited numbers have matching reference-list entries and that unused reference entries are intentional. For detailed reference shapes and citation distribution rules, use `references/format-qa.md`.

3. **Prepare figures**
   - Insert figures into Markdown where they support the argument.
   - Captions should be pure titles, for example `![方法流程图](image/figure_01.png)`.
   - Do not include `图 1` in Markdown captions when LaTeX will auto-number figures.
   - If the source already has a handwritten figure title near the image, convert it into the Markdown alt-text caption or remove it from body prose; do not keep both.
   - Avoid duplicate or decorative figures.

4. **Prepare tables**
   - Prefer Markdown pipe tables for course reports. Pandoc emits `booktabs` rules (`\toprule`, `\midrule`, `\bottomrule`) for these tables, giving the expected three-line-table style.
   - Keep table headers short. Prefer labels such as `路线`, `主要原料`, `优势`, `约束`, `内容`, and `意义` over long explanatory phrases.
   - Add a table caption immediately after the table with no blank line, for example `: 方案对比`, so LaTeX can number it as `表 2.1`. Do not use `表: 标题`; Pandoc treats that as ordinary text rather than a table caption.
   - Do not type manual labels such as `表 1` in the caption. Use a pure title and let the template number the table.
   - For tables that may cross pages, verify repeated centered headers, a continued-table marker, and `\endfoot`/`\endlastfoot` bottom rules; do not trust a single short pipe-table smoke test after changing table layout.

5. **Build with the wrapper**
   - Use the bundled wrapper for the normal path. It runs preprocessing, Pandoc, LaTeX postprocessing, compilation, JSON QA, optional PDF copy, and intermediate cleanup from the project root:
     ```bash
     # Set SKILL_DIR to the actual directory containing this SKILL.md.
     SKILL_DIR="/absolute/path/to/md-course-report-to-pdf"
     python3 "$SKILL_DIR/scripts/build_course_report.py" input.md \
       --course "课程名称" \
       --student-name "姓名" \
       --student-id "学号" \
       --logo "path/to/project-logo.png" \
       --output-pdf "course_report.pdf"
     ```
     Omit `--logo` to use the local bundled logo when present. Pass an explicit path only when the report should use a specific real logo.
   - Read the wrapper's stdout JSON summary and its `warnings` array; the same prepare warnings are also written to stderr for interactive visibility. Then inspect `latex/prepare_report.json` and `latex/postprocess_qa.json` before trusting the PDF. The wrapper blocks missing or unsafe body image paths, missing references, manual figure/table numbers, unsupported table-caption syntax, table-caption failures, inconsistent TOC font/width settings, and non-centered or non-underlined cover field layout before compile; fix the Markdown source or template before retrying.
   - The preprocessor removes repeated numeric citation markers after their first normal body-prose appearance and normalizes Chinese citation punctuation to ASCII markers. Review `qa.citation_dedup` in `latex/prepare_report.json` when citation placement matters.
   - The wrapper serializes builds from the same source directory, applies a bounded timeout to every external command, compiles in an isolated temporary directory, and atomically replaces successful PDF outputs. Use `--command-timeout SECONDS` only when a large report legitimately needs more than the default 180 seconds per command.

6. **Manual fallback**
   - If debugging the pipeline or localizing a failure, run the bundled scripts in this order: `prepare_course_report.py`, Pandoc with `ctexart-course-report.tex` and `drop_first_h1.lua`, then `postprocess_course_tex.py`.
   - Resolve script/template paths from the skill directory; do not assume `scripts/...` exists in the report project.
   - Do not use `--citeproc` for this course-report path unless the template is extended with Pandoc CSL macros. Use concise numeric references in the Markdown source instead.
   - The Pandoc Lua filter converts only semantic prose citations to `\textsupcite{n}` before the reference list. It deliberately leaves code, raw LaTeX, links, image labels, tables, and bibliography labels untouched.
   - The Lua filter converts semantic untagged display math into numbered `equation` environments. Use explicit `align`/`equation` in Markdown when special alignment, tags, or labels are needed; raw LaTeX blocks are preserved.

7. **Use the ctexart template**
   - Start from `$SKILL_DIR/assets/templates/ctexart-course-report.tex`.
   - Keep generated files ASCII-named (`course_report.tex`, `latex/report_body.md`) because TeX tools can mishandle Chinese paths in some manual workflows.
   - Compile from the project root so `image/...` paths resolve correctly.

8. **QA**
   - When scripts, template, table handling, citation handling, or wrapper behavior changed, run the bundled smoke tests before using the skill on a real report:
     ```bash
     python3 "$SKILL_DIR/scripts/run_smoke_tests.py"
     ```
   - Verify PDF exists, page count is nonzero, A4 portrait size is expected, and image count matches inserted figures.
   - Inspect the cover, TOC, abstract, first body page, at least one chapter transition page, and the reference page when layout changed.
   - Check `latex/prepare_report.json` and `latex/postprocess_qa.json` for missing images, invalid or unmatched citations, duplicated abstract/body headings, raw citation markers, unnumbered display math, unwanted bibliography URLs, table-caption failures, missing longtable continuation/final-page footers, missing continued captions, non-centered table text, and non-vertically-centered table columns.
   - For layout, table, citation, or reference-rule changes, use the detailed checklist in `references/format-qa.md`.
   - When compiler logs are available, check for `LaTeX Error`, `File not found`, large `Overfull \hbox`, missing images, and font failures.
   - Mild `Underfull \vbox` and macOS font reproducibility warnings are usually acceptable if the PDF renders correctly.

## Template Defaults

Use these defaults unless the user or a school template requires otherwise. They are a course-report adaptation of the official NJUST thesis format; `references/njust-thesis-format.md` holds the readable spec and `references/format-qa.md` ("NJUST Source Format Mapping And Deviations") records which rules are verbatim and which are intentional deviations.

- Cover fields: include course name, student name, and student ID only; no completion date by default. Use a local bundled logo when present, or a user-provided logo path.
- Front matter: Chinese abstract, English abstract, and TOC use lowercase Roman page numbers; the body switches to Arabic page numbers starting at 1.
- TOC entries: level-1 entries (chapters plus 致谢, 参考文献, 附录) use four-size bold Songti; sub-levels use small-four Songti. This follows the official NJUST thesis spec (`references/njust-thesis-format.md`, §2.5 目次页).
- TOC alignment: all section levels use a shared number-width box and configured page-number width/right margin so level-1 and level-2 entries align consistently when numbered headings have different lengths.
- Cover field layout: course name, student name, and student ID use fixed-width centered `\underline{\makebox[...][c]{...}}` value boxes so all three underlines have equal length; avoid wide ragged-right value columns that make short names or IDs look off-center.
- Headers: no page headers by default; footer page number centered.
- Body: Chinese text uses Songti, English letters/numbers use Times New Roman or fallback; body is small-four with fixed 20 bp line spacing.
- Figures, tables, and equations: number within the current section, for example `图 2.1`, `表 2.1`, and `（2.1）`.
- Long tables: repeated table heads and body cells are horizontally centered; paragraph columns are vertically centered; continuation pages include a non-numbered `（续表）` caption; non-final and final pages both carry booktabs bottom rules.
- Keywords: at most five.
- Level-1 body headings start on new pages.
- References: start on a new page, center the “参考文献” heading, keep bibliography labels normal, and hide unwanted raw URLs/DOI URLs.

## Common Fixes

- **Chinese path or `\input{...}` fails**: keep `--tex`, `--work-dir`, and generated intermediates ASCII-named.
- **Image not found**: compile from the project root, or update `\graphicspath{{./}{image/}{figures/}{assets/}}`.
- **Caption duplicates “图 1 图 1”**: remove manual figure numbers from Markdown alt text and nearby handwritten figure-title paragraphs.
- **Table is not numbered**: add a Pandoc table caption line such as `: 方案对比` immediately after the pipe table with no blank line.
- **Long table breaks across pages without a bottom rule, continued heading, or centered cells**: check `longtables_missing_endfoot == 0`, `longtables_missing_endlastfoot == 0`, `longtables_missing_continued_caption == 0`, `longtable_headers_centered == true`, `longtable_cells_centered == true`, and `longtable_columns_vertical_centered == true` in `postprocess_qa.json`.
- **Table caption syntax is rejected**: use `: 标题` only. Do not use `表: 标题`, `Table: 标题`, or manual labels such as `: 表 1 标题`.
- **`No counter 'none' defined`**: check for malformed table captions or manual caption text; use a pure `: 标题` line and remove handwritten `图/表 n` prefixes.
- **`Missing number, treated as zero` near tables**: ensure the template loads `calc`, then check that each Pandoc table caption is immediately adjacent to the pipe table.
- **URL overfull**: first remove unnecessary bibliography URLs; if a URL must remain outside the bibliography, use angle-bracket Markdown links and load `xurl`.
- **Unnumbered display formulas**: if `remaining_unnumbered_display_math` stays nonzero, manually convert only the special formula blocks that the postprocessor cannot safely rewrite.
- **TOC entries look misaligned**: check `postprocess_qa.json` for `toc_entry_font_sizes == ["-4", "4"]`, `toc_section_font_size == "4"`, `toc_section_is_bold == true`, `toc_sub_font_size == "-4"`, `toc_uses_shared_numwidth == true`, and `toc_page_width_configured == true`; then inspect the rendered TOC page.
- **Cover fields look off-center or lack underlines**: check `cover_fields_use_makebox_centering == true` and `cover_fields_have_underlines == true`, then inspect page 1. The cover should not use a wide `p{...}` value column with `\raggedright`.
