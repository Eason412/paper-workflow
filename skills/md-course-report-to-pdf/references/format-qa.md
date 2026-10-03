# 格式与 QA

调整模板、处理复杂图表引用或排查构建失败时读取。

## 输入限制

- 源文件使用 `#` 题目、`##` 章节；不要手写章节或图表编号。`2024 年政策背景`、`3D 打印`等实义数字不是编号。
- 图片使用源 Markdown 目录内的相对路径；图注放在图片 alt text，删除重复的手写图题。
- Pipe table 的表题可在表前或表后，使用 `: 标题` 或 `Table: 标题`，允许与表格之间有空行；`表: 标题`不受支持。标题只写内容，不加“表 1”。
- 顶部 front matter 仅支持单行 `key: value`，不支持嵌套、列表或多行标量。配对引号后的 `#` 注释可用，如 `author: "姓名" # 作者`；未配对引号、无效行或缺失结束分隔符会报错，不静默忽略。
- 中文、英文摘要及关键词提取为前置页；每组关键词最多五个。普通展示公式自动编号，特殊对齐或标签使用原始 `align` / `equation`。
- 数字引用使用 `[1]`、`[1,2]`、`[1-3]`，每个被引编号应有文后条目。默认仅保留首次正文引用；注释、代码、公式、链接、图注、表格和参考文献列表不决定首次位置，HTML 注释原文保留。`--keep-repeated-citations` 保留重复引用。
- 文献条目用简洁 GB/T 7714 数字格式，新增文献核对出版方或机构来源。原始 URL/DOI URL 默认隐藏，`--keep-reference-urls` 保留；不使用 `--citeproc`。
- 讲稿式输入只产生 warning，不自动改写。课程封面字段取自本次请求或源文件；学位样式字段见 [示例](../examples/学位论文模板.md)。当前实现也会由非空 `degree_type`、`advisor`、`degree_category`、`discipline` 或 `research_field` 触发学位样式，显式 `cover: thesis` 更清晰。

## PDF 检查

- 检查 PDF 存在、页数非零、A4 纵向；目视封面、摘要、目录、首个正文页、章节换页、跨页表格和参考文献。
- 封面字段居中、下划线等宽；无封面时正文前不出现空封面。目录一级条目四号加粗、下级小四，点线和页码对齐。
- 图表题各出现一次；表题在表上、图题在图下。跨页表格重复表头，后续页重复表号并标“（续表）”（如“表 2.1 标题（续表）”），各页底线完整，表头和单元格水平居中、段落列垂直居中。
- `prepare_report.json` 检查元数据、图片、引用对应关系与 `qa.citation_dedup.events`；`postprocess_qa.json` 检查摘要未重复进正文、引用未残留、展示公式有编号、长表 caption/footers/continuation 完整。
- 需要细查时核对 `longtables_missing_caption`、`longtables_missing_endfoot`、`longtables_missing_endlastfoot`、`longtables_missing_continued_caption` 均为零，`longtable_headers_centered`、`longtable_cells_centered`、`longtable_columns_vertical_centered` 为 true。
- 编译日志不应有 LaTeX 错误、缺图、字体失败或影响阅读的溢出。轻微 `Underfull` 结合 PDF 判断。

## 常见失败

- 图片缺失：核对源文件相对路径及实际文件，不靠修改编译工作目录绕过路径检查。
- 表题缺失或不编号：核对表题为 `: 标题` / `Table: 标题`，以及 Pandoc 生成的 caption；表前后和空行本身不是错误。
- `No counter 'none' defined` 或表格附近 `Missing number`：检查 malformed caption、手写编号，以及模板是否加载 `calc`。
- 中文路径或 `\input` 失败：中间目录与 TeX 文件使用 ASCII 名称，默认 `latex/` 和 `course_report.tex` 即可。
- 引用位置、链接显示不符合预期：先检查两个保留参数和 QA 事件，不直接修改已经生成的 PDF。
- URL 溢出：不需要时隐藏文后 URL；需要保留时检查断行和 `xurl`。字体失败：核对目标环境的宋体/Times New Roman 或模板回退字体。
- 目录、封面或长表结构 QA 通过但观感异常：检查实际 PDF，再改模板；修改脚本/模板后运行 `uv run "$SKILL_DIR/scripts/run_smoke_tests.py"`。

## 来源与课程报告改编

格式来源是南京理工大学研究生院 2014-09-29 发布的[《博士、硕士学位论文撰写格式（2014版）》](https://gs.njust.edu.cn/57/08/c13822a87816/page.htm)。这里仅保留本模板使用的格式摘要，不附存原件或全文转录，也不声称逐条复刻；当前课程报告格式以模板和脚本为准。

模板采用 A4，上下边距 30/24 mm、左右 25 mm；正文小四宋体、20 bp 行距，英文字母和数字使用 Times New Roman 或回退字体。目录一级四号加粗、下级小四；图表题五号，图表公式按章节编号。摘要与目录用小写罗马页码，正文阿拉伯页码从 1 开始。

课程报告改编明确不同于学位论文：无奇偶页页眉，页码居中；默认简化为课程、姓名、学号封面，无完成日期；学位样式封面只借用字段布局，不含书脊、封二或声明。关键词最多五个；不执行博士/硕士文献数量、正文篇幅、匿名送审或图表清单等学位专属要求。校徽及来源权利说明见 [第三方材料声明](../THIRD_PARTY_NOTICES.md)。
