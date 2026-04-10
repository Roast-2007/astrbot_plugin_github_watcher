from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import (
    ErrorRecord,
    GroupSubscription,
    RepoEventSettings,
    RepoRef,
    RepoSubscription,
    RuntimeState,
    StoredRepoState,
)


class Storage:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._state_path = self._data_dir / "state.json"

    def load(self) -> RuntimeState:
        if not self._state_path.exists():
            return RuntimeState()
        raw = json.loads(self._state_path.read_text(encoding="utf-8"))
        groups = {
            group_id: self._parse_group(group_id, group_data)
            for group_id, group_data in raw.get("groups", {}).items()
        }
        repo_states = {
            repo_full_name: StoredRepoState(**repo_state)
            for repo_full_name, repo_state in raw.get("repo_states", {}).items()
        }
        recent_errors = tuple(raw.get("recent_errors", []))
        return RuntimeState(
            groups=groups,
            repo_states=repo_states,
            recent_errors=recent_errors,
        )

    def save(self, state: RuntimeState) -> None:
        payload = {
            "groups": {
                group_id: self._dump_group(group)
                for group_id, group in state.groups.items()
            },
            "repo_states": {
                repo_full_name: asdict(repo_state)
                for repo_full_name, repo_state in state.repo_states.items()
            },
            "recent_errors": list(state.recent_errors),
        }
        tmp_path = self._state_path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self._state_path)

    def add_error(self, state: RuntimeState, message: str, limit: int) -> RuntimeState:
        record = ErrorRecord.create(message)
        errors = (f"{record.created_at} {record.message}", *state.recent_errors)
        return RuntimeState(
            groups=state.groups,
            repo_states=state.repo_states,
            recent_errors=errors[:limit],
        )

    def _parse_group(self, group_id: str, data: dict[str, Any]) -> GroupSubscription:
        repos = tuple(self._parse_repo_subscription(item) for item in data.get("repos", []))
        return GroupSubscription(group_id=group_id, repos=repos, enabled=bool(data.get("enabled", True)))

    def _parse_repo_subscription(self, data: dict[str, Any]) -> RepoSubscription:
        repo = RepoRef(owner=data["owner"], repo=data["repo"])
        event_data = data.get("events", {})
        events = RepoEventSettings(
            push=bool(event_data.get("push", True)),
            release=bool(event_data.get("release", True)),
            branch_create=bool(event_data.get("branch_create", True)),
            branch_delete=bool(event_data.get("branch_delete", True)),
            pr_opened=bool(event_data.get("pr_opened", True)),
            pr_merged=bool(event_data.get("pr_merged", True)),
        )
        branches = tuple(str(branch) for branch in data.get("branches", []))
        return RepoSubscription(
            repo=repo,
            branches=branches,
            events=events,
            llm_push_summary=bool(data.get("llm_push_summary", True)),
            llm_release_summary=bool(data.get("llm_release_summary", True)),
            enabled=bool(data.get("enabled", True)),
        )

    def _dump_group(self, group: GroupSubscription) -> dict[str, Any]:
        return {
            "enabled": group.enabled,
            "repos": [self._dump_repo_subscription(repo) for repo in group.repos],
        }

    def _dump_repo_subscription(self, subscription: RepoSubscription) -> dict[str, Any]:
        return {
            "owner": subscription.repo.owner,
            "repo": subscription.repo.repo,
            "branches": list(subscription.branches),
            "events": {
                "push": subscription.events.push,
                "release": subscription.events.release,
                "branch_create": subscription.events.branch_create,
                "branch_delete": subscription.events.branch_delete,
                "pr_opened": subscription.events.pr_opened,
                "pr_merged": subscription.events.pr_merged,
            },
            "llm_push_summary": subscription.llm_push_summary,
            "llm_release_summary": subscription.llm_release_summary,
            "enabled": subscription.enabled,
        }
