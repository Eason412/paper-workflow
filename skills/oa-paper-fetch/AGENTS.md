# OA Paper Fetch 维护规则

本文件仅适用于 `skills/oa-paper-fetch/`。下载工作流以 [SKILL.md](SKILL.md) 为准，项目共同规则由根目录维护；本文件保留容易被代码修改破坏的产品契约。

## 源码与测试导航

| 范围 | 实现 | 相关测试 |
| --- | --- | --- |
| CLI、身份解析、OA 与机构编排 | [oa_fetch.py](oa_fetch.py) | [CLI](tests/test_cli_contract.py)、[标题解析](tests/test_title_resolution.py)、[OA 优先](tests/test_oa_first.py) |
| 浏览器会话与出版商边界 | [institutional_fetch.py](institutional_fetch.py) | [机构边界](tests/test_institutional_boundaries.py)、[URL 安全](tests/test_oa_url_safety.py) |
| 清单与稳定身份 | [manifest.py](manifest.py) | [清单](tests/test_manifest.py) |
| 偏好与依赖 | [config.py](config.py)、[requirements.txt](requirements.txt) | [配置](tests/test_config.py) |
| 文件、状态与恢复 | [store.py](store.py) | [恢复](tests/test_store_resume.py)、[命名](tests/test_filename_metadata.py)、[回归](tests/test_recovery_regressions.py) |
| Codex 入口与文档 | [SKILL.md](SKILL.md)、[agents/openai.yaml](agents/openai.yaml) | [入口契约](tests/test_skill_contract.py) |

OA 层保持标准库实现，Playwright 仅用于可选机构访问。命令、配置、状态、依赖或安装方式变化时，同时更新本目录的中英文 README；代理执行行为变化同步 `SKILL.md`。

## 身份与获取契约

- 保留来源标题、DOI 和 URL；DOI/URL 用于硬去重，纯标题相同仅标记可能重复。最终输入 ID 与独立标题身份不得碰撞。
- 标题确认需要至少两个独立来源支持同一个 DOI。阈值以源码常量为准；arXiv DOI 别名不得掩盖出版商 DOI 冲突。
- 身份歧义、无法解析、出版商标题不匹配或不可核验时，保留状态和证据，不得由机构回退绕过。
- OA 先于机构访问；机构范围仅限 IEEE Xplore、Wiley Online Library、Elsevier ScienceDirect。修改允许范围需要明确的产品授权和边界测试。
- 保留 OA SSRF、端口和逐跳重定向检查，机构同出版商 PDF 检查、80 MiB 上限，以及下载与续传一致的轻量 PDF 校验。

## 登录与批次

浏览器可在本机持久化登录会话，但 Skill 不得读取、导出或同步 `~/.oa-paper-fetch/profile`。用户在可见浏览器中完成机构登录；不自动填写密码、SSO/MFA，不绕过验证码、付费或访问控制，不使用 Sci-Hub。

会话有效性由本次访问判断，保留缺失/过期登录的 pending 状态。机构访问保持串行、基础间隔至少 4 秒、jitter 0–10 秒、单轮最多 30 次；累计三次阻断后停止，不自动追加批次。

Skill 自动触发不扩大依赖安装、偏好保存、访问范围或登录权限。

## 存储与 CLI

- 保留稳定身份、8 位文件名后缀和 240 字节 UTF-8 限制；PDF、配置、清单、状态和报告采用原子写入。
- 命名迁移先校验旧 PDF，再创建无覆盖硬链接、保存状态，最后移除旧名称；保存失败保留原文件。损坏状态拒绝加载并返回 `4`，不静默重置。
- 保持四种论文选择器互斥，`--manifest-out` 必须与 `--batch` 配合；无输入模式限于帮助、版本、登录和独立偏好保存。
- 常规结果 JSON 写入 stdout，进度写入 stderr。保留 `candidate/downloaded/exists/duplicate/failed/pending` 区别。
- dry-run 可查询候选并写清单/结果报告，不写 PDF、恢复状态或 pending 清单，不进入机构获取。
- 保留退出码：`0` 成功/可用预检，`1` 失败或 pending，`2` 参数/配置错误，`3` 输入不可用，`4` 传输/持久化失败。

## 验证

本目录的离线检查：

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile oa_fetch.py institutional_fetch.py config.py manifest.py store.py
python3 oa_fetch.py --help
python3 oa_fetch.py --version
git diff --check
```

测试仅使用临时目录与模拟响应；真实 OA、机构登录和出版商下载分别取得授权并记录结果。已有 `pdfs/`、下载目录及浏览器会话不属于测试夹具，不检查或清理无关用户产物。
