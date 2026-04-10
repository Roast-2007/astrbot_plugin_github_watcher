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

## GitHub PAT 权限建议

如果你要监测私有仓库，PAT 至少要能读取目标仓库内容。

建议最小化授权，只给读取所需权限。

注意：

- 不要在群聊命令里发送 PAT
- 不要把 PAT 写进源码
- PAT 应只通过 AstrBot 插件配置页面设置

## 使用方法

### 1. 先把目标群加入白名单

在目标 QQ 群里执行：

```text
/ghwatch whitelist
```

移出白名单：

```text
/ghwatch unwhitelist
```

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

### PR

```text
[GitHub更新] owner/repo
类型：PR Merged
标题：PR #123 已合并：some feature
链接：https://github.com/owner/repo/pull/123
```

## 当前实现限制

这是首版实现，目前有这些已知边界：

1. 轮询模式下，分支 rename 当前按“删 + 建”处理
2. 还没有提供“按仓库动态切换某一类事件开关”的群命令
3. 还没有提供“修改已订阅仓库的摘要开关”的群命令
4. 还没有提供“按仓库不同 PAT / 多 Token 路由”
5. 还没有提供 webhook 模式
6. 错误目前以记录和查询为主，不会主动向群推送失败告警
7. 摘要复用 AstrBot 当前模型，不支持插件级独立模型配置
8. 首次订阅不会补发历史事件

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
- `_conf_schema.json`：插件配置 schema
- `metadata.yaml`：插件元数据

## 开发状态

当前版本：`v0.1.0`

定位：

- 先完成“可用的首版闭环”
- 重点验证：白名单群订阅、私有仓库访问、轮询去重、群通知、LLM 摘要

## 未来路线图

### v0.2

- [ ] 增加事件开关管理命令
- [ ] 增加分支管理命令（追加 / 删除分支过滤）
- [ ] 增加摘要开关管理命令
- [ ] 启动时做 GitHub PAT 健康检查
- [ ] 更明确的错误分类与可读错误提示

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
- [ ] 支持主动错误告警群

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
