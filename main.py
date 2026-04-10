from __future__ import annotations

import asyncio
from dataclasses import replace

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Plain
from astrbot.api.star import Context, Star, StarTools, register
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.platform.message_session import MessageSession
from astrbot.core.platform.message_type import MessageType

from .github_client import GitHubClient
from .models import GroupSubscription, RepoRef, RepoSubscription, RuntimeState, StoredRepoState
from .permissions import is_group_admin_or_owner
from .poller import Poller
from .renderer import render_event
from .storage import Storage
from .summarizer import Summarizer


@register("astrbot_plugin_github_watcher", "Roast-2007", "GitHub 仓库监测插件", "0.1.0")
class GitHubWatcherPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context, config)
        self.config = config
        self._data_dir = StarTools.get_data_dir("astrbot_plugin_github_watcher")
        self._storage = Storage(self._data_dir)
        self._state = self._storage.load()
        self._client: GitHubClient | None = None
        self._poller: Poller | None = None
        self._summarizer = Summarizer(context)
        self._polling_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        self._client = GitHubClient(
            token=str(self.config.get("github_pat", "")),
            timeout_seconds=int(self.config.get("request_timeout_seconds", 15)),
            max_retries=int(self.config.get("max_retry_count", 2)),
        )
        self._poller = Poller(self._client)
        self._polling_task = asyncio.create_task(self._poll_loop())

    async def terminate(self) -> None:
        if self._polling_task is not None:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
        if self._client is not None:
            await self._client.aclose()

    @filter.command_group("ghwatch")
    def ghwatch(self) -> None:
        """GitHub 仓库监测管理"""

    @ghwatch.command("whitelist")
    async def whitelist_group(self, event: AstrMessageEvent):
        """将当前群加入白名单。"""
        if not await self._ensure_group_admin(event):
            yield event.plain_result("只有 AstrBot 超管或当前群管理员可以执行此操作。")
            return
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用此命令。")
            return
        async with self._lock:
            self._state = self._ensure_group_exists(group_id)
            self._storage.save(self._state)
        yield event.plain_result(f"已将群 {group_id} 加入白名单。")

    @ghwatch.command("unwhitelist")
    async def unwhitelist_group(self, event: AstrMessageEvent):
        """将当前群移出白名单。"""
        if not await self._ensure_group_admin(event):
            yield event.plain_result("只有 AstrBot 超管或当前群管理员可以执行此操作。")
            return
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用此命令。")
            return
        async with self._lock:
            groups = dict(self._state.groups)
            groups.pop(group_id, None)
            self._state = RuntimeState(
                groups=groups,
                repo_states=self._state.repo_states,
                recent_errors=self._state.recent_errors,
            )
            self._storage.save(self._state)
        yield event.plain_result(f"已将群 {group_id} 移出白名单。")

    @ghwatch.command("add")
    async def add_repo(
        self,
        event: AstrMessageEvent,
        repo_full_name: str = "",
        branches: str = "",
    ):
        """添加当前群的 GitHub 仓库订阅。ghwatch add owner/repo [branch1,branch2]"""
        if not await self._ensure_group_admin(event):
            yield event.plain_result("只有 AstrBot 超管或当前群管理员可以执行此操作。")
            return
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用此命令。")
            return
        if not self._is_whitelisted_group(group_id):
            yield event.plain_result("当前群不在白名单中。请先执行 /ghwatch whitelist。")
            return
        repo_ref = self._parse_repo_full_name(repo_full_name)
        if repo_ref is None:
            yield event.plain_result("仓库格式错误，请使用 owner/repo。")
            return
        if self._client is None:
            yield event.plain_result("GitHub 客户端尚未初始化。")
            return
        access = await self._client.validate_repo_access(repo_ref)
        if not access.ok:
            yield event.plain_result(access.message)
            return
        branch_list = tuple(
            branch.strip() for branch in branches.split(",") if branch.strip()
        )
        async with self._lock:
            self._state = self._upsert_repo_subscription(group_id, repo_ref, branch_list)
            self._storage.save(self._state)
        yield event.plain_result(
            f"已为群 {group_id} 添加仓库 {repo_ref.full_name} 的订阅。"
        )

    @ghwatch.command("remove")
    async def remove_repo(self, event: AstrMessageEvent, repo_full_name: str = ""):
        """移除当前群的 GitHub 仓库订阅。ghwatch remove owner/repo"""
        if not await self._ensure_group_admin(event):
            yield event.plain_result("只有 AstrBot 超管或当前群管理员可以执行此操作。")
            return
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用此命令。")
            return
        if not self._is_whitelisted_group(group_id):
            yield event.plain_result("当前群不在白名单中。")
            return
        repo_ref = self._parse_repo_full_name(repo_full_name)
        if repo_ref is None:
            yield event.plain_result("仓库格式错误，请使用 owner/repo。")
            return
        async with self._lock:
            self._state = self._remove_repo_subscription(group_id, repo_ref)
            self._storage.save(self._state)
        yield event.plain_result(f"已移除仓库 {repo_ref.full_name}。")

    @ghwatch.command("list")
    async def list_repos(self, event: AstrMessageEvent):
        """查看当前群的订阅列表。"""
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用此命令。")
            return
        if not self._is_whitelisted_group(group_id):
            yield event.plain_result("当前群不在白名单中。")
            return
        group = self._state.groups.get(group_id)
        if group is None or not group.repos:
            yield event.plain_result("当前群还没有 GitHub 订阅。")
            return
        lines = ["当前群订阅："]
        for repo in group.repos:
            branch_desc = ", ".join(repo.branches) if repo.branches else "全部分支"
            lines.append(f"- {repo.repo.full_name} [{branch_desc}]")
        yield event.plain_result("\n".join(lines))

    @ghwatch.command("test")
    async def test_push(self, event: AstrMessageEvent, repo_full_name: str = ""):
        """向当前群发送一条测试通知。"""
        if not await self._ensure_group_admin(event):
            yield event.plain_result("只有 AstrBot 超管或当前群管理员可以执行此操作。")
            return
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用此命令。")
            return
        if not self._is_whitelisted_group(group_id):
            yield event.plain_result("当前群不在白名单中。")
            return
        repo_ref = self._parse_repo_full_name(repo_full_name)
        if repo_ref is None:
            yield event.plain_result("仓库格式错误，请使用 owner/repo。")
            return
        message = MessageChain(
            [
                Plain(
                    f"[GitHub更新] {repo_ref.full_name}\n类型：测试通知\n链接：https://github.com/{repo_ref.full_name}"
                )
            ],
        )
        await event.send(message)
        yield event.plain_result("测试通知已发送。")

    @ghwatch.command("status")
    async def status(self, event: AstrMessageEvent):
        """查看插件状态。"""
        repo_count = sum(len(group.repos) for group in self._state.groups.values())
        error_count = len(self._state.recent_errors)
        group_id = event.get_group_id()
        whitelist_status = (
            "当前群已在白名单中" if group_id and self._is_whitelisted_group(group_id) else "当前群不在白名单中"
        )
        yield event.plain_result(
            "\n".join(
                [
                    "GitHub Watcher 状态：",
                    f"- 白名单群数：{len(self._state.groups)}",
                    f"- 已订阅仓库数：{repo_count}",
                    f"- 最近错误数：{error_count}",
                    f"- {whitelist_status}",
                ],
            ),
        )

    @ghwatch.command("errors")
    async def errors(self, event: AstrMessageEvent):
        """查看最近错误。"""
        if not self._state.recent_errors:
            yield event.plain_result("最近没有错误记录。")
            return
        limit = int(self.config.get("status_error_limit", 10))
        lines = ["最近错误：", *self._state.recent_errors[:limit]]
        yield event.plain_result("\n".join(lines))

    async def _poll_loop(self) -> None:
        while True:
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.exception("GitHub watcher poll loop failed: %s", exc)
                await self._record_error(f"轮询失败: {exc}")
            await asyncio.sleep(max(10, int(self.config.get("poll_interval_seconds", 60))))

    async def _poll_once(self) -> None:
        if self._poller is None:
            return
        initial_repo_states = dict(self._state.repo_states)
        updated_repo_states = dict(self._state.repo_states)
        groups = list(self._state.groups.values())
        for group in groups:
            if not group.enabled:
                continue
            for subscription in group.repos:
                if not subscription.enabled:
                    continue
                repo_key = subscription.repo.full_name
                previous_state = initial_repo_states.get(repo_key, StoredRepoState())
                try:
                    outcome = await self._poller.poll_repo(subscription, previous_state)
                except Exception as exc:  # noqa: BLE001
                    await self._record_error(f"{repo_key} 轮询失败: {exc}")
                    continue
                updated_repo_states[repo_key] = outcome.new_state
                self._state = RuntimeState(
                    groups=self._state.groups,
                    repo_states=updated_repo_states,
                    recent_errors=self._state.recent_errors,
                )
                self._storage.save(self._state)
                for normalized_event in outcome.events:
                    event_to_send = normalized_event
                    try:
                        if (
                            normalized_event.type == "push"
                            and subscription.llm_push_summary
                            and bool(self.config.get("enable_llm_summary_for_push", True))
                        ):
                            summary = await self._summarizer.summarize(normalized_event, umo=None)
                            if summary:
                                event_to_send = replace(normalized_event, summary=summary)
                        if (
                            normalized_event.type == "release"
                            and subscription.llm_release_summary
                            and bool(self.config.get("enable_llm_summary_for_release", True))
                        ):
                            summary = await self._summarizer.summarize(normalized_event, umo=None)
                            if summary:
                                event_to_send = replace(normalized_event, summary=summary)
                    except Exception as exc:  # noqa: BLE001
                        await self._record_error(f"{repo_key} 摘要失败: {exc}")
                    session = MessageSession(
                        platform_name="aiocqhttp",
                        message_type=MessageType.GROUP_MESSAGE,
                        session_id=group.group_id,
                    )
                    await self.context.send_message(session, render_event(event_to_send))

    async def _record_error(self, message: str) -> None:
        async with self._lock:
            self._state = self._storage.add_error(
                self._state,
                message,
                int(self.config.get("status_error_limit", 10)),
            )
            self._storage.save(self._state)

    async def _ensure_group_admin(self, event: AstrMessageEvent) -> bool:
        return await is_group_admin_or_owner(event)

    def _is_whitelisted_group(self, group_id: str) -> bool:
        return group_id in self._state.groups

    def _ensure_group_exists(self, group_id: str) -> RuntimeState:
        groups = dict(self._state.groups)
        if group_id not in groups:
            groups[group_id] = GroupSubscription(group_id=group_id)
        return RuntimeState(
            groups=groups,
            repo_states=self._state.repo_states,
            recent_errors=self._state.recent_errors,
        )

    def _parse_repo_full_name(self, repo_full_name: str) -> RepoRef | None:
        if repo_full_name.count("/") != 1:
            return None
        owner, repo = [part.strip() for part in repo_full_name.split("/", 1)]
        if not owner or not repo:
            return None
        return RepoRef(owner=owner, repo=repo)

    def _upsert_repo_subscription(
        self,
        group_id: str,
        repo_ref: RepoRef,
        branches: tuple[str, ...],
    ) -> RuntimeState:
        groups = dict(self._state.groups)
        group = groups.get(group_id, GroupSubscription(group_id=group_id))
        repos = [repo for repo in group.repos if repo.repo.full_name != repo_ref.full_name]
        repos.append(RepoSubscription(repo=repo_ref, branches=branches))
        groups[group_id] = GroupSubscription(
            group_id=group_id,
            repos=tuple(repos),
            enabled=True,
        )
        return RuntimeState(
            groups=groups,
            repo_states=self._state.repo_states,
            recent_errors=self._state.recent_errors,
        )

    def _remove_repo_subscription(self, group_id: str, repo_ref: RepoRef) -> RuntimeState:
        groups = dict(self._state.groups)
        group = groups.get(group_id)
        if group is None:
            return self._state
        repos = tuple(
            repo for repo in group.repos if repo.repo.full_name != repo_ref.full_name
        )
        groups[group_id] = GroupSubscription(
            group_id=group_id,
            repos=repos,
            enabled=group.enabled,
        )
        return RuntimeState(
            groups=groups,
            repo_states=self._state.repo_states,
            recent_errors=self._state.recent_errors,
        )
