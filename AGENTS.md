# Paper Workflow 项目规则

先读上级 [opensource 工作区规则](../AGENTS.md)。本仓库维护三个相互独立的学术类 Agent Skill：文献获取、论文数据图和中文学术论文写作与改稿。**论文写作归 `paper-workflow`，其他写作归 `doc-workflow`。**

## 工作范围

| 任务 | 入口 |
| --- | --- |
| 文献获取开发 | [文献获取维护规则](skills/oa-paper-fetch/AGENTS.md) |
| 文献获取执行 | [oa-paper-fetch](skills/oa-paper-fetch/SKILL.md) |
| 论文数据图 | [paper-figure](skills/paper-figure/SKILL.md) |
| 中文论文写作与改稿 | [paper-writing-zh](skills/paper-writing-zh/SKILL.md) |
| 安装、导航与 CI | 根 README、[SETUP.md](SETUP.md)、贡献指南和 `.github/workflows/` |

每个 Skill 保持完整安装单元，入口为 `SKILL.md`、Codex 显示信息放在 `agents/openai.yaml`。本机安装、分发与推送规矩见上级规则；独立环境可用 `scripts/link-skills.sh`。

## 修改与验证

- 行为修复补充回归测试。用户可见命令、状态或依赖变化同步使用说明；文献获取的中英文 README 保持一致，根目录 `README.md` 与 `README.en.md` 保持一致。
- 测试在各自 Skill 目录、独立进程中执行：

| Skill | 命令 |
| --- | --- |
| oa-paper-fetch | `PYTHONDONTWRITEBYTECODE=1 uv run --no-project python -m unittest discover -s tests -v` |
| 仓库卫生与 paper-writing-zh | 在根目录运行 `PYTHONDONTWRITEBYTECODE=1 uv run --no-project python -m unittest discover -s tests -v` |

- 论文写作规范的重要修改按技能 `rules-maintenance`「写作技能记录、复盘与盲测」做新旧对照盲测，并运行 `uv run skills/paper-writing-zh/scripts/compare_facts.py` 核对数字、引用与符号。
- 修改 Skill 规范后，用 `quick_validate.py` 等校验工具检查 frontmatter；README 改动用 `project-docs`（`doc-workflow` 仓库）的 `check_readme.py` 检查链接。
- 并行任务按 Skill 或文件划分所有权；主代理负责公共文件、整合验证和范围变化通知。

## 数据与发布

开发测试使用临时输入、模拟网络和隔离输出。机构访问复用用户已登录的可见浏览器会话，**不把出版商账号密码写进仓库或 `凭据.md`**；浏览器 profile、Cookie、受限全文、未发表手稿和本机绝对路径不进入源码或提示词。

使用 GitHub noreply 邮箱提交并保留各 Skill 的许可证；远端更名、公开和删除按用户授权范围执行。交付区分源码修改、安装入口、测试、真实运行和推送结果，不把静态检查或 CI 成功写成机构访问验收。
