# Course Report Format And QA Reference

Load this file only when changing the template, rewriting references, debugging QA failures, or handling nontrivial tables/citations.

## Reference Policy

- Verify every new reference against official sources, publisher pages, academic databases, or reliable institutional pages.
- Use concise GB/T 7714 numeric entries unless a school template requires a fuller form.
- Prefer these rendered shapes:
  - Journal article: `[n] Authors. Title[J]. Journal, year, volume(issue): pages.`
  - Book/report/standard: `[n] Authors or institution. Title[M/R/S]. Place: Publisher, year.`
  - Official web page or news release: `[n] Institution. Title[EB/OL]. Year or publish date.`
- Hide raw URLs, tracking parameters, access boilerplate, database names, ISSN/ISBN, and DOI URLs in the rendered bibliography unless explicitly required.
- Keep source URLs in working notes when they are needed for verification.
- Keep repeated citations only at the first meaningful normal-prose appearance. After automatic cleanup, inspect `latex/prepare_report.json` `qa.citation_dedup.events` to confirm that code blocks, Markdown links, image captions, tables, and the reference list did not decide the first citation location.
- Put most citations in background, method, technology-route, and related-work sections. Later practice, recommendation, and conclusion sections can synthesize earlier evidence without adding new markers when that is the requested writing style.
- A paragraph should normally carry no more than two citation markers unless the user asks for dense literature mapping.

## Layout Defaults

- A4 single-sided report; margins: top 30 mm, bottom 24 mm, left/right 25 mm, footskip 20 mm.
- Cover: no page number; if a local bundled logo or user-provided logo is used, it is centered near the upper one-third; no generic “课程大报告” label unless the source title requires it.
- Cover fields: course name, student name, and student ID as one centered label/value block with equal-width underlined value boxes; no completion date by default.
- Abstracts: Chinese abstract, English abstract, then TOC; these front-matter pages use lowercase Roman page numbers.
- Body pages use Arabic page numbers starting at 1.
- Chinese body text uses Songti; English letters/numbers use Times New Roman when available. Chinese headings use bold Songti unless the school template requires Heiti.
- TOC title is centered (three-size bold Songti). TOC level-1 entries (chapters, 致谢, 参考文献, 附录) use four-size bold Songti; sub-levels use small-four Songti; all levels share dot leaders and number-width/page-number alignment. This matches the official NJUST thesis spec (`njust-thesis-format.md` §2.5 目次页).
- Body uses small-four Songti, fixed 20 bp line spacing, 2-em first-line indentation, and no extra paragraph spacing.
- Figure/table captions use fifth-size Songti; figure captions below figures, table captions above tables when Pandoc emits them that way.
- Tables should come from Markdown pipe tables with a pure caption line such as `: 路线比较` immediately after the table with no blank line; do not type `表 1`, `表: 标题`, or `Table: 标题`.
- Table headers and body cells should be concise, horizontally centered, and vertically centered in the rendered longtable. If a table crosses pages, continuation pages should show a non-numbered `（续表）` caption and both non-final and final pages should carry booktabs bottom rules.
- Figures, tables, and equations are numbered by section: `图 2.1`, `表 2.1`, `（2.1）`.

## QA Checklist

- `latex/metadata.yaml`: abstracts and keywords are present and sane. `latex/prepare_report.json`: title, cover fields, image paths, table captions, reference numbers, and `qa.citation_dedup.events` are sane.
- `latex/postprocess_qa.json`: `references_section_found` is true when references exist; `body_has_abstract_section` is false; `remaining_raw_citations_before_references` is empty; `remaining_unnumbered_display_math` is normally zero; `reference_urls` and `dangling_url_macro` are empty unless URLs are intentional.
- Cover visual check: logo centered horizontally near upper one-third; field block centered with equal-width underlined value boxes; no completion date.
- TOC visual check: `toc_section_font_size == "4"`, `toc_section_is_bold == true`, `toc_sub_font_size == "-4"`, `toc_entry_font_sizes == ["-4", "4"]`; level-1 entries (chapters, 致谢, 参考文献, 附录) render in four-size bold, sub-levels in small-four, with consistent dot-leader/page-number alignment.
- Table check: `latex/prepare_report.json` has no `tables_without_adjacent_caption`, `table_captions_separated_by_blank_line`, `invalid_table_captions`, or `table_captions_with_manual_numbers`; `longtable_count` matches expected table count, `booktabs_longtable_count` matches `longtable_count`, `longtables_missing_caption`, `longtables_missing_endfoot`, `longtables_missing_endlastfoot`, and `longtables_missing_continued_caption` are zero, `longtable_headers_centered`, `longtable_cells_centered`, and `longtable_columns_vertical_centered` are true, and captions render above tables.
- Log check: no `LaTeX Error`, missing image, font failure, or large unresolved `Overfull \hbox`. Mild `Underfull \vbox` is acceptable when the PDF renders correctly.

