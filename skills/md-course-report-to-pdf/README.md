# Markdown Course Report to PDF

中文课程报告的 Markdown 排版工具，提供课程封面、中英文摘要、目录、图表与公式编号、参考文献排版，以及 Markdown / LaTeX 双阶段 QA。

构建链路：

```text
Markdown 与本地图片 → 预处理 → Pandoc / ctexart → LaTeX 后处理 → PDF 与 QA JSON
```

## 安装与环境

Skill 安装见 [Paper Workflow](../../README.md#安装)。本目录是完整安装单元，脚本、模板、示例和格式参考应一并保留。

运行依赖为 Python 3.10+、Pandoc，以及 Tectonic 或 XeLaTeX。模板包含中文字体回退；固定字体要求应在目标环境核对。首次 Tectonic 编译可能需要下载 TeX 资源包。

```bash
python3 --version
pandoc --version
tectonic --version
```

仅使用 XeLaTeX 时，最后一条替换为 `xelatex --version`。使用 `--skip-compile` 可只生成 LaTeX 和 QA，但仍需 Pandoc。

## 快速开始

完成总仓库的链接安装后，在准备存放报告的目录执行：

```bash
SKILL_DIR="$HOME/.agents/skills/md-course-report-to-pdf"
mkdir -p my-course-report
cp "$SKILL_DIR/examples/标准课程报告模板.md" my-course-report/report.md
cd my-course-report
python3 "$SKILL_DIR/scripts/build_course_report.py" report.md \
  --course "课程名称" \
  --student-name "姓名" \
  --student-id "学号" \
  --pdf "report.pdf"
```

其他安装位置将 `SKILL_DIR` 替换为包含本 README 的绝对目录。编辑 Markdown 后重新运行构建命令即可。

无封面构建：

```bash
python3 "$SKILL_DIR/scripts/build_course_report.py" report.md --no-cover --pdf "report.pdf"
```

Codex 调用：

```text
使用 $md-course-report-to-pdf，将 report.md 转为课程报告 PDF。
课程名称为“示例课程”，姓名为“示例学生”，学号为“0000000000”。
```

课程封面字段由本次请求提供；无需封面时明确说明。完整代理流程见 [SKILL.md](SKILL.md)。

## Markdown 结构

建议使用 [标准课程报告模板](examples/标准课程报告模板.md)：

```markdown
# 报告题目

## 摘要
中文摘要正文。
关键词：关键词一；关键词二

## Abstract
English abstract.
Keywords: keyword one; keyword two

## 引言
正文与数字引用[1]。

## 结论
结论正文。

## 参考文献
[1] 作者. 文献题名[J]. 期刊名, 年份, 卷(期): 页码.
```

- 一级标题 `#` 表示报告题目，正文从 `##` 开始，章节编号由模板生成。
- 摘要和关键词提取为封面后的独立前置页，关键词最多五个；代码块中的示例标题保持原样。
- 引用采用 `[1]`、`[1,2]` 或 `[1-3]`。重复引用默认保留第一次正文出现；HTML 注释、公式、代码、链接、图注和表格不决定首次引用位置。注释原文保留，注释内的参考文献标题或编号不作为正文依据。
- 输入应为可信 Markdown。原始 LaTeX/HTML 和本机编译器属于构建流程，临时目录不提供不可信文档沙箱。

### 图片与表格

图片使用报告目录内的相对路径，支持行内与引用式图片：

```markdown
![方法流程图](image/flow.png)

![结果对比][result]
[result]: image/result.png
```

图注采用纯标题，避免手写“图 1”。不存在、绝对路径或越出报告目录的图片会被 QA 阻断。

表题紧邻 pipe table，使用 `: 标题`，中间不留空行：

```markdown
| 方法 | 特征 |
| --- | --- |
| 方法 A | 特征说明 |
: **方法**对比
```

模板提供三线表、重复表头、续表标记与末页底线；富文本表题保留强调格式。图、表和公式按章节编号。

### 公式与列表

普通展示公式自动编号；特殊对齐与标签可使用原始 `align` / `equation` 环境。数学表达式中的方括号不作为数字引用处理。有序列表与嵌套列表保留原项目内容。

## 封面模式

| 模式 | 配置 |
| --- | --- |
| 课程报告 | `--course`、`--student-name`、`--student-id` |
| 无封面 | `--no-cover` |
| 学位论文样式 | Markdown 顶部元数据 `cover: thesis`，见 [学位论文模板](examples/学位论文模板.md) |

默认课程封面不含完成日期。存在本地校徽时使用该资源，可通过 `--logo` 指定其他真实校徽。学位封面字段与格式映射见 [格式参考](references/format-qa.md)；课程报告默认规则不能替代具体学校或课程的提交要求。

## 输出与参数

成功构建退出码为 `0`，stdout 返回 JSON 摘要及 `warnings`；警告同时写入 stderr。默认输出：

```text
report.pdf                     --pdf 指定的最终文件
course_report.tex              生成的 LaTeX
latex/report_body.md           预处理正文
latex/metadata.yaml            元数据
latex/prepare_report.json       Markdown QA
latex/postprocess_qa.json       LaTeX QA
```

| 参数 | 用途 |
| --- | --- |
| `--pdf PATH` | 主 PDF 输出，文件名须以 `.pdf` 结尾 |
| `--output-pdf PATH` | 成功 PDF 的额外复制位置 |
| `--work-dir PATH` / `--tex PATH` | 中间目录 / TeX 输出，位于源 Markdown 目录内 |
| `--skip-compile` | 预处理、Pandoc 与后处理，不编译 PDF |
| `--keep-intermediates` | 保留编译日志等中间文件 |
| `--command-timeout SECONDS` | 外部命令超时，默认 180 秒 |
| `--allow-slide-draft` | 显式允许原样转换逐页讲稿 |

完整参数见 `python3 scripts/build_course_report.py --help`。

## 验证与维护

同一报告目录的构建通过锁串行化；编译使用临时目录，成功 PDF 原子替换。图片路径、引用对应关系、表题和长表结构等关键 QA 失败会阻断构建。

修改后从本 Skill 目录执行：

```bash
python3 -m unittest discover -s tests -v
python3 scripts/run_smoke_tests.py
```

回归测试覆盖内容保全、路径、锁、超时、图片、引用、公式和长表。完整 smoke 在工具可用时实际编译；跨平台回归及指定 Pandoc 版本的 PDF 构建配置见 [CI](../../.github/workflows/pdf.yml)。

最终 PDF 应检查封面、摘要、目录、正文、跨页表格和参考文献页。QA 负责结构检查，参考文献真实性与正文内容仍需来源核验。

## 许可证与反馈

原创代码、模板、示例与文档保留 [MIT License](LICENSE)。校徽和官方格式资料另见 [第三方材料声明](THIRD_PARTY_NOTICES.md)。

问题反馈提交至 [Paper Workflow](https://github.com/Eason412/paper-workflow/issues)，附最小 Markdown、环境版本、错误信息及脱敏 QA / PDF 页面。
