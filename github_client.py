from __future__ import annotations

import asyncio
from typing import Any

import httpx

from .models import ErrorLevel, GitHubError, HealthCheckResult, PushCommit, RepoAccessResult, RepoRef


class GitHubClient:
    def __init__(
        self,
        *,
        token: str,
        timeout_seconds: int,
        max_retries: int,
    ) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "astrbot-plugin-github-watcher",
        }
        if token.strip():
            headers["Authorization"] = f"Bearer {token.strip()}"
        self._client = httpx.AsyncClient(
            base_url="https://api.github.com",
            headers=headers,
            timeout=timeout_seconds,
        )
        self._max_retries = max_retries

    async def aclose(self) -> None:
        await self._client.aclose()

    async def check_health(self) -> HealthCheckResult:
        try:
            response = await self._request("GET", "/user")
            if response.status_code == 401:
                return HealthCheckResult(ok=False, message="GitHub PAT 无效或已过期，请检查配置。")
            if response.is_success:
                return HealthCheckResult(ok=True, message="GitHub 认证可用。")
            error = self.classify_error(response)
            return HealthCheckResult(ok=False, message=error.message)
        except Exception as exc:  # noqa: BLE001
            error = self.classify_error(exc)
            return HealthCheckResult(ok=False, message=error.message)

    @staticmethod
    def classify_error(response_or_exception: httpx.Response | Exception) -> GitHubError:
        if isinstance(response_or_exception, httpx.Response):
            status = response_or_exception.status_code
            if status == 401:
                return GitHubError(
                    level="auth_failure",
                    status_code=status,
                    message="GitHub PAT 无效或已过期，请检查配置。",
                )
            if status == 403:
                try:
                    body = response_or_exception.json()
                    message = body.get("message", "") if isinstance(body, dict) else ""
                except Exception:
                    message = ""
                if "rate limit" in message.lower() or "api rate limit" in message.lower():
                    return GitHubError(
                        level="rate_limit",
                        status_code=status,
                        message="GitHub API 速率限制，请降低轮询频率或检查 PAT 配额。",
                    )
                return GitHubError(
                    level="auth_failure",
                    status_code=status,
                    message="权限不足，请确认 PAT 拥有访问该仓库的权限。",
                )
            if status == 404:
                return GitHubError(
                    level="not_found",
                    status_code=status,
                    message="仓库或资源不存在，请检查仓库名称或 PAT 权限。",
                )
            if status == 429:
                return GitHubError(
                    level="rate_limit",
                    status_code=status,
                    message="GitHub API 速率限制，请降低轮询频率或检查 PAT 配额。",
                )
            if 500 <= status < 600:
                return GitHubError(
                    level="network_error",
                    status_code=status,
                    message=f"GitHub 服务器异常 (HTTP {status})，请稍后重试。",
                )
            return GitHubError(
                level="unknown",
                status_code=status,
                message=f"未知错误 (HTTP {status})。",
            )

        exc = response_or_exception
        if isinstance(exc, httpx.ConnectTimeout) or isinstance(exc, httpx.ConnectError):
            return GitHubError(
                level="network_error",
                status_code=0,
                message="无法连接到 GitHub，请检查网络连接。",
            )
        if isinstance(exc, httpx.TimeoutException):
            return GitHubError(
                level="network_error",
                status_code=0,
                message="连接 GitHub 超时，请检查网络或降低请求频率。",
            )
        return GitHubError(
            level="network_error",
            status_code=0,
            message=f"网络请求异常: {exc}",
        )

    async def validate_repo_access(self, repo: RepoRef) -> RepoAccessResult:
        response = await self._request("GET", f"/repos/{repo.full_name}")
        if response.status_code == 404:
            return RepoAccessResult(ok=False, message=f"仓库 {repo.full_name} 不存在或当前 PAT 无法访问。")
        response.raise_for_status()
        payload = response.json()
        return RepoAccessResult(
            ok=True,
            message="ok",
            default_branch=str(payload.get("default_branch") or ""),
        )

    async def get_repo(self, repo: RepoRef) -> dict[str, Any]:
        response = await self._request("GET", f"/repos/{repo.full_name}")
        response.raise_for_status()
        return response.json()

    async def get_branches(self, repo: RepoRef) -> list[dict[str, Any]]:
        response = await self._request("GET", f"/repos/{repo.full_name}/branches")
        response.raise_for_status()
        return response.json()

    async def compare_commits(self, repo: RepoRef, base_sha: str, head_sha: str) -> dict[str, Any]:
        response = await self._request(
            "GET",
            f"/repos/{repo.full_name}/compare/{base_sha}...{head_sha}",
        )
        response.raise_for_status()
        return response.json()

    async def get_latest_release(self, repo: RepoRef) -> dict[str, Any] | None:
        response = await self._request("GET", f"/repos/{repo.full_name}/releases/latest")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    async def get_pull_requests(self, repo: RepoRef, state: str) -> list[dict[str, Any]]:
        response = await self._request(
            "GET",
            f"/repos/{repo.full_name}/pulls",
            params={"state": state, "sort": "updated", "direction": "desc", "per_page": 30},
        )
        response.raise_for_status()
        return response.json()

    async def get_recent_closed_pull_requests(self, repo: RepoRef) -> list[dict[str, Any]]:
        return await self.get_pull_requests(repo, "closed")

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.request(method, path, **kwargs)
                if response.status_code in {429, 500, 502, 503, 504} and attempt < self._max_retries:
                    await asyncio.sleep(min(2 ** attempt, 5))
                    continue
                return response
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    raise
                await asyncio.sleep(min(2 ** attempt, 5))
        if last_error is not None:
            raise last_error
        raise RuntimeError("unexpected request state")

    @staticmethod
    def parse_compare_commits(payload: dict[str, Any]) -> tuple[PushCommit, ...]:
        commits: list[PushCommit] = []
        for item in payload.get("commits", []):
            commit_data = item.get("commit", {})
            author = commit_data.get("author", {})
            commits.append(
                PushCommit(
                    sha=str(item.get("sha") or "")[:7],
                    message=str(commit_data.get("message") or "").strip(),
                    author_name=str(author.get("name") or "unknown"),
                    url=str(item.get("html_url") or ""),
                ),
            )
        return tuple(commits)
