# md-course-report-to-pdf

[![Smoke Test](https://github.com/Eason412/md-course-report-to-pdf/actions/workflows/smoke.yml/badge.svg)](https://github.com/Eason412/md-course-report-to-pdf/actions/workflows/smoke.yml)

把中文 Markdown 课程报告、课程论文或作业报告转换为带封面、摘要、目录、图表编号、公式编号和参考文献的 LaTeX/PDF。它既可以安装为 Codex skill，也可以直接作为命令行工具运行。

项目内置 Pandoc/`ctexart` 模板、Markdown 与 LaTeX 两阶段 QA，以及 Tectonic/XeLaTeX 编译封装。模板参考了南京理工大学学位论文格式，但针对课程报告做了取舍；本项目不是学校官方模板，正式提交前仍应核对任课教师、学院或学校的当前要求。

## 能做什么

- 从一个 Markdown 文件生成课程报告封面、中文摘要、英文摘要、目录和正文。
- 支持无封面模式，以及由 YAML front-matter 驱动的学位论文样式封面。
- 将 Markdown pipe table 转换为可跨页的 `booktabs`/`longtable` 表格。
- 自动编号章节、图片、表格和普通展示公式。
- 将正文数字引用转换为上标引用，并检查引用与参考文献编号是否对应。
- 检查图片路径、表题、手写编号、非法引用、未编号公式、目录配置和长表结构。
- 在隔离目录中编译 LaTeX；同一报告目录中的并发构建会自动串行化，成功 PDF 以原子方式写入。

详细排版规则、官方规范映射和已知偏离见 [`references/format-qa.md`](references/format-qa.md)。

## 前置条件

运行构建脚本需要：

- Python 3；仓库 CI 使用 Python 3.11，并在 Ubuntu、macOS 和 Windows 上运行纯 Python 回归测试。
- [Pandoc](https://pandoc.org/)；命令名为 `pandoc`。
- LaTeX 编译器：优先使用 `tectonic`，未找到时回退到 `xelatex`。

先确认命令能够从终端找到：

```bash
python3 --version
pandoc --version
tectonic --version
```

如果只想检查 Markdown、生成 LaTeX 和查看 QA，可以不安装 LaTeX 编译器，并在构建时使用 `--skip-compile`。

## 安装为 Codex skill

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/Eason412/md-course-report-to-pdf.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/md-course-report-to-pdf"
```

安装后可以在 Codex 中直接描述任务，例如：

```text
请使用 $md-course-report-to-pdf 把 ./report.md 转成课程报告 PDF。
课程名称是“机器学习”，姓名是“张三”，学号是“20260001”。
```

如果不需要封面，应明确说明：

```text
请使用 $md-course-report-to-pdf 把 ./report.md 转成 PDF，不加入封面。
```

skill 的完整代理工作流见 [`SKILL.md`](SKILL.md)。

## 快速开始

下面的命令从标准模板创建一份报告，并生成 `report.pdf`。所有命令都在你准备存放报告的目录中执行。

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/md-course-report-to-pdf"

mkdir -p my-course-report
cp "$SKILL_DIR/examples/标准课程报告模板.md" my-course-report/report.md
cd my-course-report

python3 "$SKILL_DIR/scripts/build_course_report.py" report.md \
  --course "课程名称" \
  --student-name "姓名" \
  --student-id "学号" \
  --pdf "report.pdf"
```

成功时，命令退出码为 `0`，stdout 会输出一段 JSON 摘要，并在当前目录生成：

```text
report.pdf
course_report.tex
latex/report_body.md
latex/metadata.yaml
latex/prepare_report.json
latex/postprocess_qa.json
```

预处理 warning 会逐条写到 stderr，并同时保留在成功 JSON 的 `warnings` 数组中；`warning_count` 与数组长度一致。构建或 QA 失败时，脚本会把原因写到 stderr 并以非零状态退出。不要只看 PDF 是否存在；同时检查终端结果和两个 QA JSON 文件。

如果不需要封面：

```bash
python3 "$SKILL_DIR/scripts/build_course_report.py" report.md \
  --no-cover \
  --pdf "report.pdf"
```

如果只想把仓库当作普通命令行工具使用，可以把 `SKILL_DIR` 指向任意 clone 下来的仓库目录，不要求它位于 Codex skills 目录。

## Markdown 输入规则

建议从 [`examples/标准课程报告模板.md`](examples/标准课程报告模板.md) 开始修改。最小结构如下：

```markdown
# 课程报告题目

## 摘要

这里写中文摘要。

关键词：关键词一；关键词二；关键词三

## Abstract

Write the English abstract here.

Keywords: keyword one; keyword two; keyword three

## 引言

这里写正文，并在需要的位置引用文献[1]。

## 结论

这里写结论。

## 参考文献

[1] 作者. 文献题名[J]. 期刊名, 年份, 卷(期): 页码.
```

需要注意：

- 全文只保留一个 `#` 作为报告题目；正文从 `##` 开始。
- 不要在标题中手写 `1.`、`1.1` 等章节编号。
- 图片必须是报告目录内可以解析的相对路径；远程 URL、绝对路径和跳出报告目录的路径会被 QA 拒绝。
- 正文引用使用 `[1]`、`[1,2]`、`[1-3]` 等数字形式，文末应存在对应编号的参考文献。
- 本工具不会替你核实参考文献真伪，也不会自动运行 CSL/`citeproc`；作者、题名、年份、DOI 和 URL 仍需人工核对。
- 默认会拒绝逐页讲稿或幻灯片草稿；只有明确需要原样转换时才使用 `--allow-slide-draft`。

### 图片

把图片放在报告目录内，例如：

```text
report.md
image/
  method_flow.png
```

在 Markdown 中使用相对路径：

```markdown
![方法流程图](image/method_flow.png)
```

图片说明只写标题，不要手写“图 1”，模板会自动编号。

### 表格

使用 Markdown pipe table，并在表格后紧跟 Pandoc 表题；表格与表题之间不能有空行：

```markdown
| 方案 | 优势 | 约束 |
|---|---|---|
| 方案 A | 易于实现 | 依赖输入质量 |
| 方案 B | 效果稳定 | 成本较高 |
: 方案对比
```

表题必须写成 `: 标题`。不要写 `表: 标题`，也不要手写 `: 表 1 标题`。

### 公式

普通展示公式使用 LaTeX 数学语法：

```markdown
$$
E = mc^2
$$
```

过滤器会为普通展示公式生成编号。需要对齐、标签或特殊编号时，可以显式使用 `align` 或 `equation` 环境；原始 LaTeX 块会保留。

## 三种封面模式

| 模式 | 如何启用 | 所需信息 |
| --- | --- | --- |
| 课程报告封面 | 默认模式 | `--course`、`--student-name`、`--student-id` |
| 无封面 | `--no-cover` | 不需要课程名称、姓名、学号或 logo |
| 学位论文样式封面 | Markdown 顶部设置 `cover: thesis` | 使用 front-matter 字段，不要求课程报告三字段 |

课程报告封面默认使用 skill 内的 `assets/njust_logo.png`。如需其他 logo，可以传入 `--logo path/to/logo.png`；构建脚本会把外部 logo 复制到报告的生成目录中。校徽和其他机构标识可能受额外权利限制，分发或提交前应确认使用权限。

### 学位论文样式封面

可以复制 [`examples/学位论文模板.md`](examples/学位论文模板.md)，或者在 Markdown 文件最顶部加入：

```yaml
---
cover: thesis
classification: TP391
secrecy: 公开
udc: 004.8
degree_type: 硕士学位论文
title: 基于深度学习的图像识别方法研究
subtitle: 以遥感图像为例
author: 张三
advisor: 李四
advisor_title: 教授
degree_category: 工学硕士
discipline: 计算机科学与技术
research_field: 计算机视觉
submit_date: 2026 年 6 月
---
```

`degree_type`、`advisor`、`degree_category`、`discipline`、`research_field` 中任一字段非空也会触发学位论文封面；建议显式填写 `cover: thesis`，避免意外切换。命令行参数优先于 front-matter 中的同类字段。

这个封面只覆盖仓库已实现的附件 2.1 样式。书脊、封二、英文封二、原创性声明、使用授权声明、双面印刷页眉页脚等要求不在当前自动化范围内。

## 输出文件

所有相对路径都以源 Markdown 所在目录为基准。

| 输出 | 默认值 | 说明 |
| --- | --- | --- |
| LaTeX | `course_report.tex` | Pandoc 生成并经过后处理的完整 TeX |
| PDF | `course_report.pdf` | 使用 `--pdf` 可以更改文件名，但路径必须位于报告目录内 |
| 工作目录 | `latex/` | 存放预处理正文、元数据和 QA JSON |
| 额外 PDF 副本 | 不生成 | 使用 `--output-pdf PATH` 将成功 PDF 再复制到指定位置 |

`--output-pdf` 只能在实际编译 PDF 时使用，不能与 `--skip-compile` 同时使用。

## 常用参数

| 参数 | 作用 |
| --- | --- |
| `--course TEXT` | 课程名称 |
| `--student-name TEXT` | 学生姓名 |
| `--student-id TEXT` | 学号 |
| `--logo PATH` | 指定封面 logo |
| `--no-cover` | 不生成封面 |
| `--allow-slide-draft` | 允许转换被识别为逐页讲稿/幻灯片草稿的输入 |
| `--work-dir PATH` | 修改工作目录；必须位于源 Markdown 目录内 |
| `--tex PATH` | 修改 TeX 输出；必须位于源 Markdown 目录内 |
| `--pdf PATH` | 修改主 PDF 输出；必须以 `.pdf` 结尾 |
| `--output-pdf PATH` | 把最终 PDF 额外复制到指定位置 |
| `--keep-intermediates` | 保留 `.aux`、`.log`、`.toc` 等 LaTeX 中间文件 |
| `--skip-compile` | 运行预处理、Pandoc 和后处理，但不编译 PDF |
| `--command-timeout SECONDS` | 每个外部命令的超时时间；默认 `180` 秒 |

完整参数以当前脚本输出为准：

```bash
python3 scripts/build_course_report.py --help
```

## QA 与构建安全

构建过程会生成两份主要检查报告：

- `latex/prepare_report.json`：检查 Markdown 输入、图片、表题、引用、摘要和封面元数据。
- `latex/postprocess_qa.json`：检查生成的 LaTeX、目录、公式、表格、长表续页和封面布局。

端到端脚本会把关键 QA 失败视为构建失败，例如：

- 图片缺失或路径越出报告目录；
- 图片题、表题中存在手写编号；
- pipe table 缺少紧邻表题；
- 正文引用缺少参考文献条目或引用格式无法安全解释；
- 展示公式仍未编号；
- 长表缺少续表标题、重复表头或末页底线；
- 目录或封面布局没有满足模板约束。

构建器还会阻止源文件与 TeX/PDF/中间文件发生路径碰撞，为同一报告目录加构建锁，对外部命令应用超时，并且只在编译出有效 PDF 后替换最终输出。

这些检查不能代替人工阅览。提交前至少检查封面、摘要、目录、正文第一页、跨页表格、参考文献页和最终页。

## 测试

在仓库根目录运行：

```bash
python3 -m py_compile scripts/*.py tests/*.py
python3 -m unittest -v tests.test_regressions
python3 scripts/run_smoke_tests.py
```

- 回归测试覆盖路径碰撞、并发锁、Pandoc CLI 参数兼容、超时诊断、标题处理、图片解析、引用、公式和长表后处理。
- smoke test 会处理仓库示例；本机存在 Tectonic 或 XeLaTeX 时还会真实编译 PDF。
- GitHub Actions 在 Ubuntu、macOS 和 Windows 上运行回归测试；完整 PDF smoke 同时覆盖 Pandoc 3.1.3 和 3.10.1，并在 Ubuntu 安装 Tectonic、Poppler 和 qpdf。

如果本地需要强制要求编译器和 PDF 工具全部存在，可以使用与 CI 相同的环境变量：

```bash
MD_COURSE_REPORT_REQUIRE_COMPILER=1 \
MD_COURSE_REPORT_REQUIRE_PDF_TOOLS=1 \
python3 scripts/run_smoke_tests.py
```

## 仓库结构

```text
SKILL.md                           Codex skill 工作流
agents/openai.yaml                 skill 展示元数据
assets/templates/                  Pandoc/ctexart 模板
examples/标准课程报告模板.md       可复制的课程报告模板
examples/学位论文模板.md           学位论文样式封面模板
references/format-qa.md            排版规则、QA 清单和规范映射
scripts/build_course_report.py     端到端构建入口
scripts/prepare_course_report.py   Markdown 预处理与 QA
scripts/postprocess_course_tex.py  LaTeX 后处理与 QA
scripts/run_smoke_tests.py         端到端 smoke test
tests/test_regressions.py          回归测试
```

## 当前边界

- 这是面向课程报告的自动排版工具，不是完整的正式学位论文提交系统。
- 模板提供字体回退，但不同系统的实际字体可能不同；学校要求固定字体时，应安装对应字体并检查最终 PDF。
- QA 检查结构和已知错误模式，不判断论述质量、数据真实性、引用真实性、摘要字数或学校对参考文献数量的要求。
- 图片内容、机构 logo、官方文档和用户自行提供的素材可能不属于本项目的 MIT 授权范围。

## 许可证与第三方材料

原创代码、模板、示例和仓库文档使用 [MIT License](LICENSE)。

`assets/njust_logo.png`、南京理工大学官方格式原件及其可读转写件不属于 MIT License 的授权范围。来源、哈希和已知限制见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。这些材料的收录不表示南京理工大学对本项目的认可或背书。

## 反馈与贡献

发现构建失败、格式回归或文档错误时，请提交 [GitHub Issue](https://github.com/Eason412/md-course-report-to-pdf/issues)，并尽量附上：

- 可最小复现的 Markdown；
- 使用的操作系统以及 Pandoc、Tectonic/XeLaTeX 版本；
- 终端错误信息；
- `latex/prepare_report.json` 和 `latex/postprocess_qa.json` 中与问题有关的字段；
- 不包含个人信息的 PDF 页面截图。
