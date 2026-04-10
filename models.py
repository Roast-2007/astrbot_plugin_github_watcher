from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


EventType = Literal[
    "push",
    "release",
    "branch_create",
    "branch_delete",
    "pr_opened",
    "pr_merged",
]


@dataclass(frozen=True)
class RepoRef:
    owner: str
    repo: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"


@dataclass(frozen=True)
class RepoEventSettings:
    push: bool = True
    release: bool = True
    branch_create: bool = True
    branch_delete: bool = True
    pr_opened: bool = True
    pr_merged: bool = True

    def enabled_types(self) -> set[EventType]:
        enabled: set[EventType] = set()
        if self.push:
            enabled.add("push")
        if self.release:
            enabled.add("release")
        if self.branch_create:
            enabled.add("branch_create")
        if self.branch_delete:
            enabled.add("branch_delete")
        if self.pr_opened:
            enabled.add("pr_opened")
        if self.pr_merged:
            enabled.add("pr_merged")
        return enabled


@dataclass(frozen=True)
class RepoSubscription:
    repo: RepoRef
    branches: tuple[str, ...] = field(default_factory=tuple)
    events: RepoEventSettings = field(default_factory=RepoEventSettings)
    llm_push_summary: bool = True
    llm_release_summary: bool = True
    enabled: bool = True


@dataclass(frozen=True)
class GroupSubscription:
    group_id: str
    repos: tuple[RepoSubscription, ...] = field(default_factory=tuple)
    enabled: bool = True


@dataclass(frozen=True)
class StoredRepoState:
    default_branch: str = ""
    known_branch_heads: dict[str, str] = field(default_factory=dict)
    last_seen_release_id: int = 0
    known_pr_states: dict[str, str] = field(default_factory=dict)
    bootstrap_completed: bool = False
    last_poll_at: str = ""
    last_error: str = ""


@dataclass(frozen=True)
class RuntimeState:
    groups: dict[str, GroupSubscription] = field(default_factory=dict)
    repo_states: dict[str, StoredRepoState] = field(default_factory=dict)
    recent_errors: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PushCommit:
    sha: str
    message: str
    author_name: str
    url: str


@dataclass(frozen=True)
class NormalizedEvent:
    type: EventType
    repo_full_name: str
    title: str
    url: str
    branch: str = ""
    summary: str = ""
    details: tuple[str, ...] = field(default_factory=tuple)
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PollOutcome:
    new_state: StoredRepoState
    events: tuple[NormalizedEvent, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class HealthCheckResult:
    ok: bool
    message: str


@dataclass(frozen=True)
class RepoAccessResult:
    ok: bool
    message: str
    default_branch: str = ""


@dataclass(frozen=True)
class ErrorRecord:
    message: str
    created_at: str

    @staticmethod
    def create(message: str) -> "ErrorRecord":
        return ErrorRecord(message=message, created_at=datetime.utcnow().isoformat())
