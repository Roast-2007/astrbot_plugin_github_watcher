from __future__ import annotations

from .detectors import (
    build_new_state,
    detect_branch_events,
    detect_pr_events,
    detect_push_events,
    detect_release_event,
)
from .github_client import GitHubClient
from .models import PollOutcome, RepoSubscription, StoredRepoState


class Poller:
    def __init__(self, client: GitHubClient) -> None:
        self._client = client

    async def poll_repo(
        self,
        subscription: RepoSubscription,
        previous_state: StoredRepoState,
    ) -> PollOutcome:
        repo_info = await self._client.get_repo(subscription.repo)
        branches = await self._client.get_branches(subscription.repo)
        release = await self._client.get_latest_release(subscription.repo)
        open_pulls = await self._client.get_pull_requests(subscription.repo, "open")
        recent_closed_pulls = await self._client.get_recent_closed_pull_requests(subscription.repo)

        events = []
        enabled = subscription.events.enabled_types()
        if "branch_create" in enabled or "branch_delete" in enabled:
            branch_events = detect_branch_events(
                repo=subscription.repo,
                watched_branches=subscription.branches,
                old_state=previous_state,
                branches=branches,
            )
            events.extend(
                event
                for event in branch_events
                if event.type in enabled
            )
        if "push" in enabled:
            events.extend(
                await detect_push_events(
                    client=self._client,
                    repo=subscription.repo,
                    watched_branches=subscription.branches,
                    old_state=previous_state,
                    branches=branches,
                ),
            )
        if "release" in enabled:
            events.extend(
                detect_release_event(
                    repo=subscription.repo,
                    old_state=previous_state,
                    release=release,
                ),
            )
        if "pr_opened" in enabled or "pr_merged" in enabled:
            pr_events = detect_pr_events(
                repo=subscription.repo,
                old_state=previous_state,
                open_pulls=open_pulls,
                recent_closed_pulls=recent_closed_pulls,
            )
            events.extend(event for event in pr_events if event.type in enabled)

        new_state = build_new_state(
            old_state=previous_state,
            repo_info=repo_info,
            branches=branches,
            release=release,
            open_pulls=open_pulls,
            recent_closed_pulls=recent_closed_pulls,
        )
        return PollOutcome(new_state=new_state, events=tuple(events))
