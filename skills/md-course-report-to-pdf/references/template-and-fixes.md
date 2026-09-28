# Template Defaults and Common Fixes

(Moved verbatim from SKILL.md.)

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
