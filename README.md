# Paper Workflow

中文 | [English](README.en.md)

**从文献获取到课程报告和论文数据图，按学术任务独立选用 Skill。** 本仓库收录 `oa-paper-fetch`、`course-report` 和 `paper-figure` 三个学术类 Agent Skill。Skill 是以 `SKILL.md` 定义的任务规范，可附带脚本、模板和参考资料。

> ⚠️ 各 Skill 的依赖按任务准备；机构全文获取需要已有访问权限，登录与验证由用户本人完成。文献获取不用于 Sci-Hub 或绕过付费墙。

写作与文档类 Skill 收录于姊妹仓库 [doc-workflow](https://github.com/Eason412/doc-workflow)。

## ✨ 特点

- 📚 **开放获取优先与批量续传**：支持 DOI、标题、链接和参考文献清单；优先下载可开放获取的 PDF，必要时复用已登录的 IEEE、Wiley、ScienceDirect 会话，并复用已验证的下载结果。
- 🖨️ **完整课程报告排版**：中文 Markdown 生成带封面、摘要、目录、图表与公式编号、参考文献的 PDF，配套 Markdown 与 LaTeX 结构检查及成品检查流程。
- 📊 **论证导向的论文数据图**：根据论证目标与数据形态选图，按期刊成品尺寸处理字号、中文字体、色盲安全配色和矢量导出，并渲染检查成图。

## 🧩 Skill 目录

| Skill | 用途 | 入口 |
| --- | --- | --- |
| `oa-paper-fetch` | 开放获取、授权机构全文、批量与续传 | [任务规范](skills/oa-paper-fetch/SKILL.md)（英文）· [中文说明](skills/oa-paper-fetch/README.zh-CN.md) · [英文说明](skills/oa-paper-fetch/README.md) |
| `course-report` | 中文课程报告的 PDF 排版与检查 | [任务规范](skills/course-report/SKILL.md) · [使用说明](skills/course-report/README.md) |
| `paper-figure` | 论文数据图的选图、尺寸与导出检查 | [任务规范](skills/paper-figure/SKILL.md) · [选图参考](skills/paper-figure/references/chart_selection.md) |

各 `skills/<name>` 目录均为独立安装单元，运行资源随目录保留。Codex、Claude Code 等支持 `SKILL.md` 的 Agent 可使用这些规范；脚本执行、浏览器控制和读图能力由宿主提供。

`course-report` 面向课程报告或作业；学位样式只借用封面字段布局。`paper-figure` 面向数据图，示意图、流程图和架构图不属于其范围。

## 🛠️ 运行条件

| Skill | 基础依赖 | 按需依赖 |
| --- | --- | --- |
| `oa-paper-fetch` | uv、Python 3.12+；OA 层仅用标准库 | 机构 CLI：Playwright 1.40+、Chrome 或 Chromium；已有会话：浏览器控制工具 |
| `course-report` | uv、Python 3.10+、Pandoc；无第三方 Python 包 | PDF：Tectonic 或 XeLaTeX、中英字体；扩展 QA：Poppler、qpdf |
| `paper-figure` | uv、Python、matplotlib、seaborn、读图工具 | 中文数据图：中文字体；PDF 字体检查：`pdffonts` |

`oa-paper-fetch` 的独立 OA 脚本兼容 Python 3.10+，uv 项目要求 Python 3.12+。`course-report` 仅生成 LaTeX 时仍需 Pandoc；编译器同时存在时优先使用 Tectonic，首次编译可能下载 TeX 资源。`paper-figure` 未声明固定 Python 或绘图库版本。依赖出处与验收步骤见 [SETUP.md](SETUP.md)（英文）。

## 🚀 设置方法

由 Agent 读取 [SETUP.md](SETUP.md)（英文）完成安装与所需依赖检查。安装完成后重新打开 Agent 会话，确认 Skill 已被发现。机构访问的账号登录、单点登录与多因素验证由用户本人完成。

| 设置项 | 位置 | 用途 |
| --- | --- | --- |
| 文献输出与访问偏好 | `~/.oa-paper-fetch/config.json`、CLI 参数 | 默认输出位置、访问方式与单次任务设置 |
| 报告封面与引用 | 源 Markdown 元数据、构建参数 | 课程、姓名、学号、封面模式与引用保留 |
| 数据图规格 | 本次任务、绘图代码 | 论证目标、期刊、尺寸、字体与输出格式 |

## 📁 仓库结构

| 路径 | 用途 |
| --- | --- |
| `skills/<name>/SKILL.md` | 各 Skill 的任务入口 |
| `skills/<name>/agents/openai.yaml` | Codex 显示信息 |
| `skills/<name>/references/` | 工作流、格式与选图参考 |
| `skills/course-report/scripts/`、`assets/`、`examples/` | 报告构建、模板与样例 |
| `skills/oa-paper-fetch/*.py` | 文献获取、身份解析、配置与恢复状态 |
| `skills/<name>/tests/`（若有）、`tests/` | Skill 回归与仓库卫生检查 |
| [scripts/link-skills.sh](scripts/link-skills.sh) | 个人 Skill 入口的链接安装 |
| [SETUP.md](SETUP.md) | 面向 Agent 的设置与验收手册（英文） |
| [AGENTS.md](AGENTS.md)、[CONTRIBUTING.md](CONTRIBUTING.md) | 项目规则与贡献要求 |
| [.github/workflows/](.github/workflows/) | 文献获取回归与报告 PDF 构建配置 |

修改与验证规则见 [AGENTS.md](AGENTS.md)。

## 🤝 贡献须知

PR 聚焦一个问题，附受影响的 Skill、最小复现、预期与实际结果及验证记录；行为变更同步测试和说明。样例与日志应去除个人信息和认证数据，保留各 Skill 的许可证与第三方署名。完整要求见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 📄 许可证与署名

许可证按各 Skill 目录内的文件确定，根目录没有统一 `LICENSE`。

| Skill | 许可证 | 版权署名 |
| --- | --- | --- |
| `oa-paper-fetch` | [MIT（英文）](skills/oa-paper-fetch/LICENSE) | Eason412 |
| `course-report` | [MIT（英文）](skills/course-report/LICENSE) | Huyi |
| `paper-figure` | [MIT（英文）](skills/paper-figure/LICENSE) | Haojae |

`course-report` 的校徽与官方格式资料另见 [THIRD_PARTY_NOTICES.md](skills/course-report/THIRD_PARTY_NOTICES.md)（英文）；相关名称、标识与材料的权利归原权利人。
