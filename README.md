# astrbot_plugin_github_watcher

一个面向 AstrBot 的 GitHub 仓库更新监测插件。

它可以轮询指定 GitHub 仓库的更新，把结果主动推送到白名单 QQ 群（`aiocqhttp` / OneBot v11），并对 `push` 与 `release` 调用 AstrBot 当前已配置的 LLM 生成中文摘要。

## 当前功能

### 已支持的 GitHub 事件

| 事件类型 | 说明 | 触发条件 |
|---------|------|---------|
| `push` | 代码推送通知 | 分支 HEAD SHA 发生变化时 |
| `release` | 版本发布通知 | 仓库出现新的非 draft release |
| `branch_create` | 新分支创建通知 | 分支列表中出现新分支 |
| `branch_delete` | 分支删除通知 | 分支列表中消失的分支 |
| `pr_opened` | PR 打开通知 | 出现新的 open 状态 PR |
| `pr_merged` | PR 合并通知 | PR 从 open 变为 merged |

### 已支持的能力

- **群维度订阅**：每个群可独立订阅多个仓库
- **白名单群管理**：管理员可添加/移除群的白名单资格
- **分支白名单过滤**：添加订阅时可指定只监测特定分支
- **私有仓库访问**：通过单个全局 GitHub PAT 访问私有仓库
- **本地持久化去重**：状态保存至 `state.json`，重启不丢失
- **LLM 中文摘要**：对 push 和 release 事件调用 AstrBot LLM 生成摘要，push 摘要会附带变更文件统计（文件名、增删行数）辅助 LLM 分析
- **手动测试通知**：随时发送测试消息验证推送是否正常
- **状态与错误查看**：查看插件运行状态和最近错误记录
- **事件级别开关**：可为每个仓库独立控制每种事件类型的通知开关
- **摘要级别开关**：可为每个仓库独立控制 push/release 的 LLM 摘要
- **分支过滤管理**：动态添加/移除已订阅仓库的分支过滤列表
- **PAT 健康检查**：启动时自动检查 + 手动检查命令
- **错误主动通知**：轮询/摘要失败时主动推送错误到指定告警群
- **错误分类**：将 HTTP 状态码和异常映射为结构化的中文错误提示
- **路由持久化**：aiocqhttp 路由持久化，适配实例 ID 不必字面量等于 `aiocqhttp`

### 当前消息平台

- `aiocqhttp`（OneBot v11）

## 工作方式

插件采用**轮询 GitHub API**的方式获取更新。

当前设计特点：

- `push` 按"一次分支 head 变化"聚合为一条消息
- 首次添加订阅时**不会补发历史事件**
- `release` 默认只看已发布版本，不推送 draft
- 分支 rename 在轮询模式下当前视作"删 + 建"
- `push` 与 `release` 摘要复用 AstrBot 当前会话默认模型能力
- `push` 的 LLM 摘要 prompt 会附带变更文件统计（文件名、状态、增删行数），让 LLM 基于实际代码变更生成摘要，而非仅依赖提交消息
- 主动推送会持久化当前 aiocqhttp 群会话路由，适配实例 ID 不必字面量等于 `aiocqhttp`
- 通知文本统一按单条多行消息发送，避免字段粘连
- 启动时自动对配置的 GitHub PAT 执行健康检查，验证其有效性

## 安装方式

### 1. 克隆 AstrBot 本体

```bash
git clone https://github.com/AstrBotDevs/AstrBot
```

### 2. 克隆本插件到 AstrBot 插件目录

```bash
mkdir -p AstrBot/data/plugins
cd AstrBot/data/plugins
git clone https://github.com/Roast-2007/astrbot_plugin_github_watcher
```

### 3. 安装插件依赖

进入插件目录后安装：

```bash
pip install -r requirements.txt
```

当前依赖：

- `httpx>=0.27,<1`

### 4. 配置 GitHub PAT

在 AstrBot 插件配置页面中设置 `github_pat`。

> 建议配置 PAT，即使是公开仓库。不配置 PAT 时会受到更严格的 API 速率限制。

