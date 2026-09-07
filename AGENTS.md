# Paper Workflow 项目规则

本仓库维护两个独立的 Codex Skill。运行行为以各 Skill 的源码与测试为准，下载或排版任务按对应 `SKILL.md` 执行。

## 工作范围

| 任务 | 入口 |
| --- | --- |
| 文献获取开发 | [文献获取维护规则](skills/oa-paper-fetch/AGENTS.md) |
| 文献获取执行 | [文献获取 Skill](skills/oa-paper-fetch/SKILL.md) |
| 报告排版开发与执行 | [报告排版 Skill](skills/md-course-report-to-pdf/SKILL.md)，格式问题按需读取其 QA 参考 |
| 安装、导航与 CI | 根 README、贡献指南和 `.github/workflows/` |

每个 Skill 保持完整安装单元，不依赖另一个 Skill 或总仓库根目录运行。只维护 Codex 的 `SKILL.md` 与 `agents/openai.yaml` 入口。

## 修改与验证

- 先检查 Git 状态，保留现有改动；只处理用户要求及其必要关联变更。
- 行为修复补充回归测试。用户可见命令、状态或依赖变化同步使用说明；文献获取的中英文 README 保持一致。
- 两套测试在各自 Skill 目录、独立进程中执行：`python3 -m unittest discover -s tests -v`。
- 排版、模板或内容转换变化运行 `scripts/run_smoke_tests.py`，并按影响检查实际 PDF；纯文字修订不要求重跑完整编译。
- 并行任务按 Skill 或文件划分所有权；主代理负责公共文件、整合验证和范围变化通知，不回退其他执行者改动。

## 数据与发布

开发测试使用临时输入、模拟网络和隔离输出。机构登录、真实下载或依赖安装需要相应授权；浏览器 profile、Cookie、凭据、受限全文和私人报告不进入源码或提示词。

提交前检查差异和相对链接，使用 GitHub noreply 邮箱，保留原许可证及第三方声明。远端更名、公开和删除按用户授权范围执行；破坏性操作先说明具体目标及影响并等待确认。

交付区分源码修改、安装入口、测试、真实运行和推送结果，不把静态检查或 CI 成功写成机构访问验收。
