# OA Paper Fetch

**简体中文** | [English](README.md)

文献身份解析、开放获取检索与授权机构全文下载。支持完整标题、DOI、URL、Markdown、CSV 和逐行清单，提供批量处理、浏览器登录会话复用、准确文件命名及失败项续传。

默认输出目录为 `~/Desktop/Papers`；当前 CLI 版本为 `0.5.0`，独立运行的 OA 层需要 Python 3.10+、仅使用标准库；uv 管理的环境需要 Python 3.12+。纯 OA 命令不安装第三方包；机构访问按下文启用可选依赖。

## 安装与入口

Skill 安装见 [Paper Workflow 安装手册](../../SETUP.md)，总仓库维护见 [Paper Workflow](../../README.md)。本目录为独立安装单元，需保留全部 Python 模块及配套资源。`oa_fetch.py` 仍为 CLI 入口；元数据、传输、来源查询、身份确认、获取编排和报告按职责分模块。文件布局见[源码与测试导航](AGENTS.md#源码与测试导航)。

从总仓库根目录进入后，后续命令均在本 Skill 目录执行：

```bash
cd skills/oa-paper-fetch
uv run python oa_fetch.py --help
```

Codex 调用示例：

```text
使用 $oa-paper-fetch，将这份参考文献清单中的论文下载到指定目录。
先尝试开放获取，未完成项使用已配置的学校访问。
```

Codex 通过 [SKILL.md](SKILL.md) 读取规范工作流，通过 `agents/openai.yaml` 获取 Skill 元数据。安装入口统一指向本目录。

## OA 文献获取

```bash
uv run python oa_fetch.py --oa-only --url "https://arxiv.org/abs/1706.03762" --format text
```

成功后，PDF 和结果报告保存到默认目录。可使用 `--out` 指定本次输出位置，或通过 `--save-config` 保存用户明确指定的默认位置。

OA 候选包括直接 PDF、arXiv、OpenAlex、Unpaywall 和 Semantic Scholar。Unpaywall 可使用本机已配置的 `UNPAYWALL_EMAIL`。

正常下载按来源逐个查询并立即尝试候选，PDF 成功后不再查询后续来源。OpenAlex 和 Unpaywall 的结果优先尝试直接 PDF 地址，再尝试落地页；跳过 OpenAlex 明确标为非开放获取的位置。dry-run 仍收集完整候选证据。

## 批量清单与身份解析

CSV 使用以下字段；未知信息留空：

```csv
id,title,doi,url
ref-001,Exact Full Paper Title,,
ref-002,,10.xxxx/yyyy,
```

以下绝对路径均为占位符，替换为实际输入和输出路径：

```bash
uv run python oa_fetch.py --oa-only --batch "/absolute/references.csv" --out "/absolute/papers" --format text
```

支持 Markdown 表格和逐行纯文本。DOI、URL 为硬去重依据；同标题记录只标记疑似重复，保留各自身份。重复输入 ID 会分配无冲突后缀。

标题解析查询 arXiv、Crossref 和 OpenAlex。Crossref 候选发现阈值为 `0.62`，多源身份确认阈值为 `0.85`；确认需要至少两个独立来源支持同一个 DOI。机构页面的出版商标题核验另用 `0.93` 阈值。单一精确匹配不足以完成确认。身份歧义和无法解析的记录不会继续进入机构获取。

离线清单预检仅执行规范化与去重：

```bash
uv run python oa_fetch.py --batch "/absolute/references.csv" --manifest-out "/absolute/oa_fetch_manifest.csv"
```

`--manifest-out` 必须与 `--batch` 配合，不发起元数据查询或 PDF 下载。

## 浏览器登录与会话复用

### 可选依赖

仅机构访问需要 Playwright 和 Chromium：

这些安装命令须取得授权。后续 CLI 按已保存偏好启用机构访问时，也需添加
`--extra institutional`。

```bash
uv sync --extra institutional
uv run --extra institutional python -m playwright install chromium
```

### 首次登录与会话刷新

```bash
uv run --extra institutional python oa_fetch.py --institutional-login
```

程序打开可见浏览器及 IEEE Xplore、Wiley Online Library、Elsevier ScienceDirect 页面。用户自行选择机构访问并完成 SSO/MFA，完成后回到终端按 Enter。

浏览器使用独立的本机持久化目录 `~/.oa-paper-fetch/profile` 保存登录状态，包括浏览器管理的 Cookie；不连接日常浏览器的个人 profile。工具不读取或导出 Cookie，不填写账号、密码及验证码，也不绕过访问控制。该目录不进入 Git 或同步备份。

### 授权机构获取

```bash
uv run --extra institutional python oa_fetch.py --batch "/absolute/references.csv" --out "/absolute/papers" --institutional --format text
```

OA 阶段优先执行，未完成且身份符合条件的记录才进入机构阶段。机构范围固定为 IEEE Xplore、Wiley Online Library 和 Elsevier ScienceDirect。

有效会话可跨运行复用。`--headless` 仅用于复用已有有效会话；首次登录和失效修复使用可见浏览器。缺失会话返回 `profile_missing_login_required`，登录失效返回 `login_refresh_required`。

## 代理协助的浏览器流程

如果 Chrome 已有用户授权的登录，Codex 可使用可用的浏览器控制工具继续在同一会话操作。这与 CLI 的独立 profile 是两种执行模式，二者不转移登录数据。操作细节见[浏览器流程](references/browser-workflow.md)。

批量开始前明确期刊和数量，检查指定本地目录及已有下载记录是否可复用，并完成一篇论文的保存与身份核验。同一出版商由一个代理持有浏览器，其他代理可独立核验文件，避免交接正在使用的标签页。按期刊分目录、复用 CLI 状态之外的 PDF 由代理组织，并非新增 CLI 参数。下载保存完成后再关闭本次创建的页面。

两种机构访问方式均采用至少 4 秒的基础间隔、0–10 秒 jitter，每轮最多尝试 30 次。浏览器流程需显式计数，切换方式不重置本轮计数。

## 参数偏好与批次控制

非敏感偏好保存在 `~/.oa-paper-fetch/config.json`。优先级为本次显式参数、本地配置、内置默认值。只有用户要求时才保存长期设置：

```bash
uv run python oa_fetch.py --institutional --inst-delay 4 --inst-jitter 3 --max-institutional 30 --save-config
```

本次仅用 OA 时添加 `--oa-only`。常用参数如下，完整列表见 `--help`：

| 参数 | 默认值与范围 |
| --- | --- |
| `--out` | `~/Desktop/Papers`，或已保存的目录 |
| `--oa-delay` | 1 秒；0–60 秒 |
| `--timeout` | 30 秒；5–300 秒 |
| `--inst-delay` | 4 秒；4–86400 秒 |
| `--inst-jitter` | 3 秒；0–10 秒 |
| `--max-institutional` | 30 次；1–30 次 |
| `--browser-profile` | `~/.oa-paper-fetch/profile` |
| `--dry-run` | 查询候选与写结果报告，不下载 PDF、不写恢复状态、不进入机构阶段 |

所有获取串行执行。机构阶段从上次成功 PDF 起累计三次 HTTP 4xx、验证或登录阻断后停止；达到批次上限返回 `institutional_cap_reached`。工具不自动追加机构批次。

## 状态与续传

同一清单和输出目录的再次执行用于续传。已验证文件返回 `exists`；缺失或损坏文件重新获取。PDF 提交与恢复采用一致的轻量检查：长度大于 5 字节且以 `%PDF` 开头。

机构阶段逐篇合并元数据、完成命名并保存检查点。批次中断后，已完成检查点的论文直接复用；检查点写入失败时停止后续机构请求并返回 `4`，保留已落盘状态和原 PDF。下载响应逐项释放，避免响应正文一直累积到整批结束；80 MiB 仍为文件大小检查，不是传输过程的内存硬上限。

文件名采用 `年份_第一作者_完整标题_稳定哈希.pdf`，保留 8 位身份后缀和 240 字节 UTF-8 长度限制。命名迁移通过无覆盖硬链接和状态持久化完成；失败时保留原文件。

需要显式继续时生成 `oa_fetch_pending.csv`。登录失效须先刷新会话，批次上限须等待新的继续请求：

```bash
uv run --extra institutional python oa_fetch.py --batch "/absolute/papers/oa_fetch_pending.csv" --out "/absolute/papers" --institutional
```

同一输出目录一次只运行一个任务。结构损坏或版本不受支持的状态文件保留原样并返回退出码 `4`，不静默重置。

迁移细节、身份解析证据和混合 pending 原因见[恢复与命名](references/recovery-naming.md)。

| 状态 / 原因 | 含义或处理 |
| --- | --- |
| `candidate` | dry-run 候选，未下载 |
| `downloaded` / `exists` | 本轮获取成功 / 已有文件通过检查 |
| `duplicate` | DOI 或 URL 重复 |
| `failed` / `pending` | 获取失败 / 需要进一步处理 |
| `title_resolution_ambiguous` | 候选 DOI 冲突，需补充身份信息 |
| `title_resolution_unresolved` | 无法确认身份，需补充 DOI、文章 URL 或准确标题 |
| `not_pdf_browser_download_required` | ScienceDirect 返回 HTML；记为 `failed`，诊断保存在 JSON 的 `institutional.error`，不进入 pending CSV；已有授权时可转正常浏览器 PDF 流程 |
| `publisher_title_mismatch` | 出版商标题与预期不符 |
| `publisher_title_unverifiable` | 出版商页面缺少可核验标题 |
| `profile_missing_login_required` / `login_refresh_required` | 首次登录 / 会话刷新 |
| `institutional_cap_reached` | 本轮机构访问上限 |

## 输出与退出码

常规任务完成报告阶段后，stdout 为一个 JSON payload；进度写入 stderr。帮助、版本和可见登录使用交互文本，早期错误可能在 JSON 生成前退出。

输出包括 PDF、`oa_fetch_manifest.csv`、`oa_fetch_results.json`、`oa_fetch_results.csv`、`oa_fetch_state.json` 和按需生成的 `oa_fetch_pending.csv`。结果报告保留身份解析、候选、获取尝试及失败原因。

退出码：`0` 成功或可用预检；`1` 存在失败/待处理项；`2` 参数或配置错误；`3` 输入缺失、为空或不可执行；`4` 传输或持久化失败。

## 开发与反馈

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python -m unittest discover -s tests -v
uv run python oa_fetch.py --version
```

离线测试使用临时配置和模拟响应，并在测试进程与 CLI 子进程中阻断未模拟的网络和浏览器访问；真实机构登录及下载由用户在授权环境完成。开发规则见 [AGENTS.md](AGENTS.md)，下载工作流见 [SKILL.md](SKILL.md)。

问题与 PR 提交至 [Paper Workflow](https://github.com/Eason412/paper-workflow/issues)，附最小复现、预期/实际结果及脱敏日志。许可证：[MIT](LICENSE)。