## Troubleshooting

- If a bibliography URL causes overfull lines, remove it from the rendered bibliography first; keep it only in notes or source comments.
- If a table is not numbered, put a Pandoc caption line immediately after the pipe table with no blank line.
- If LaTeX reports `No counter 'none' defined` or `Missing number, treated as zero`, first inspect recent figure/table captions for manual numbering, separated Pandoc captions, or malformed caption text.
- If a section title contains a real leading number such as `2024 年政策背景` or `3D 打印路线`, do not strip that number; only strip explicit outline prefixes like `1. 引言` or `2.1 判定标准`.
- If Chinese fonts fail on a non-macOS machine, use the template fallbacks or install the school-required fonts before changing the report text.

## NJUST Source Format Mapping And Deviations

The layout defaults trace to the official **南京理工大学博士、硕士学位论文撰写格式** (GB 7713-87 based). The full spec is in this folder as readable text (`njust-thesis-format.md`) and as the original binary (`njust-thesis-format.doc`). This skill is a **course-report adaptation** of that thesis spec, not a verbatim thesis clone. Use this table to tell faithful rules from intentional deviations.

### Implemented verbatim from the official spec

- Page setup: top 30 mm, bottom 24 mm, left/right 25 mm, header/footer 20 mm, A4 (§1).
- Heading typography (left-aligned, bold Songti, number + `\quad`): level-1 小三号 with 18 bp before/after; level-2 四号 with 12 bp; level-3 小四号 with 6 bp; level-4 same as body 小四号 (§1). Numbers/letters in Times New Roman.
- Abstract heading 三号加粗居中; body 小四号; keyword label "关键词" 四号加粗 with 小四号 values (§2.3, §2.4).
- TOC title 三号加粗居中; level-1 entries (chapters, 致谢, 参考文献, 附录) 四号加粗, sub-levels 小四号 (§2.5).
- Figure/table caption text 五号宋体; table caption above the table, figure caption below (§2.6, §3.2).
- Figure/table/equation numbered within the chapter: `图 2.1`, `表 2.1`, `（2.1）`; continued tables repeat the head and carry a non-numbered `（续表）` (§3.2).
- Page numbers: front matter (摘要…) lowercase Roman, body (引言…附录) Arabic restarting at 1 (§6).
- References: GB/T 7714 numeric entries; section starts on a new page with a centered heading (§3.5).

### Intentional deviations (course report ≠ thesis)

- **Keywords ≤ 5** instead of the thesis range 3–8 (§2.4). Tightened for short course reports; enforced before conversion.
- **No odd/even running headers.** The thesis spec mandates 小五号 headers carrying 论文题目 / 章节名 (§1); a course report uses none, with a centered footer page number instead of the thesis outer-edge position (§6).
- **Simplified cover by default.** The default cover carries only course name, student name, and student ID (equal-width underlined boxes), no completion date. An **optional thesis cover** (附件 2.1 layout: 分类号/密级/UDC → logo → 学位类型 → 题名/(题名和副题名) → 作者 → 指导教师/学位类别/学科名称/研究方向/论文提交时间) is rendered when the Markdown front matter supplies those fields (`cover: thesis` or any 学位 field); see README「学位论文封面」. Still out of scope: 书脊, 中英文封二, 声明 (§2.1–2.3, 附件 2.2–2.5).
- **No thesis-only requirements:** reference counts (博士 ≥ 80, 硕士 ≥ 40, 外文/近五年比例, §3.5), 匿名送审 anonymization (§7), and 图表清单/注释表 front matter (§2.6, §2.7) are not enforced.
- Bibliography hides raw URLs/DOI by default (the GB 7713-87 examples predate routine URL/DOI fields).
