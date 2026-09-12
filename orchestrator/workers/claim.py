"""CLAIM -> VERIFY: the protocol that stops two workers doing one task.

This is the load-bearing safety property of the whole worker
(`tasks/README.md` -> "Claim protocol", ADR-0003). The rule:

    Reading `status:ready` is not claiming. Posting a claim is not
    winning. Only re-reading the issue and finding *your* claim_id on the
    earliest live CLAIM comment is winning.

Ordering comes from GitHub's server-assigned, monotonically increasing
comment IDs -- never from the worker's own clock, which four
workstations cannot be trusted to agree on.

Relationship to `scripts/orchestration/task_cli.py`
--------------------------------------------------
That script is the manual, stdlib-only version of the same protocol, and
its comment format is the wire format. This module emits and parses
*exactly* the same shape, so a human running `task_cli.py claim` and a
worker running `worker start` compete correctly against each other.
`tests/unit/test_worker_claim.py` asserts that compatibility rather than
trusting the two regexes to stay in step.

Where it goes beyond `task_cli.find_earliest_claim`: this module honours
RELEASE. A task claimed, released, and re-opened for claiming would
otherwise be permanently owned by the stale first claim.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

CLAIM_PATTERN = re.compile(
    r"^CLAIM\s*\n"
    r"task_id:\s*(?P<task_id>\S+)\s*\n"
    r"worker_id:\s*(?P<worker_id>\S+)\s*\n"
    r"claim_id:\s*(?P<claim_id>\S+)\s*\n"
    r"timestamp:\s*(?P<timestamp>\S+)",
    re.MULTILINE,
)

RELEASE_PATTERN = re.compile(r"^RELEASE\s*\n\s*worker_id:\s*(?P<worker_id>\S+)", re.MULTILINE)

#: Posted by a worker that lost the race, so the thread reads honestly.
SUPERSEDED_PATTERN = re.compile(r"^CLAIM-WITHDRAWN\s*\n\s*claim_id:\s*(?P<claim_id>\S+)", re.MULTILINE)


class ClaimError(RuntimeError):
    """The claim protocol could not be completed safely."""


@dataclass(frozen=True)
class Claim:
    """One CLAIM comment, parsed."""

    task_id: str
    worker_id: str
    claim_id: str
    timestamp: str
    comment_id: int

    def render(self) -> str:
        return format_claim(self.task_id, self.worker_id, self.claim_id, self.timestamp)


def format_claim(task_id: str, worker_id: str, claim_id: str, timestamp: str) -> str:
    """The exact wire format shared with `scripts/orchestration/task_cli.py`."""
    return (
        f"CLAIM\n"
        f"task_id: {task_id}\n"
        f"worker_id: {worker_id}\n"
        f"claim_id: {claim_id}\n"
        f"timestamp: {timestamp}\n"
    )


def new_claim_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_claims(comments: list[dict]) -> list[Claim]:
    """Every CLAIM comment on an issue, in comment-ID order."""
    claims = []
    for comment in comments:
        match = CLAIM_PATTERN.search(comment.get("body", "") or "")
        if match:
            claims.append(
                Claim(
                    task_id=match.group("task_id"),
                    worker_id=match.group("worker_id"),
                    claim_id=match.group("claim_id"),
                    timestamp=match.group("timestamp"),
                    comment_id=int(comment["id"]),
                )
            )
    return sorted(claims, key=lambda claim: claim.comment_id)


def find_winning_claim(comments: list[dict]) -> Claim | None:
    """The claim that currently owns the task, or None if it is free.

    Live claims are those posted after the most recent RELEASE and not
    explicitly withdrawn. Among them the lowest comment ID wins, because
    GitHub assigned it first.
    """
    last_release_id = -1
    withdrawn: set[str] = set()
    for comment in comments:
        body = comment.get("body", "") or ""
        if RELEASE_PATTERN.search(body):
            last_release_id = max(last_release_id, int(comment["id"]))
        withdrawal = SUPERSEDED_PATTERN.search(body)
        if withdrawal:
            withdrawn.add(withdrawal.group("claim_id"))

    live = [
        claim
        for claim in parse_claims(comments)
        if claim.comment_id > last_release_id and claim.claim_id not in withdrawn
    ]
    return live[0] if live else None


@dataclass(frozen=True)
class ClaimOutcome:
    """The result of one CLAIM -> VERIFY round trip."""

    won: bool
    claim_id: str
    task_id: str
    issue_number: int
    winner: Claim | None = None

    @property
    def reason(self) -> str:
        if self.won:
            return f"claim {self.claim_id} is the earliest live CLAIM on issue #{self.issue_number}"
        if self.winner is None:
            return "no live claim found after posting -- treating as lost, which is the safe direction"
        return (
            f"lost to worker_id={self.winner.worker_id} "
            f"(claim_id={self.winner.claim_id}, comment_id={self.winner.comment_id})"
        )


def claim_task(client, task, worker_id: str) -> ClaimOutcome:
    """Post a claim, then re-read the issue to see whether it won.

    The re-read is not optional and is not cached: between the POST and
    the GET another worker's claim may land, and this GET is the only
    thing that can reveal it.
    """
    claim_id = new_claim_id()
    body = format_claim(task.task_id, worker_id, claim_id, utc_now())
    client.add_comment(task.issue_number, body)

    comments = client.list_comments(task.issue_number)
    winner = find_winning_claim(comments)
    won = winner is not None and winner.claim_id == claim_id
    return ClaimOutcome(
        won=won,
        claim_id=claim_id,
        task_id=task.task_id,
        issue_number=task.issue_number,
        winner=winner,
    )


def withdraw_claim(client, issue_number: int, claim_id: str, worker_id: str, reason: str) -> None:
    """Mark a losing claim as withdrawn so the issue thread stays honest.

    A worker that loses must leave no ambiguity about who owns the task
    -- two live claim comments on one issue is exactly the after-the-fact
    signal ADR-0003 relies on to detect a race.
    """
    client.add_comment(
        issue_number,
        f"CLAIM-WITHDRAWN\n"
        f"claim_id: {claim_id}\n"
        f"worker_id: {worker_id}\n"
        f"timestamp: {utc_now()}\n"
        f"reason: {reason}\n",
    )


def release_task(client, issue_number: int, worker_id: str, reason: str) -> None:
    """Hand a claimed task back to the queue."""
    client.add_comment(
        issue_number,
        f"RELEASE\n"
        f"worker_id: {worker_id}\n"
        f"timestamp: {utc_now()}\n"
        f"reason: {reason}\n",
    )