### 5. 启动 AstrBot

用你平时的方式启动 AstrBot，然后在插件管理页面确认插件已被识别。

插件元数据来自：

- `metadata.yaml`

当前元数据：

- 插件名：`astrbot_plugin_github_watcher`
- 展示名：`GitHub Watcher`
- 版本：`v0.2.2`
- 支持平台：`aiocqhttp`
- AstrBot 版本：`>=4.16,<5`

## 配置项

插件通过 `_conf_schema.json` 暴露以下配置：

### 必填 / 强烈建议配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `github_pat` | string | `""` | GitHub Personal Access Token，用于访问私有仓库和提高 API 配额 |

### 轮询与请求

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `poll_interval_seconds` | int | `60` | 轮询 GitHub API 的间隔秒数 |
| `request_timeout_seconds` | int | `15` | 单次 GitHub API 请求超时秒数 |
| `max_retry_count` | int | `2` | 请求失败后的最大重试次数 |

### 摘要与状态

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_llm_summary_for_push` | bool | `true` | 默认是否对 push 事件启用 LLM 中文摘要 |
| `enable_llm_summary_for_release` | bool | `true` | 默认是否对 release 事件启用 LLM 中文摘要 |
| `notify_on_error` | bool | `true` | 轮询或摘要失败时是否记录错误 |
| `status_error_limit` | int | `10` | `/ghwatch errors` 和 `/ghwatch status` 最多展示多少条最近错误 |

### 错误通知

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `alert_on_error` | bool | `true` | 是否启用主动错误通知（总开关） |
| `alert_network_error` | bool | `true` | 是否将网络错误推送到告警群 |
| `alert_rate_limit` | bool | `true` | 是否将速率限制错误推送到告警群 |
| `alert_auth_failure` | bool | `true` | 是否将认证失败错误推送到告警群 |
| `alert_not_found` | bool | `true` | 是否将资源不存在错误推送到告警群 |

## GitHub PAT 权限建议

如果你要监测私有仓库，PAT 至少要能读取目标仓库内容。

建议最小化授权，只给读取所需权限。

注意：

- 不要在群聊命令里发送 PAT
- 不要把 PAT 写进源码
- PAT 应只通过 AstrBot 插件配置页面设置

## 使用方法

### 第一步：先把目标群加入白名单

在目标 QQ 群（`aiocqhttp`）里执行：

```text
/ghwatch whitelist
```

**权限要求**：AstrBot 超级管理员 或 当前群管理员

**效果**：将当前群加入插件白名单，后续才能使用订阅功能。

---

移出白名单：

```text
/ghwatch unwhitelist
```

**权限要求**：AstrBot 超级管理员 或 当前群管理员

**效果**：将当前群移出白名单，不再接收该群的推送。

> **说明**：插件当前只识别 `aiocqhttp` 群会话。加入白名单时会记录当前群会话的真实路由信息，后续主动推送会按该路由发送。若更换了适配器实例或路由信息失效，可在目标群重新执行一次 `/ghwatch whitelist`。

### 第二步：添加仓库订阅

订阅一个仓库（监测全部分支）：

```text
/ghwatch add owner/repo
```

只监测指定分支：

```text
/ghwatch add owner/repo main,dev
```

例如：

```text
/ghwatch add AstrBotDevs/AstrBot main
```

**权限要求**：AstrBot 超级管理员 或 当前群管理员

**前提**：当前群已在白名单中

**效果**：插件会验证 PAT 是否能访问该仓库，验证通过后添加订阅。首次添加不会补发历史事件。

### 第三步：查看/管理订阅

查看当前群的订阅列表：

```text
/ghwatch list
```

移除某个仓库订阅：

```text
/ghwatch remove owner/repo
```

发送一条测试通知（验证推送是否正常）：

```text
/ghwatch test owner/repo
```

### 第四步：精细控制（v0.2 新增）

#### 管理事件通知开关

为指定仓库开启/关闭特定事件类型的通知：

```text
/ghwatch event owner/repo <事件类型> <on|off>
```

**示例**：

```text
# 关闭某个仓库的 push 通知
/ghwatch event owner/repo push off

