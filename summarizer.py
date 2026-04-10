from __future__ import annotations

from astrbot.core.agent.message import Message, TextPart
from astrbot.core.star import Context

from .models import NormalizedEvent


class Summarizer:
    def __init__(self, context: Context) -> None:
        self._context = context

    async def summarize(self, event: NormalizedEvent, *, umo: str | None) -> str:
        provider = self._context.get_using_provider(umo)
        if provider is None:
            return ""
        provider_id = provider.meta().id
        prompt = self._build_prompt(event)
        if not prompt:
            return ""
        response = await self._context.llm_generate(
            chat_provider_id=provider_id,
            contexts=[Message(role="user", content=[TextPart(text=prompt)])],
            temperature=0.2,
        )
        return (response.completion_text or "").strip()

    def _build_prompt(self, event: NormalizedEvent) -> str:
        if event.type == "push":
            detail_text = "\n".join(event.details[:12])
            return (
                "请用简洁中文总结这次 GitHub push，限制在 2 到 4 句，不要编造细节。\n"
                f"仓库：{event.repo_full_name}\n"
                f"分支：{event.branch}\n"
                f"提交列表：\n{detail_text}"
            )
        if event.type == "release":
            body = str(event.payload.get("body") or "")[:4000]
            tag_name = str(event.payload.get("tag_name") or "")
            return (
                "请用简洁中文总结这次 GitHub Release，限制在 2 到 4 句，不要编造细节。\n"
                f"仓库：{event.repo_full_name}\n"
                f"标题：{event.title}\n"
                f"Tag：{tag_name}\n"
                f"Release Notes：\n{body}"
            )
        return ""
