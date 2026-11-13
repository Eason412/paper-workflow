# Paper Workflow 项目规则

本仓库维护三个相互独立的学术类 Agent Skill：文献获取、论文数据图和中文学术论文写作与改稿。运行行为以各 Skill 的源码与测试为准，任务按对应 `SKILL.md` 执行。

## 工作范围

| 任务 | 入口 |
| --- | --- |
| 文献获取开发 | [文献获取维护规则](skills/oa-paper-fetch/AGENTS.md) |
| 文献获取执行 | [oa-paper-fetch](skills/oa-paper-fetch/SKILL.md) |
| 论文数据图 | [paper-figure](skills/paper-figure/SKILL.md) |
| 中文论文写作与改稿 | [paper-writing-zh](skills/paper-writing-zh/SKILL.md) |
| 安装、导航与 CI | 根 README、[SETUP.md](SETUP.md)、贡献指南和 `.github/workflows/` |

每个 Skill 保持完整安装单元，不依赖另一个 Skill 或总仓库根目录运行。入口为 `SKILL.md`，Codex 的显示信息放在 `agents/openai.yaml`。

使用 Magpie 资源库的环境经 `~/.config/magpie/library/skills/<name>` 软链到本仓库 `skills/<name>` 并统一分发到各客户端（不再运行 `scripts/link-skills.sh`）；独立环境可用 `scripts/link-skills.sh` 软链到 `~/.codex/skills` 与 `~/.claude/skills`。软链下本地优化 Skill 即修改本仓库，验证通过后提交并推送。**论文写作归 paper-workflow，其他写作归 doc-workflow。**

## 修改与验证

- 先检查 Git 状态，保留现有改动；只处理用户要求及其必要关联变更。
- 行为修复补充回归测试。用户可见命令、状态或依赖变化同步使用说明；文献获取的中英文 README 保持一致，根目录 README 与 README.en.md 保持一致。
- 测试在各自 Skill 目录、独立进程中执行：

| Skill | 命令 |
| --- | --- |
| oa-paper-fetch | `PYTHONDONTWRITEBYTECODE=1 uv run --no-project python -m unittest discover -s tests -v` |
| 仓库卫生与 paper-writing-zh | 在根目录运行 `PYTHONDONTWRITEBYTECODE=1 uv run --no-project python -m unittest discover -s tests -v` |

- 论文写作规范的重要修改做新旧双盲对照验证，并运行 `uv run skills/paper-writing-zh/scripts/compare_facts.py` 核对数字、引用与符号。
- 修改 Skill 规范后，用 `quick_validate.py` 等校验工具检查 frontmatter；README 改动用 project-docs（doc-workflow 仓库）的 `check_readme.py` 检查链接。
- 并行任务按 Skill 或文件划分所有权；主代理负责公共文件、整合验证和范围变化通知，不回退其他执行者改动。

## 数据与发布

开发测试使用临时输入、模拟网络和隔离输出。机构登录、真实下载或依赖安装需要相应授权；浏览器 profile、Cookie、凭据、受限全文、未发表手稿和本机绝对路径不进入源码或提示词。

提交前检查差异和相对链接，使用 GitHub noreply 邮箱，保留各 Skill 的许可证。远端更名、公开和删除按用户授权范围执行；破坏性操作先说明具体目标及影响并等待确认。

交付区分源码修改、安装入口、测试、真实运行和推送结果，不把静态检查或 CI 成功写成机构访问验收。
