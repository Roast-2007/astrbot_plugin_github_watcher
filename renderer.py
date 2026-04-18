from __future__ import annotations

from astrbot.api.message_components import Plain
from astrbot.core.message.message_event_result import MessageChain

from .models import ErrorLevel, GitHubError, NormalizedEvent


def render_event_text(event: NormalizedEvent) -> str:
    lines = [f"[GitHub更新] {event.repo_full_name}"]

    if event.type == "push":
        lines.append("类型：Push")
        if event.branch:
            lines.append(f"分支：{event.branch}")
    elif event.type == "release":
        lines.append("类型：Release")
    elif event.type == "branch_create":
        lines.append("类型：新分支")
    elif event.type == "branch_delete":
        lines.append("类型：删除分支")
    elif event.type == "pr_opened":
        lines.append("类型：PR Opened")
    elif event.type == "pr_merged":
        lines.append("类型：PR Merged")
    elif event.type == "test":
        lines.append("类型：测试通知")

    lines.append(f"标题：{event.title}")

    summary = event.summary.strip()
    if summary:
        summary_lines = [line.rstrip() for line in summary.splitlines() if line.strip()]
        if summary_lines:
            lines.append(f"摘要：{summary_lines[0]}")
            lines.extend(summary_lines[1:])
    elif event.details:
        lines.append("详情：")
        lines.extend(f"- {detail}" for detail in event.details[:6])

    lines.append(f"链接：{event.url}")
    return "\n".join(lines)


def render_event(event: NormalizedEvent) -> MessageChain:
    return MessageChain([Plain(render_event_text(event))])


def render_error_text(repo_name: str, error: GitHubError) -> str:
    level_map: dict[ErrorLevel, str] = {
        "network_error": "网络错误",
        "rate_limit": "速率限制",
        "auth_failure": "认证失败",
        "not_found": "资源不存在",
        "unknown": "未知错误",
    }
    level_label = level_map.get(error.level, error.level)
    return (
        f"[GitHub Watcher 错误] {repo_name}\n"
        f"级别：{level_label}\n"
        f"详情：{error.message}"
    )


def render_error_message(repo_name: str, error: GitHubError) -> MessageChain:
    return MessageChain([Plain(render_error_text(repo_name, error))])
