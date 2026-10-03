---
name: course-report
description: "把中文 Markdown 课程报告或作业排版成带封面、摘要、目录、图表编号与参考文献的 PDF，并检查成品。普通 Markdown 转 PDF 不用本 skill。"
---

# 课程报告排版

以已有 Markdown 和本地图片生成 LaTeX/PDF；不自动改写正文或补写文献。
将 `SKILL_DIR` 设为当前加载的 `SKILL.md` 所在目录的绝对路径，不依赖安装位置。
调整格式、处理复杂图表引用或排查失败时，按需读 [格式与 QA](references/format-qa.md)。

## 输入与封面

- `#` 是报告题目，正文从 `##` 开始；章节、图表与公式由模板编号，图表题只写纯标题。
- 每张表都要有表题：表前或表后写 `: 标题` 或 `Table: 标题`；`表: 标题` 会被当成正文。
- `## 摘要`、`## Abstract` 及其关键词行会被提取到前置摘要页，缺失时给 warning。
- 图片路径相对于源 Markdown 目录，不使用绝对路径或越出该目录的路径。
- 源文件顶部的 front matter 只支持单行 `key: value`。
- 课程封面：从本次请求或源文件读取课程、姓名、学号，只询问缺失字段，不复用历史信息；默认不加完成日期。
- 无封面：传 `--no-cover`，无需询问封面字段或校徽。
- 学位样式封面：源文件顶部写 `cover: thesis`；字段见 [学位封面示例](examples/学位论文模板.md)，仅借用字段布局，不代表完整学位论文规范。
- 默认使用本地附带校徽（若存在）；`--logo` 可指定其他校徽。

## 构建

在报告目录执行；封面参数按所选模式调整：

```bash
uv run "$SKILL_DIR/scripts/build_course_report.py" report.md \
  --course "课程名称" --student-name "姓名" --student-id "学号" \
  --pdf "report.pdf"
```

重复数字引用默认仅保留首次正文出现；需要重复引用时传 `--keep-repeated-citations`。
参考文献默认隐藏原始 URL/DOI URL；需要显示时传 `--keep-reference-urls`。
不支持 `--citeproc`；使用源文件中的数字引用与文后条目，不编造来源。
讲稿式输入会给出 warning，不会自动改写；`--allow-slide-draft` 已废弃且无效果。

## 验收与维护

读取 stdout JSON 的 `warnings`，以及 `latex/prepare_report.json`、`latex/postprocess_qa.json`；失败时修正对应输入或实现。
版式变化后检查实际 PDF 的封面、摘要、目录、正文、跨页表格和参考文献，结构 QA 不能替代目视检查。
修改脚本或模板后运行 `uv run "$SKILL_DIR/scripts/run_smoke_tests.py"`，再用于真实报告。

入口脚本保留在 `scripts/prepare_course_report.py`、`scripts/build_course_report.py` 和 `scripts/run_smoke_tests.py`；同目录的职责模块需随 Skill 一并安装。模块职责与两种加载方式见 [脚本结构](README.md#脚本结构)。
