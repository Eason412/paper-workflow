# Paper Workflow

文献身份解析、批量获取与报告排版工具集。以 DOI、完整标题、文章链接或参考文献清单为输入，完成开放获取检索、授权机构全文下载和失败项续传；课程报告 Skill 提供 Markdown 到 LaTeX/PDF 的排版流程。

## 功能与入口

| Skill | 主要功能 | 使用说明 |
| --- | --- | --- |
| `oa-paper-fetch` | OA 优先获取、批量清单处理、浏览器登录会话复用、下载状态与续传管理 | [中文说明](skills/oa-paper-fetch/README.zh-CN.md) · [English](skills/oa-paper-fetch/README.md) |
| `md-course-report-to-pdf` | 课程报告封面、摘要与目录生成，图表、公式和参考文献排版，双阶段 QA | [使用说明](skills/md-course-report-to-pdf/README.md) |

两个 Skill 可独立安装和调用，源码统一在本仓库维护。

## 文献获取流程

```text
标题 / DOI / URL / 批量清单
  → 身份解析与去重
  → 开放获取检索与下载
  → 未完成项的机构访问（按需启用）
  → PDF、结果报告与续传清单
```

机构访问支持 IEEE Xplore、Wiley Online Library 和 Elsevier ScienceDirect。首次使用时，由用户在可见浏览器中完成登录；浏览器在本机持久化会话，包括 Cookie，后续批次复用有效登录状态。会话过期或出现验证页面时，暂停机构任务并等待用户重新登录。

下载范围以用户已有访问权限为准。登录状态保留在本机浏览器配置目录，不导出 Cookie，不处理学校密码或验证码。

## 安装

### 仓库获取

```bash
git clone https://github.com/Eason412/paper-workflow.git
cd paper-workflow
```

### Codex 安装

macOS / Linux 可将所需 Skill 链接到个人目录。以下命令在仓库根目录执行；目标位置已有同名安装时，先核对并备份原入口。

```bash
mkdir -p "$HOME/.agents/skills"
ln -s "$PWD/skills/oa-paper-fetch" "$HOME/.agents/skills/oa-paper-fetch"
ln -s "$PWD/skills/md-course-report-to-pdf" "$HOME/.agents/skills/md-course-report-to-pdf"
```

仅需文献获取时，执行第一条链接命令即可。Windows 可将对应的完整 Skill 子目录复制到个人 Skill 目录。安装内容必须包含同目录内的脚本、模板和引用资源。

### 运行依赖

| 用途 | 依赖 |
| --- | --- |
| OA 文献获取 | Python 3.10+，仅 Python 标准库 |
| 机构登录与全文获取 | 另需 Playwright 和 Chromium；安装步骤见文献获取说明 |
| 课程报告排版 | Python 3.10+、Pandoc、Tectonic 或 XeLaTeX、可用中文字体 |

## 使用示例

### 批量文献获取

```text
使用 $oa-paper-fetch，将这份参考文献清单中的论文下载到指定目录。
先尝试开放获取，未获取到的论文使用已配置的学校访问。
```

### 首次机构登录

```text
使用 $oa-paper-fetch，打开机构登录浏览器，由我完成登录并保留本机会话。
```

### 未完成项续传

```text
使用 $oa-paper-fetch，按上次生成的 oa_fetch_pending.csv 继续下载。
```

### 课程报告生成

```text
使用 $md-course-report-to-pdf，将 report.md 转为课程报告 PDF，不添加封面。
```

文献默认保存到 `~/Desktop/Papers`，可通过请求或 CLI 的 `--out` 指定其他目录。报告排版以已有 Markdown 为输入；具体命令、状态解释和示例文件见各 Skill 的使用说明。

## 开发与维护

```text
skills/oa-paper-fetch/             文献获取源码、测试与使用说明
skills/md-course-report-to-pdf/    报告排版源码、模板、示例与测试
.github/workflows/                独立回归与 PDF 构建检查
```

源码修改在对应 Skill 子目录完成。两套测试分别执行，避免同名 Python 模块互相影响：

```bash
cd skills/oa-paper-fetch
python3 -m unittest discover -s tests -v
cd ../md-course-report-to-pdf
python3 -m unittest discover -s tests -v
python3 scripts/run_smoke_tests.py
```

问题反馈与 PR 应包含最小复现、预期和实际结果、解决思路及验证记录，见 [贡献指南](CONTRIBUTING.md)。日志、截图和输入样例须去除个人信息及认证数据。

## 许可证

两项 Skill 的原创代码分别保留原有 MIT 许可证：[文献获取](skills/oa-paper-fetch/LICENSE)、[报告排版](skills/md-course-report-to-pdf/LICENSE)。报告排版所附校徽与官方格式资料的来源和权利说明见 [第三方材料声明](skills/md-course-report-to-pdf/THIRD_PARTY_NOTICES.md)。