# 开启某个仓库的 release 通知
/ghwatch event owner/repo release on

# 关闭 PR 合并通知
/ghwatch event owner/repo pr_merged off
```

**支持的完整事件类型**：

| 事件类型 | 说明 |
|---------|------|
| `push` | 代码推送 |
| `release` | 版本发布 |
| `branch_create` | 分支创建 |
| `branch_delete` | 分支删除 |
| `pr_opened` | PR 打开 |
| `pr_merged` | PR 合并 |

**权限要求**：AstrBot 超级管理员 或 当前群管理员

**前提**：当前群已订阅该仓库

---

#### 管理 LLM 摘要开关

为指定仓库开启/关闭 push 或 release 的 LLM 中文摘要：

```text
/ghwatch summary-toggle owner/repo <push|release> <on|off>
```

**示例**：

```text
# 关闭某个仓库 push 的 LLM 摘要（只显示原始提交信息）
/ghwatch summary-toggle owner/repo push off

# 开启某个仓库 release 的 LLM 摘要
/ghwatch summary-toggle owner/repo release on
```

**说明**：关闭摘要后，推送消息中只会显示原始提交信息或 release 说明文本，不会调用 LLM 生成摘要。

**权限要求**：AstrBot 超级管理员 或 当前群管理员

**前提**：当前群已订阅该仓库

---

#### 管理分支过滤列表

在已订阅的仓库上动态添加/移除分支过滤：

```text
/ghwatch branch-filter owner/repo <add|remove> <分支名>
```

**示例**：

```text
# 增加监测 main 分支
/ghwatch branch-filter owner/repo add main

# 增加监测 dev 分支
/ghwatch branch-filter owner/repo add dev

