from __future__ import annotations

from astrbot.core.message.message_event_result import MessageChain

from .models import NormalizedEvent


def render_event(event: NormalizedEvent) -> MessageChain:
    message = MessageChain()
    message.message(f"[GitHub更新] {event.repo_full_name}\n")
    if event.type == "push":
        message.message("类型：Push\n")
        if event.branch:
            message.message(f"分支：{event.branch}\n")
    elif event.type == "release":
        message.message("类型：Release\n")
    elif event.type == "branch_create":
        message.message("类型：新分支\n")
    elif event.type == "branch_delete":
        message.message("类型：删除分支\n")
    elif event.type == "pr_opened":
        message.message("类型：PR Opened\n")
    elif event.type == "pr_merged":
        message.message("类型：PR Merged\n")
    message.message(f"标题：{event.title}\n")
    if event.summary:
        message.message(f"摘要：{event.summary}\n")
    elif event.details:
        detail_text = "\n".join(f"- {detail}" for detail in event.details[:6])
        message.message(f"详情：\n{detail_text}\n")
    message.message(f"链接：{event.url}")
    return message
