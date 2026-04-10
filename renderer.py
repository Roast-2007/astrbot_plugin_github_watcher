from __future__ import annotations

from astrbot.api.message_components import Plain
from astrbot.core.message.message_event_result import MessageChain

from .models import NormalizedEvent


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
