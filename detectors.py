from __future__ import annotations

from datetime import datetime
from typing import Iterable

from .github_client import GitHubClient
from .models import NormalizedEvent, PollOutcome, RepoRef, StoredRepoState


def branch_matches(branch_name: str, watched_branches: tuple[str, ...]) -> bool:
    return not watched_branches or branch_name in watched_branches


def detect_branch_events(
    *,
    repo: RepoRef,
    watched_branches: tuple[str, ...],
    old_state: StoredRepoState,
    branches: list[dict],
) -> tuple[NormalizedEvent, ...]:
    old_heads = old_state.known_branch_heads
    new_heads = {
        str(branch.get("name") or ""): str(((branch.get("commit") or {}).get("sha")) or "")
        for branch in branches
    }
    events: list[NormalizedEvent] = []
    for branch_name in sorted(new_heads):
        if not branch_matches(branch_name, watched_branches):
            continue
        if branch_name not in old_heads and old_state.bootstrap_completed:
            events.append(
                NormalizedEvent(
                    type="branch_create",
                    repo_full_name=repo.full_name,
                    title=f"新分支 {branch_name}",
                    url=f"https://github.com/{repo.full_name}/tree/{branch_name}",
                    branch=branch_name,
                ),
            )
    for branch_name in sorted(old_heads):
        if not branch_matches(branch_name, watched_branches):
            continue
        if branch_name not in new_heads and old_state.bootstrap_completed:
            events.append(
                NormalizedEvent(
                    type="branch_delete",
                    repo_full_name=repo.full_name,
                    title=f"删除分支 {branch_name}",
                    url=f"https://github.com/{repo.full_name}",
                    branch=branch_name,
                ),
            )
    return tuple(events)


async def detect_push_events(
    *,
    client: GitHubClient,
    repo: RepoRef,
    watched_branches: tuple[str, ...],
    old_state: StoredRepoState,
    branches: list[dict],
) -> tuple[NormalizedEvent, ...]:
    if not old_state.bootstrap_completed:
        return tuple()
    old_heads = old_state.known_branch_heads
    events: list[NormalizedEvent] = []
    for branch in branches:
        branch_name = str(branch.get("name") or "")
        if not branch_matches(branch_name, watched_branches):
            continue
        head_sha = str(((branch.get("commit") or {}).get("sha")) or "")
        old_sha = old_heads.get(branch_name, "")
        if not old_sha or not head_sha or old_sha == head_sha:
            continue
        compare = await client.compare_commits(repo, old_sha, head_sha)
        commits = GitHubClient.parse_compare_commits(compare)
        if not commits:
            continue
        details = tuple(
            f"{commit.sha} {commit.author_name}: {commit.message.splitlines()[0]}"
            for commit in commits
            if commit.message
        )
        events.append(
            NormalizedEvent(
                type="push",
                repo_full_name=repo.full_name,
                title=f"{branch_name} 分支有 {len(commits)} 条新提交",
                url=str(compare.get("html_url") or f"https://github.com/{repo.full_name}"),
                branch=branch_name,
                details=details,
                payload={
                    "compare_url": str(compare.get("html_url") or ""),
                    "commit_count": len(commits),
                    "commits": [
                        {
                            "sha": commit.sha,
                            "author_name": commit.author_name,
                            "message": commit.message,
                            "url": commit.url,
                        }
                        for commit in commits
                    ],
                },
            ),
        )
    return tuple(events)


def detect_release_event(
    *,
    repo: RepoRef,
    old_state: StoredRepoState,
    release: dict | None,
) -> tuple[NormalizedEvent, ...]:
    if not release:
        return tuple()
    release_id = int(release.get("id") or 0)
    if release_id <= 0 or release.get("draft"):
        return tuple()
    if not old_state.bootstrap_completed:
        return tuple()
    if release_id == old_state.last_seen_release_id:
        return tuple()
    title = str(release.get("name") or release.get("tag_name") or "新版本发布")
    details = tuple(
        line.strip()
        for line in str(release.get("body") or "").splitlines()
        if line.strip()
    )[:8]
    return (
        NormalizedEvent(
            type="release",
            repo_full_name=repo.full_name,
            title=title,
            url=str(release.get("html_url") or f"https://github.com/{repo.full_name}/releases"),
            details=details,
            payload={
                "tag_name": str(release.get("tag_name") or ""),
                "body": str(release.get("body") or ""),
                "published_at": str(release.get("published_at") or ""),
            },
        ),
    )


def detect_pr_events(
    *,
    repo: RepoRef,
    old_state: StoredRepoState,
    open_pulls: Iterable[dict],
    recent_closed_pulls: Iterable[dict],
) -> tuple[NormalizedEvent, ...]:
    if not old_state.bootstrap_completed:
        return tuple()
    known_states = old_state.known_pr_states
    events: list[NormalizedEvent] = []
    for pr in open_pulls:
        pr_number = str(pr.get("number") or "")
        if not pr_number:
            continue
        if pr_number not in known_states:
            events.append(
                NormalizedEvent(
                    type="pr_opened",
                    repo_full_name=repo.full_name,
                    title=f"PR #{pr_number} 已打开：{str(pr.get('title') or '')}",
                    url=str(pr.get("html_url") or f"https://github.com/{repo.full_name}/pull/{pr_number}"),
                    payload={
                        "number": pr_number,
                        "author": str((pr.get("user") or {}).get("login") or "unknown"),
                    },
                ),
            )
    for pr in recent_closed_pulls:
        pr_number = str(pr.get("number") or "")
        if not pr_number:
            continue
        if known_states.get(pr_number) != "merged" and pr.get("merged_at"):
            events.append(
                NormalizedEvent(
                    type="pr_merged",
                    repo_full_name=repo.full_name,
                    title=f"PR #{pr_number} 已合并：{str(pr.get('title') or '')}",
                    url=str(pr.get("html_url") or f"https://github.com/{repo.full_name}/pull/{pr_number}"),
                    payload={
                        "number": pr_number,
                        "author": str((pr.get("user") or {}).get("login") or "unknown"),
                    },
                ),
            )
    return tuple(events)


def build_new_state(
    *,
    old_state: StoredRepoState,
    repo_info: dict,
    branches: list[dict],
    release: dict | None,
    open_pulls: list[dict],
    recent_closed_pulls: list[dict],
    error_message: str = "",
) -> StoredRepoState:
    known_branch_heads = {
        str(branch.get("name") or ""): str(((branch.get("commit") or {}).get("sha")) or "")
        for branch in branches
    }
    known_pr_states = {
        str(pr.get("number") or ""): (
            "merged" if pr.get("merged_at") else str(pr.get("state") or "open")
        )
        for pr in [*open_pulls, *recent_closed_pulls]
        if pr.get("number") is not None
    }
    release_id = int((release or {}).get("id") or 0)
    return StoredRepoState(
        default_branch=str(repo_info.get("default_branch") or old_state.default_branch),
        known_branch_heads=known_branch_heads,
        last_seen_release_id=release_id or old_state.last_seen_release_id,
        known_pr_states=known_pr_states,
        bootstrap_completed=True,
        last_poll_at=datetime.utcnow().isoformat(),
        last_error=error_message,
    )