# 不再监测 dev 分支
/ghwatch branch-filter owner/repo remove dev
```

**说明**：
- 如果分支过滤列表为空，则监测该仓库的全部分支
- 添加已存在的分支不会重复添加
- 移除不存在的分支不会产生效果

**权限要求**：AstrBot 超级管理员 或 当前群管理员

**前提**：当前群已订阅该仓库

---

#### 检查 PAT 健康状态

手动检查当前配置的 GitHub PAT 是否有效：

```text
/ghwatch health
```

**返回示例**：

```
GitHub PAT 状态：可用 — GitHub 认证可用。
```

或

```
GitHub PAT 状态：异常 — GitHub PAT 无效或已过期，请检查配置。
```

**说明**：插件在启动时也会自动执行一次 PAT 健康检查，如果失败会在日志中记录警告。

**权限要求**：AstrBot 超级管理员 或 当前群管理员

---

#### 管理错误通知接收群（告警群）

添加/移除接收主动错误通知的群：

```text
/ghwatch alert-group add
/ghwatch alert-group remove
```

**说明**：
- 添加后，当轮询或摘要失败时，错误信息会主动推送到该群
- 错误通知按级别过滤，可在配置项中控制哪些级别的错误需要推送
- 同一个群可以既是订阅群又是告警群

**告警群通知的错误级别**：

| 级别 | 说明 | 触发场景 |
|------|------|---------|
| `network_error` | 网络错误 | 无法连接 GitHub、请求超时、服务器 5xx |
| `rate_limit` | 速率限制 | GitHub API 返回 429 或 403 中的 rate limit |
| `auth_failure` | 认证失败 | PAT 无效(401) 或权限不足(403) |
| `not_found` | 资源不存在 | 仓库不存在(404) 或 PAT 无访问权限 |
| `unknown` | 未知错误 | 其他未分类的异常 |

**权限要求**：AstrBot 超级管理员 或 当前群管理员

### 第五步：查看状态与错误

查看插件运行状态：

```text
/ghwatch status
```

**返回示例**：

```
GitHub Watcher 状态：
- 白名单群数：2
- 已订阅仓库数：5
- 最近错误数：0
- 当前群已在白名单中
- 告警群数：1
```

查看最近错误记录：

```text
/ghwatch errors
```

**返回示例**：

```
最近错误：
2024-01-01T12:00:00 PAT 健康检查失败: GitHub PAT 无效或已过期，请检查配置。
2024-01-01T11:00:00 owner/repo 轮询失败: 无法连接到 GitHub，请检查网络连接。
```

**说明**：最多展示 `status_error_limit` 条（默认 10 条）最近错误，按时间倒序。

## 命令行为说明

- **权限控制**：所有管理类命令（whitelist/unwhitelist/add/remove/event/summary-toggle/branch-filter/health/alert-group）均要求执行者为 AstrBot 超级管理员或当前群管理员
- **白名单限制**：只有白名单中的 `aiocqhttp` 群可以正常执行订阅相关命令
- **路由绑定**：如果当前群号相同，但不是之前绑定的 aiocqhttp 会话实例，插件会提示重新执行 `/ghwatch whitelist` 以刷新路由绑定
- **命令格式**：所有命令均通过 `/ghwatch` 命令组发起，后接子命令名和参数

## 命令列表

| 命令 | 权限要求 | 说明 |
|---|---|---|
| `/ghwatch whitelist` | 管理员 | 将当前群加入白名单 |
| `/ghwatch unwhitelist` | 管理员 | 将当前群移出白名单 |
| `/ghwatch add owner/repo [branch1,branch2]` | 管理员 | 为当前群添加仓库订阅，可选指定监测分支 |
| `/ghwatch remove owner/repo` | 管理员 | 为当前群移除仓库订阅 |
| `/ghwatch list` | 无 | 查看当前群订阅列表 |
| `/ghwatch test owner/repo` | 管理员 | 向当前群发送一条测试通知 |
| `/ghwatch status` | 无 | 查看插件状态（白名单群数、订阅仓库数、错误数、告警群数） |
| `/ghwatch errors` | 无 | 查看最近错误记录 |
| `/ghwatch event owner/repo <type> <on\|off>` | 管理员 | 切换指定仓库的指定事件类型通知开关。支持类型: push, release, branch_create, branch_delete, pr_opened, pr_merged |
| `/ghwatch summary-toggle owner/repo <push\|release> <on\|off>` | 管理员 | 切换指定仓库的 push/release LLM 摘要开关 |
| `/ghwatch branch-filter owner/repo <add\|remove> <branch>` | 管理员 | 管理指定仓库的分支过滤列表（添加/移除分支） |
| `/ghwatch health` | 管理员 | 手动检查 GitHub PAT 健康状态 |
| `/ghwatch alert-group <add\|remove>` | 管理员 | 管理错误通知接收群（添加/移除告警群） |

## 消息示例

### Push

```text
[GitHub更新] owner/repo
类型：Push
分支：main
标题：main 分支有 3 条新提交
摘要：本次更新新增了用户登录接口，修改了 auth 模块的验证逻辑，
同时更新了相关测试用例。变更主要集中在 src/auth/ 目录下。
链接：https://github.com/owner/repo/compare/...
```

> **摘要增强**：push 事件的 LLM 摘要现在会附带变更文件统计信息。例如 LLM 收到的 prompt 包含：
> ```
> 变更文件（共 5 个文件）：
> src/auth/login.py (modified +42/-8)
> src/auth/verify.py (modified +15/-3)
> tests/test_auth.py (modified +20/-2)
> docs/AUTH.md (added +30/-0)
> README.md (modified +2/-1)
> ```
> 这样 LLM 能基于实际变更的文件和行数生成更准确的摘要，而非仅依赖提交消息。

### Release

```text
[GitHub更新] owner/repo
类型：Release
标题：v1.2.3
摘要：这个版本主要……
链接：https://github.com/owner/repo/releases/tag/v1.2.3
```

### 测试通知

```text
[GitHub更新] owner/repo
类型：测试通知
标题：这是一条测试通知
链接：https://github.com/owner/repo
```

### PR

```text
[GitHub更新] owner/repo
类型：PR Merged
标题：PR #123 已合并：some feature
链接：https://github.com/owner/repo/pull/123
```

### 错误通知（告警群）

```text
[GitHub Watcher 错误] owner/repo
级别：认证失败
详情：GitHub PAT 无效或已过期，请检查配置。
```

## 错误分类说明

插件对 GitHub API 返回的错误进行了结构化分类，输出可读的中文提示：

| HTTP 状态码/异常 | 错误级别 | 中文提示 |
|-----------------|---------|---------|
| 401 | auth_failure | GitHub PAT 无效或已过期，请检查配置。 |
| 403 (含 rate limit) | rate_limit | GitHub API 速率限制，请降低轮询频率或检查 PAT 配额。 |
| 403 (不含 rate limit) | auth_failure | 权限不足，请确认 PAT 拥有访问该仓库的权限。 |
| 404 | not_found | 仓库或资源不存在，请检查仓库名称或 PAT 权限。 |
| 429 | rate_limit | GitHub API 速率限制，请降低轮询频率或检查 PAT 配额。 |
| 5xx | network_error | GitHub 服务器异常 (HTTP xxx)，请稍后重试。 |
| 连接超时/失败 | network_error | 无法连接到 GitHub，请检查网络连接。 |
| 请求超时 | network_error | 连接 GitHub 超时，请检查网络或降低请求频率。 |
| 其他异常 | network_error | 网络请求异常: {具体异常信息} |

## 当前实现限制

1. 轮询模式下，分支 rename 当前按"删 + 建"处理
2. 还没有提供"按仓库不同 PAT / 多 Token 路由"
3. 还没有提供 webhook 模式
4. 摘要复用 AstrBot 当前模型，不支持插件级独立模型配置
5. 首次订阅不会补发历史事件

## 目录结构

| 文件 | 说明 |
|------|------|
| `main.py` | 插件入口、命令处理、轮询调度 |
| `github_client.py` | GitHub REST API 客户端（httpx 实现） |
| `models.py` | 数据模型（全部为 frozen dataclass） |
| `storage.py` | JSON 文件持久化（原子写入） |
| `poller.py` | 轮询编排（调用 API + 运行检测器） |
| `detectors.py` | 事件检测逻辑（push/release/branch/PR） |
| `summarizer.py` | LLM 中文摘要逻辑 |
| `renderer.py` | 消息格式化（事件通知 + 错误通知） |
| `permissions.py` | 群管理员/超级管理员权限判断 |
| `error_notifier.py` | 错误主动通知器（推送至告警群） |
| `_conf_schema.json` | 插件配置 schema |
| `metadata.yaml` | 插件元数据 |

## 开发状态

当前版本：`v0.2.2`

定位：

- 完善群维度事件/摘要/分支控制
- 增强错误分类与主动告警能力
- 启动时自动验证 PAT 有效性

## 未来路线图

### v0.2 (已完成)

- [x] 增加事件开关管理命令 (`/ghwatch event`)
- [x] 增加分支管理命令 (`/ghwatch branch-filter`)
- [x] 增加摘要开关管理命令 (`/ghwatch summary-toggle`)
- [x] 启动时做 GitHub PAT 健康检查
- [x] 更明确的错误分类与可读错误提示
- [x] 增加错误主动通知群功能 (`/ghwatch alert-group`)
- [x] 手动 PAT 健康检查命令 (`/ghwatch health`)

### v0.3

- [ ] 支持 Tag 事件
- [ ] 支持 PR 更多阶段事件（如 synchronize）
- [ ] 支持 Issue 事件
- [ ] 支持失败时降级策略配置
- [ ] 支持更丰富的消息模板

### v0.4

- [ ] 支持多 Token 路由
- [ ] 支持按仓库绑定不同认证信息
- [ ] 支持插件级独立 LLM 配置

### v0.5+

- [ ] 支持 GitHub webhook 模式
- [ ] 支持更低延迟的事件投递
- [ ] 支持历史回补
- [ ] 支持 WebUI 可视化订阅管理
- [ ] 支持更丰富的通知格式（转发消息 / 模板化）

## 致谢

- [AstrBot](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot 插件开发文档](https://docs.astrbot.app/dev/star/plugin-new.html)

## License

AGPL-3.0
