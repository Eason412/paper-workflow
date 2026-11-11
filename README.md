# Paper Workflow

中文 | [English](README.en.md)

**围绕文献获取、论文数据图与中文论文写作，按学术任务独立选用 Skill。** 本仓库收录 `oa-paper-fetch`、`paper-figure` 和 `paper-writing-zh` 三个学术类 Agent Skill。Skill 是以 `SKILL.md` 定义的任务规范，可附带脚本和参考资料。

最近发布版本：[V0.1.0](https://github.com/Eason412/paper-workflow/releases/tag/V0.1.0)（[全部版本与更新说明](https://github.com/Eason412/paper-workflow/releases)）；`main` 分支在此之后已有增删更新。原课程报告排版技能 `course-report` 已归档，完整内容见 [V0.1.0 版本](https://github.com/Eason412/paper-workflow/tree/V0.1.0/skills/course-report)。

> ⚠️ 各 Skill 的依赖按任务准备；机构全文获取需要已有访问权限，登录与验证由用户本人完成。文献获取不用于 Sci-Hub 或绕过付费墙。

论文写作归本仓库；其他写作与文档类 Skill 收录于姊妹仓库 [doc-workflow](https://github.com/Eason412/doc-workflow)。

## ✨ 特点

- 📚 **开放获取优先与批量续传**：支持 DOI、标题、链接和参考文献清单；优先下载可开放获取的 PDF，必要时复用已登录的 IEEE、Wiley、ScienceDirect 会话，并复用已验证的下载结果。
- 📊 **论证导向的论文数据图**：根据论证目标与数据形态选图，按期刊成品尺寸处理字号、中文字体、色盲安全配色和矢量导出，并渲染检查成图。
- ✍️ **事实不增减的中文论文写作与改稿**：覆盖句子搭配、段首句衔接、图表前后文与摘要结论体例，改稿后自动比对数字、引用编号、符号、标点与双语摘要数据。

## 🧩 Skill 目录

| Skill | 用途 | 入口 |
| --- | --- | --- |
| `oa-paper-fetch` | 开放获取、授权机构全文、批量与续传 | [任务规范](skills/oa-paper-fetch/SKILL.md)（英文）· [中文说明](skills/oa-paper-fetch/README.zh-CN.md) · [英文说明](skills/oa-paper-fetch/README.md) |
| `paper-figure` | 论文数据图的选图、尺寸与导出检查 | [任务规范](skills/paper-figure/SKILL.md) · [选图参考](skills/paper-figure/references/chart_selection.md) |
| `paper-writing-zh` | 中文学术论文与综述的起草、改稿及事实核对 | [任务规范](skills/paper-writing-zh/SKILL.md) · [句子与搭配](skills/paper-writing-zh/references/sentence.md) |

- **独立安装**：各 `skills/<name>` 目录均为独立安装单元，运行资源随目录保留。
- **宿主**：Codex、Claude Code 等支持 `SKILL.md` 的 Agent 可使用这些规范；脚本执行、浏览器控制和读图能力由宿主提供。
- **适用范围**：`paper-figure` 面向数据图，示意图、流程图和架构图不属于其范围；`paper-writing-zh` 面向中文学术论文、综述与学位论文正文，非论文中文写作归 `doc-workflow`。

## 🛠️ 运行条件

| Skill | 基础依赖 | 按需依赖 |
| --- | --- | --- |
| `oa-paper-fetch` | uv、Python 3.12+；OA 层仅用标准库 | 机构 CLI：Playwright 1.40+、Chrome 或 Chromium；已有会话：浏览器控制工具 |
| `paper-figure` | uv、Python、matplotlib、seaborn、读图工具 | 中文数据图：中文字体；PDF 字体检查：`pdffonts` |
| `paper-writing-zh` | Agent；文本规范无额外软件包 | 改稿事实核对脚本：uv、Python 3.9+（仅标准库） |

- **Python 版本**：`oa-paper-fetch` 的独立 OA 脚本兼容 Python 3.10+，uv 项目要求 Python 3.12+；`paper-writing-zh` 的事实核对脚本仅用标准库；`paper-figure` 未声明固定 Python 或绘图库版本。
- **依赖出处**：依赖出处与验收步骤见 [SETUP.md](SETUP.md)（英文）。

## 🚀 设置方法

- **设置**：由 Agent 读取 [SETUP.md](SETUP.md)（英文）完成安装与所需依赖检查。
- **完成后**：重新打开 Agent 会话，确认 Skill 已被发现。
- **需用户亲自完成**：机构访问的账号登录、单点登录与多因素验证。

| 设置项 | 位置 | 用途 |
| --- | --- | --- |
| 文献输出与访问偏好 | `~/.oa-paper-fetch/config.json`、CLI 参数 | 默认输出位置、访问方式与单次任务设置 |
| 数据图规格 | 本次任务、绘图代码 | 论证目标、期刊、尺寸、字体与输出格式 |
| 论文术语与样刊体例 | 论文项目目录的术语表或符号表、本次任务 | 单篇固定译法、符号定义与目标刊物图表体例 |

## 📁 仓库结构

| 路径 | 用途 |
| --- | --- |
| `skills/<name>/SKILL.md` | 各 Skill 的任务入口 |
| `skills/<name>/agents/openai.yaml` | Codex 显示信息 |
| `skills/<name>/references/` | 工作流、选图与写作参考 |
| `skills/paper-writing-zh/scripts/` | 论文改稿事实核对脚本 |
| `skills/oa-paper-fetch/*.py` | 文献获取、身份解析、配置与恢复状态 |
| `skills/<name>/tests/`（若有）、`tests/` | Skill 回归与仓库卫生检查 |
| [scripts/link-skills.sh](scripts/link-skills.sh) | 个人 Skill 入口的链接安装 |
| [SETUP.md](SETUP.md) | 面向 Agent 的设置与验收手册（英文） |
| [AGENTS.md](AGENTS.md)、[CONTRIBUTING.md](CONTRIBUTING.md) | 项目规则与贡献要求 |
| [.github/workflows/](.github/workflows/) | 文献获取与论文写作核对配置 |

修改与验证规则见 [AGENTS.md](AGENTS.md)。

## 🤝 贡献须知

欢迎提交兼容修复、功能改进与文档修订。提交 PR 前请注意：

- **范围**：PR 聚焦一个问题，附受影响的 Skill、最小复现、预期与实际结果及验证记录。
- **行为修改**：同步更新测试和说明。
- **隐私与署名**：样例与日志去除个人信息和认证数据，保留各 Skill 的许可证与署名。

完整要求见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 📄 许可证与署名

许可证按各 Skill 目录内的文件确定，根目录没有统一 `LICENSE`。

| Skill | 许可证 | 版权署名 |
| --- | --- | --- |
| `oa-paper-fetch` | [MIT（英文）](skills/oa-paper-fetch/LICENSE) | Eason412 |
| `paper-figure` | [MIT（英文）](skills/paper-figure/LICENSE) | Haojae |
| `paper-writing-zh` | [MIT（英文）](skills/paper-writing-zh/LICENSE) | Eason412 |
