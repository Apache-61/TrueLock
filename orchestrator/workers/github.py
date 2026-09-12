"""GitHub REST access for the worker.

Stdlib only (`urllib`), matching `scripts/orchestration/task_cli.py`, so a
fresh workstation needs nothing but Python 3 and a token before it can
coordinate (ADR-0003 -> "no new infrastructure").

Three implementations share one interface:

`GitHubClient`      real API calls.
`DryRunGitHubClient` reads through to the real API, records writes without
                    sending them. This is what `--dry-run` uses, so a dry
                    run reasons about *real* task state while being
                    incapable of mutating it.
`FakeGitHubClient`  fully in-memory, for tests and for `--dry-run` with no
                    token available.

Write methods are the only ones that mutate anything, and they all funnel
through `_write`, so "can this run change the world?" has exactly one
answer per class rather than one per call site.
"""
from __future__ import annotations

import json
import itertools
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

API_ROOT = "https://api.github.com"
USER_AGENT = "truelock-ai-worker"


class GitHubError(RuntimeError):
    """A GitHub API call failed in a way the worker cannot paper over."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass
class RecordedCall:
    """One write the worker wanted to perform."""

    method: str
    path: str
    body: dict[str, Any] | None = None

    def describe(self) -> str:
        summary = f"{self.method} {self.path}"
        if self.body:
            keys = ", ".join(sorted(self.body))
            summary = f"{summary} ({keys})"
        return summary


class GitHubClient:
    """Minimal GitHub REST client covering issues, comments, labels, PRs."""

    def __init__(self, owner: str, repo: str, token: str, *, api_root: str = API_ROOT) -> None:
        self.owner = owner
        self.repo = repo
        self._token = token
        self._api_root = api_root
        self.recorded: list[RecordedCall] = []

    # -- transport ----------------------------------------------------
    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        url = f"{self._api_root}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Authorization", f"Bearer {self._token}")
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        request.add_header("User-Agent", USER_AGENT)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise GitHubError(
                f"GitHub API {method} {path} -> {exc.code}: {detail}", status=exc.code
            ) from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network dependent
            raise GitHubError(f"GitHub API {method} {path} unreachable: {exc.reason}") from exc

    def _read(self, path: str) -> Any:
        return self._request("GET", path)

    def _write(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        self.recorded.append(RecordedCall(method, path, body))
        return self._request(method, path, body)

    # -- reads --------------------------------------------------------
    def list_issues(self, *, labels: str = "", state: str = "open", per_page: int = 100) -> list[dict]:
        query: dict[str, str] = {"state": state, "per_page": str(per_page)}
        if labels:
            query["labels"] = labels
        path = f"/repos/{self.owner}/{self.repo}/issues?{urllib.parse.urlencode(query)}"
        issues = self._read(path) or []
        # The issues endpoint also returns pull requests; the worker only
        # ever wants real issues.
        return [issue for issue in issues if "pull_request" not in issue]

    def get_issue(self, number: int) -> dict:
        return self._read(f"/repos/{self.owner}/{self.repo}/issues/{number}")

    def list_comments(self, number: int, *, per_page: int = 100) -> list[dict]:
        return (
            self._read(
                f"/repos/{self.owner}/{self.repo}/issues/{number}/comments?per_page={per_page}"
            )
            or []
        )

    def list_pull_requests(self, *, state: str = "open", head: str = "") -> list[dict]:
        query: dict[str, str] = {"state": state, "per_page": "100"}
        if head:
            query["head"] = f"{self.owner}:{head}"
        return self._read(
            f"/repos/{self.owner}/{self.repo}/pulls?{urllib.parse.urlencode(query)}"
        ) or []

    # -- writes -------------------------------------------------------
    def add_comment(self, number: int, body: str) -> dict:
        return self._write(
            "POST", f"/repos/{self.owner}/{self.repo}/issues/{number}/comments", {"body": body}
        )

    def add_labels(self, number: int, labels: list[str]) -> Any:
        return self._write(
            "POST", f"/repos/{self.owner}/{self.repo}/issues/{number}/labels", {"labels": labels}
        )

    def remove_label(self, number: int, label: str) -> Any:
        quoted = urllib.parse.quote(label, safe="")
        return self._write(
            "DELETE", f"/repos/{self.owner}/{self.repo}/issues/{number}/labels/{quoted}"
        )

    def create_pull_request(
        self, *, title: str, head: str, base: str, body: str, draft: bool = False
    ) -> dict:
        return self._write(
            "POST",
            f"/repos/{self.owner}/{self.repo}/pulls",
            {"title": title, "head": head, "base": base, "body": body, "draft": draft},
        )


class DryRunGitHubClient(GitHubClient):
    """Reads are real; writes are recorded, dropped, and locally overlaid.

    Used by `--dry-run` so the rehearsal reasons about the true state of
    the task queue while being structurally unable to claim a task,
    relabel an issue, or open a pull request.

    The overlay matters: without it, a rehearsed CLAIM is invisible to
    the VERIFY that follows, so every dry run would end at "lost the
    claim" and could never exercise the rest of the loop. Simulated
    comments are given IDs far above any real one, so a *real* competing
    claim still wins the comparison -- a dry run against a task someone
    else already holds correctly reports LOST.
    """

    #: Above any plausible real GitHub comment ID, so simulated comments
    #: always sort last and never beat a real claim.
    SIMULATED_ID_BASE = 10**15

    def __init__(self, owner: str, repo: str, token: str, *, api_root: str = API_ROOT) -> None:
        super().__init__(owner, repo, token, api_root=api_root)
        self._simulated_comments: dict[int, list[dict]] = {}

    def _write(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        self.recorded.append(RecordedCall(method, path, body))
        match = re.match(r"/repos/[^/]+/[^/]+/issues/(\d+)/comments$", path)
        if match and method == "POST" and body and "body" in body:
            issue_number = int(match.group(1))
            comment = {
                "id": self.SIMULATED_ID_BASE + len(self.recorded),
                "body": body["body"],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "simulated": True,
            }
            self._simulated_comments.setdefault(issue_number, []).append(comment)
            return comment
        return {"dry_run": True, "method": method, "path": path, "id": len(self.recorded)}

    def list_comments(self, number: int, *, per_page: int = 100) -> list[dict]:
        """Real comments plus the ones this rehearsal would have posted."""
        return super().list_comments(number, per_page=per_page) + list(
            self._simulated_comments.get(number, [])
        )


@dataclass
class FakeGitHubClient:
    """In-memory GitHub double.

    Comment IDs come from a monotonic counter, which is precisely the
    property the claim protocol depends on (ADR-0003), so tests exercise
    the real race-resolution rule rather than a simplified stand-in.
    """

    owner: str = "apache-61"
    repo: str = "truelock"
    issues: dict[int, dict] = field(default_factory=dict)
    comments: dict[int, list[dict]] = field(default_factory=dict)
    pulls: list[dict] = field(default_factory=list)
    recorded: list[RecordedCall] = field(default_factory=list)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1000))

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_issue(self, number: int, title: str, body: str, labels: list[str] | None = None,
                  state: str = "open") -> dict:
        issue = {
            "number": number,
            "title": title,
            "body": body,
            "state": state,
            "labels": [{"name": name} for name in (labels or [])],
            "html_url": f"https://github.com/{self.owner}/{self.repo}/issues/{number}",
        }
        self.issues[number] = issue
        self.comments.setdefault(number, [])
        return issue

    def list_issues(self, *, labels: str = "", state: str = "open", per_page: int = 100) -> list[dict]:
        wanted = {label for label in labels.split(",") if label}
        result = []
        for issue in self.issues.values():
            if state != "all" and issue["state"] != state:
                continue
            names = {label["name"] for label in issue.get("labels", [])}
            if wanted and not wanted.issubset(names):
                continue
            result.append(issue)
        return sorted(result, key=lambda issue: issue["number"])

    def get_issue(self, number: int) -> dict:
        if number not in self.issues:
            raise GitHubError(f"issue #{number} not found", status=404)
        return self.issues[number]

    def list_comments(self, number: int, *, per_page: int = 100) -> list[dict]:
        return list(self.comments.get(number, []))

    def list_pull_requests(self, *, state: str = "open", head: str = "") -> list[dict]:
        return [
            pull
            for pull in self.pulls
            if (state == "all" or pull.get("state") == state)
            and (not head or pull.get("head") == head)
        ]

    def add_comment(self, number: int, body: str) -> dict:
        self.recorded.append(RecordedCall("POST", f"/issues/{number}/comments", {"body": body}))
        comment = {"id": next(self._ids), "body": body, "created_at": self._now()}
        self.comments.setdefault(number, []).append(comment)
        return comment

    def add_labels(self, number: int, labels: list[str]) -> Any:
        self.recorded.append(RecordedCall("POST", f"/issues/{number}/labels", {"labels": labels}))
        issue = self.get_issue(number)
        existing = {label["name"] for label in issue.get("labels", [])}
        for label in labels:
            if label not in existing:
                issue.setdefault("labels", []).append({"name": label})
        return issue["labels"]

    def remove_label(self, number: int, label: str) -> Any:
        self.recorded.append(RecordedCall("DELETE", f"/issues/{number}/labels/{label}"))
        issue = self.get_issue(number)
        issue["labels"] = [item for item in issue.get("labels", []) if item["name"] != label]
        return issue["labels"]

    def create_pull_request(
        self, *, title: str, head: str, base: str, body: str, draft: bool = False
    ) -> dict:
        self.recorded.append(RecordedCall("POST", "/pulls", {"title": title, "head": head}))
        number = len(self.pulls) + 1
        pull = {
            "number": number,
            "title": title,
            "head": head,
            "base": base,
            "body": body,
            "draft": draft,
            "state": "open",
            "html_url": f"https://github.com/{self.owner}/{self.repo}/pull/{number}",
        }
        self.pulls.append(pull)
        return pull
