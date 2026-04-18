from __future__ import annotations

from astrbot.api.message_components import Plain
from astrbot.core.message.message_event_result import MessageChain

from .models import ErrorNotificationConfig, GitHubError
from .renderer import render_error_message


class ErrorNotifier:
    def __init__(self, context) -> None:
        self._context = context
        self._last_error_key: str = ""

    async def notify(
        self,
        config: ErrorNotificationConfig,
        repo_name: str,
        error: GitHubError,
    ) -> None:
        if not config.enabled:
            return
        if error.level not in config.filter_levels:
            return
        if not config.alert_groups:
            return
        error_key = f"{repo_name}:{error.level}:{error.status_code}"
        if error_key == self._last_error_key:
            return
        self._last_error_key = error_key
        for alert_group in config.alert_groups:
            if not alert_group.unified_msg_origin:
                continue
            message = render_error_message(repo_name, error)
            await self._context.send_message(alert_group.unified_msg_origin, message)
