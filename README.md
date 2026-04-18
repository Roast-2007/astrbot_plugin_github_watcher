# astrbot_plugin_github_watcher

一个面向 AstrBot 的 GitHub 仓库更新监测插件。

它可以轮询指定 GitHub 仓库的更新，把结果主动推送到白名单 QQ 群（`aiocqhttp` / OneBot v11），并对 `push` 与 `release` 调用 AstrBot 当前已配置的 LLM 生成中文摘要。

## 当前功能

### 已支持的 GitHub 事件

- `push` / commit 聚合通知
- `release` 发布通知
- 新分支创建通知
- 分支删除通知
- PR 打开通知
- PR 合并通知

### 已支持的能力

- 群维度订阅
- 白名单群管理
- 分支白名单过滤
- 私有仓库访问（通过单个全局 GitHub PAT）
- 本地持久化去重状态
- AstrBot LLM 摘要（push / release）
- 手动测试通知
- 状态与最近错误查看
- aiocqhttp 路由持久化（按当前群会话动态识别适配器实例）

### 当前消息平台

- `aiocqhttp`

## 工作方式

插件采用**轮询 GitHub API**的方式获取更新，而不是 webhook。

当前设计特点：

- `push` 按“一次分支 head 变化”聚合为一条消息
- 首次添加订阅时**不会补发历史事件**
- `release` 默认只看已发布版本，不推送 draft
- 分支 rename 在轮询模式下当前视作“删 + 建”
- `push` 与 `release` 摘要复用 AstrBot 当前会话默认模型能力
- 主动推送会持久化当前 aiocqhttp 群会话路由，适配实例 ID 不必字面量等于 `aiocqhttp`
- 通知文本统一按单条多行消息发送，避免字段粘连

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

### 4. 启动 AstrBot

用你平时的方式启动 AstrBot，然后在插件管理页面确认插件已被识别。

插件元数据来自：

- `metadata.yaml`

当前元数据：

- 插件名：`astrbot_plugin_github_watcher`
- 展示名：`GitHub Watcher`
- 支持平台：`aiocqhttp`
- AstrBot 版本：`>=4.16,<5`

## 配置项

插件通过 `_conf_schema.json` 暴露以下配置：

### 必填 / 强烈建议配置

- `github_pat`
  - GitHub PAT
  - 用于访问私有仓库
  - 也建议用于公开仓库，避免速率限制过低

### 轮询与请求

- `poll_interval_seconds`
  - 轮询间隔，默认 `60`
- `request_timeout_seconds`
  - GitHub API 超时秒数，默认 `15`
- `max_retry_count`
  - 请求失败后的最大重试次数，默认 `2`

### 摘要与状态

- `enable_llm_summary_for_push`
  - 默认是否对 push 启用摘要，默认 `true`
- `enable_llm_summary_for_release`
  - 默认是否对 release 启用摘要，默认 `true`
- `notify_on_error`
  - 当前主要用于错误记录与查看，默认 `true`
- `status_error_limit`
  - `/ghwatch errors` 最多展示多少条错误，默认 `10`

### 错误通知

- `alert_on_error`
  - 是否启用主动错误通知，默认 `true`
- `alert_network_error`
  - 是否将网络错误推送到告警群，默认 `true`
- `alert_rate_limit`
  - 是否将速率限制错误推送到告警群，默认 `true`
- `alert_auth_failure`
  - 是否将认证失败错误推送到告警群，默认 `true`
- `alert_not_found`
  - 是否将资源不存在错误推送到告警群，默认 `true`

## GitHub PAT 权限建议

如果你要监测私有仓库，PAT 至少要能读取目标仓库内容。

建议最小化授权，只给读取所需权限。

注意：

- 不要在群聊命令里发送 PAT
- 不要把 PAT 写进源码
- PAT 应只通过 AstrBot 插件配置页面设置

## 使用方法

### 1. 先把目标群加入白名单

在目标 QQ 群（`aiocqhttp`）里执行：

```text
/ghwatch whitelist
```

移出白名单：

```text
/ghwatch unwhitelist
```

