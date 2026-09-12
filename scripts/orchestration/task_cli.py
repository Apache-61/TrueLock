#!/usr/bin/env python3
"""Task claim/verify protocol over GitHub Issues.

Implements the CLAIM -> VERIFY protocol from tasks/README.md and
history/decisions/ADR-0003-task-coordination.md: GitHub Issues are the
source of truth for who owns a task, because they're visible to all four
workstations and comment IDs are assigned monotonically by GitHub's
servers, which is enough to detect (not fully prevent) a race between two
workers claiming the same task at nearly the same instant.

Stdlib only (urllib), so it runs on any workstation with just Python 3 and
a GITHUB_TOKEN - no dependency install required before the team can start
coordinating.

Usage:
    export GITHUB_TOKEN=...      # repo-scoped token
    export GITHUB_OWNER=apache-61
    export GITHUB_REPO=truelock
    export WORKER_ID=WORKER-01

    python task_cli.py list
    python task_cli.py claim --issue 42 --task-id TASK-004
    python task_cli.py verify --issue 42 --claim-id <uuid-printed-by-claim>
    python task_cli.py release --issue 42
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

CLAIM_PATTERN = re.compile(
    r"^CLAIM\s*\n"
    r"task_id:\s*(?P<task_id>\S+)\s*\n"
    r"worker_id:\s*(?P<worker_id>\S+)\s*\n"
    r"claim_id:\s*(?P<claim_id>\S+)\s*\n"
    r"timestamp:\s*(?P<timestamp>\S+)",
    re.MULTILINE,
)

API_ROOT = "https://api.github.com"


def _env(name: str, required: bool = True) -> str:
    value = os.environ.get(name)
    if required and not value:
        print(f"error: missing required environment variable {name}", file=sys.stderr)
        sys.exit(2)
    return value or ""


def _request(method: str, path: str, token: str, body: dict | None = None) -> object:
    url = f"{API_ROOT}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"error: GitHub API {method} {path} -> {exc.code}: {detail}", file=sys.stderr)
        sys.exit(1)


def find_earliest_claim(comments: list[dict]) -> dict | None:
    """Pure function, unit-testable without network access.

    Given raw GitHub issue comments (each a dict with at least 'id' and
    'body'), return the parsed fields of the earliest CLAIM comment by
    comment id (GitHub assigns these monotonically), or None if no
    comment matches the CLAIM format.
    """
    claims = []
    for comment in comments:
        match = CLAIM_PATTERN.search(comment.get("body", ""))
        if match:
            claims.append({**match.groupdict(), "comment_id": comment["id"]})
    if not claims:
        return None
    return min(claims, key=lambda c: c["comment_id"])


def cmd_list(args, token, owner, repo):
    issues = _request(
        "GET", f"/repos/{owner}/{repo}/issues?labels=status:ready&state=open", token
    )
    for issue in issues:
        print(f"#{issue['number']}\t{issue['title']}")


def cmd_claim(args, token, owner, repo):
    worker_id = _env("WORKER_ID")
    claim_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    body = (
        f"CLAIM\n"
        f"task_id: {args.task_id or 'UNKNOWN'}\n"
        f"worker_id: {worker_id}\n"
        f"claim_id: {claim_id}\n"
        f"timestamp: {timestamp}\n"
    )
    _request(
        "POST",
        f"/repos/{owner}/{repo}/issues/{args.issue}/comments",
        token,
        {"body": body},
    )
    _request(
        "POST",
        f"/repos/{owner}/{repo}/issues/{args.issue}/labels",
        token,
        {"labels": ["status:claimed"]},
    )
    print(f"CLAIM posted. claim_id={claim_id}")
    print("Now run: task_cli.py verify --issue "
          f"{args.issue} --claim-id {claim_id}")


def cmd_verify(args, token, owner, repo):
    comments = _request(
        "GET", f"/repos/{owner}/{repo}/issues/{args.issue}/comments", token
    )
    earliest = find_earliest_claim(comments)
    if earliest is None:
        print("error: no CLAIM comment found on this issue", file=sys.stderr)
        sys.exit(1)
    if earliest["claim_id"] == args.claim_id:
        _request(
            "DELETE",
            f"/repos/{owner}/{repo}/issues/{args.issue}/labels/status:ready",
            token,
        )
        print("WON: you hold this task. Proceed - move it to tasks/active/ "
              "and start your branch.")
    else:
        print(
            "LOST: another worker's CLAIM comment is earlier "
            f"(worker_id={earliest['worker_id']}, claim_id={earliest['claim_id']}). "
            "Abandon this task now and claim a different READY task."
        )
        sys.exit(3)


def cmd_release(args, token, owner, repo):
    _request(
        "DELETE",
        f"/repos/{owner}/{repo}/issues/{args.issue}/labels/status:claimed",
        token,
    )
    _request(
        "POST",
        f"/repos/{owner}/{repo}/issues/{args.issue}/comments",
        token,
        {"body": f"RELEASE\nworker_id: {_env('WORKER_ID')}\ntimestamp: {datetime.now(timezone.utc).isoformat()}\n"},
    )
    print("Released. Task is available for another worker to claim again.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="list open issues labeled status:ready")

    p_claim = sub.add_parser("claim", help="post a CLAIM comment on a task issue")
    p_claim.add_argument("--issue", type=int, required=True)
    p_claim.add_argument("--task-id", type=str, default=None)

    p_verify = sub.add_parser("verify", help="check whether your claim won the race")
    p_verify.add_argument("--issue", type=int, required=True)
    p_verify.add_argument("--claim-id", type=str, required=True)

    p_release = sub.add_parser("release", help="give up a claimed task")
    p_release.add_argument("--issue", type=int, required=True)

    args = parser.parse_args()

    token = _env("GITHUB_TOKEN")
    owner = _env("GITHUB_OWNER")
    repo = _env("GITHUB_REPO")

    {
        "list": cmd_list,
        "claim": cmd_claim,
        "verify": cmd_verify,
        "release": cmd_release,
    }[args.command](args, token, owner, repo)


if __name__ == "__main__":
    main()
