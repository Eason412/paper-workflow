# Paper Workflow 项目规则

本仓库维护三个相互独立的学术类 Agent Skill：文献获取、课程报告排版和论文数据图。运行行为以各 Skill 的源码与测试为准，任务按对应 `SKILL.md` 执行。

## 工作范围

| 任务 | 入口 |
| --- | --- |
| 文献获取开发 | [文献获取维护规则](skills/oa-paper-fetch/AGENTS.md) |
| 文献获取执行 | [oa-paper-fetch](skills/oa-paper-fetch/SKILL.md) |
| 报告排版开发与执行 | [course-report](skills/course-report/SKILL.md)，格式问题按需读取其 QA 参考 |
| 论文数据图 | [paper-figure](skills/paper-figure/SKILL.md) |
| 安装、导航与 CI | 根 README、[SETUP.md](SETUP.md)、贡献指南和 `.github/workflows/` |

每个 Skill 保持完整安装单元，不依赖另一个 Skill 或总仓库根目录运行。入口为 `SKILL.md`，Codex 的显示信息放在 `agents/openai.yaml`。

本机的 `~/.codex/skills/<name>`、`~/.claude/skills/<name>` 由 `scripts/link-skills.sh` 软链到本仓库 `skills/<name>`，在本机优化 Skill 即修改本仓库；验证通过后提交并推送。新增 Skill 后重跑该脚本。写作与文档类 Skill 在姊妹仓库 doc-workflow 维护。

## 修改与验证

- 先检查 Git 状态，保留现有改动；只处理用户要求及其必要关联变更。
- 行为修复补充回归测试。用户可见命令、状态或依赖变化同步使用说明；文献获取的中英文 README 保持一致，根目录 README 与 README.en.md 保持一致。
- 测试在各自 Skill 目录、独立进程中执行：

| Skill | 命令 |
| --- | --- |
| oa-paper-fetch、course-report | `PYTHONDONTWRITEBYTECODE=1 uv run --no-project python -m unittest discover -s tests -v` |
| 仓库卫生 | 在根目录运行 `PYTHONDONTWRITEBYTECODE=1 uv run --no-project python -m unittest discover -s tests -v` |

- 排版、模板或内容转换变化运行 course-report 的 `uv run scripts/run_smoke_tests.py`，并按影响检查实际 PDF；纯文字修订不要求重跑完整编译。
- 修改 Skill 规范后，用 `quick_validate.py` 等校验工具检查 frontmatter；README 改动用 project-docs（doc-workflow 仓库）的 `check_readme.py` 检查链接。
- 并行任务按 Skill 或文件划分所有权；主代理负责公共文件、整合验证和范围变化通知，不回退其他执行者改动。

## 数据与发布

开发测试使用临时输入、模拟网络和隔离输出。机构登录、真实下载或依赖安装需要相应授权；浏览器 profile、Cookie、凭据、受限全文、私人报告和本机绝对路径不进入源码或提示词。

提交前检查差异和相对链接，使用 GitHub noreply 邮箱，保留各 Skill 的许可证及第三方声明。远端更名、公开和删除按用户授权范围执行；破坏性操作先说明具体目标及影响并等待确认。

交付区分源码修改、安装入口、测试、真实运行和推送结果，不把静态检查或 CI 成功写成机构访问验收。