> 说明：插件当前只识别 `aiocqhttp` 群会话。加入白名单时会记录当前群会话的真实路由信息，后续主动推送会按该路由发送。若更换了适配器实例或路由信息失效，可在目标群重新执行一次 `/ghwatch whitelist`。

### 2. 添加仓库订阅

订阅一个仓库：

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

### 3. 查看当前群的订阅列表

```text
/ghwatch list
```

### 4. 移除仓库订阅

```text
/ghwatch remove owner/repo
```

### 5. 发送一条测试通知

```text
/ghwatch test owner/repo
```

### 6. 查看插件状态

```text
/ghwatch status
```

### 7. 查看最近错误

```text
/ghwatch errors
```

### 8. 管理事件通知开关

```text
/ghwatch event owner/repo push on
/ghwatch event owner/repo release off
```

支持的事件类型: `push`, `release`, `branch_create`, `branch_delete`, `pr_opened`, `pr_merged`

### 9. 管理 LLM 摘要开关

```text
/ghwatch summary-toggle owner/repo push on
/ghwatch summary-toggle owner/repo release off
```

### 10. 管理分支过滤

```text
/ghwatch branch-filter owner/repo add main
/ghwatch branch-filter owner/repo remove dev
```

### 11. 检查 PAT 健康状态

```text
/ghwatch health
```

### 12. 管理错误通知接收群

```text
/ghwatch alert-group add
/ghwatch alert-group remove
```

添加后，当轮询或摘要失败时，错误信息会主动推送到该群。

## 命令行为说明

- 只有白名单中的 `aiocqhttp` 群可以正常执行订阅相关命令。
- 如果当前群号相同，但不是之前绑定的 aiocqhttp 会话实例，插件会提示重新执行 `/ghwatch whitelist` 以刷新路由绑定。

## 命令列表

| 命令 | 说明 |
|---|---|
| `/ghwatch whitelist` | 将当前群加入白名单 |
| `/ghwatch unwhitelist` | 将当前群移出白名单 |
| `/ghwatch add owner/repo [branch1,branch2]` | 为当前群添加仓库订阅 |
| `/ghwatch remove owner/repo` | 为当前群移除仓库订阅 |
| `/ghwatch list` | 查看当前群订阅列表 |
| `/ghwatch test owner/repo` | 发送测试通知 |
| `/ghwatch status` | 查看插件状态 |
| `/ghwatch errors` | 查看最近错误 |
| `/ghwatch event owner/repo <type> <on\|off>` | 切换指定仓库的事件通知开关 |
| `/ghwatch summary-toggle owner/repo <push\|release> <on\|off>` | 切换指定仓库的 LLM 摘要开关 |
| `/ghwatch branch-filter owner/repo <add\|remove> <branch>` | 管理仓库的分支过滤列表 |
| `/ghwatch health` | 检查 GitHub PAT 健康状态 |
| `/ghwatch alert-group <add\|remove>` | 管理错误通知接收群 |

## 消息示例

### Push

```text
[GitHub更新] owner/repo
类型：Push
分支：main
标题：main 分支有 3 条新提交
摘要：本次更新主要……
链接：https://github.com/owner/repo/compare/...
```

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

## 当前实现限制

这是首版实现，目前有这些已知边界：

1. 轮询模式下，分支 rename 当前按”删 + 建”处理
2. 还没有提供”按仓库不同 PAT / 多 Token 路由”
3. 还没有提供 webhook 模式
4. 摘要复用 AstrBot 当前模型，不支持插件级独立模型配置
5. 首次订阅不会补发历史事件

## 目录结构

当前插件主要文件：

- `main.py`：插件入口、命令、轮询调度
- `github_client.py`：GitHub API 客户端
- `models.py`：数据模型
- `storage.py`：本地持久化
- `poller.py`：轮询编排
- `detectors.py`：事件检测逻辑
- `summarizer.py`：LLM 摘要逻辑
- `renderer.py`：消息渲染
- `permissions.py`：权限判断
- `error_notifier.py`：错误主动通知
- `_conf_schema.json`：插件配置 schema
- `metadata.yaml`：插件元数据

## 开发状态

当前版本：`v0.2.0`

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

沿用仓库现有 License。
