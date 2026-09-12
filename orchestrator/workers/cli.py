"""`worker start` — the command a teammate actually types.

    worker start --once                 claim and execute one task
    worker start --continuous           keep going until a stop condition
    worker start --dry-run              rehearse without changing anything
    worker doctor                       check this machine's setup
    worker status                       show the queue as this worker sees it

Stop conditions for `--continuous`, all of them explicit:
no READY task remains, a task ends BLOCKED, a task needs human
authorization, a critical error occurs, or a safety limit
(`--max-tasks`, `--max-runtime`) is reached.
"""
from __future__ import annotations

import argparse
import sys

from .adapters.claude_code import ClaudeCodeAdapter
from .adapters.mock import MockAdapter
from .config import ConfigError, WorkerConfig, find_repo_root, load_config
from .dependencies import check_eligibility
from .github import DryRunGitHubClient, FakeGitHubClient, GitHubClient, GitHubError
from .gitops import Git
from .runner import WorkerRunner
from .safety import RunLimits
from .validation import Validator

BANNER = "TrueLock AI development worker"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="worker", description=BANNER)
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="claim and execute READY tasks")
    mode = start.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true",
                      help="attempt exactly one task, then stop (the default)")
    mode.add_argument("--continuous", action="store_true",
                      help="keep claiming tasks until a stop condition is reached")
    start.add_argument("--max-tasks", type=int, default=0, metavar="N",
                       help="stop after N tasks (0 = no limit; --once implies 1)")
    start.add_argument("--max-runtime", type=float, default=0.0, metavar="MINUTES",
                       help="stop once this many minutes have elapsed")
    start.add_argument("--max-idle", type=float, default=0.0, metavar="MINUTES",
                       help="in --continuous, stop after this long with no eligible "
                            "task (default: wait indefinitely)")
    start.add_argument("--poll-seconds", type=float, default=None, metavar="SECONDS",
                       help="how long to wait before re-reading the queue when idle "
                            "(default: WORKER_POLL_SECONDS, 120)")
    start.add_argument("--max-failure-streak", type=int, default=None, metavar="N",
                       help="stop after N consecutive failed tasks (default 3); "
                            "0 disables the circuit breaker")
    start.add_argument("--stop-on-blocker", action="store_true",
                       help="in --continuous, stop on the first BLOCKED or PROPOSAL "
                            "outcome instead of moving to the next task")
    start.add_argument("--dry-run", action="store_true",
                       help="rehearse the full loop: no claim, no commit, no push, no PR")
    start.add_argument("--adapter", choices=("claude_code", "mock"), default=None,
                       help="AI backend to use (default: claude_code; mock never calls an API)")
    start.add_argument("--model", default=None, help="model for the adapter, if it takes one")
    start.add_argument("--worker-id", default=None, help="override WORKER_ID for this run")
    start.add_argument("--base-branch", default=None, help="branch to open PRs against")
    start.add_argument("--task", default=None, metavar="ISSUE",
                       help="attempt only this issue number, if it is eligible")
    start.add_argument("--allow-auto-merge", action="store_true",
                       help="permit auto-merge for pre-authorized simple tasks only; "
                            "architecture, contract, security and migration changes are "
                            "refused regardless")

    status = sub.add_parser("status", help="show the task queue as this worker sees it")
    status.add_argument("--worker-id", default=None)

    doctor = sub.add_parser("doctor", help="check this machine's configuration")
    doctor.add_argument("--worker-id", default=None)
    return parser


def _make_config(args, *, dry_run: bool = False) -> WorkerConfig:
    overrides: dict[str, object] = {"dry_run": dry_run}
    for key in ("worker_id", "base_branch", "adapter", "model", "poll_seconds"):
        value = getattr(args, key, None)
        if value:
            overrides[{"base_branch": "worker_base_branch",
                       "adapter": "worker_adapter",
                       "model": "worker_model",
                       "poll_seconds": "worker_poll_seconds"}.get(key, key)] = value
    return load_config(repo_root=find_repo_root(), overrides=overrides)


def _make_client(config: WorkerConfig):
    """Pick the client whose *capabilities* match the run's authority.

    A dry run gets a client that cannot write, rather than a normal
    client plus a promise not to call the write methods.
    """
    if not config.dry_run:
        return GitHubClient(config.owner, config.repo, config.requires_token())
    if config.token:
        return DryRunGitHubClient(config.owner, config.repo, config.token)
    print(
        "note: no GITHUB_TOKEN available, so this dry run uses an in-memory "
        "GitHub double seeded from tasks/ready/. Set GITHUB_TOKEN to rehearse "
        "against the real queue."
    )
    return _seeded_fake(config)


def _seeded_fake(config: WorkerConfig) -> FakeGitHubClient:
    """An offline queue built from the task mirror files."""
    client = FakeGitHubClient(owner=config.owner, repo=config.repo)
    ready = sorted((config.repo_root / "tasks" / "ready").glob("TASK-*.md"))
    for index, path in enumerate(ready, start=1):
        body = path.read_text(encoding="utf-8")
        title = body.splitlines()[0].lstrip("# ").strip()
        client.add_issue(number=index, title=title, body=body, labels=["status:ready"])
    return client


def _make_adapter(config: WorkerConfig, args):
    name = getattr(args, "adapter", None) or config.adapter
    if name == "mock" or (config.dry_run and name != "claude_code"):
        return MockAdapter()
    if config.dry_run:
        print("note: --dry-run uses the mock adapter; no paid API is called.")
        return MockAdapter()
    return ClaudeCodeAdapter(model=config.model)


def cmd_start(args) -> int:
    config = _make_config(args, dry_run=args.dry_run)
    client = _make_client(config)
    adapter = _make_adapter(config, args)

    # --once is the default: an unattended loop must be asked for.
    once = args.once or not args.continuous
    limits = RunLimits(
        max_tasks=args.max_tasks,
        max_runtime_minutes=args.max_runtime,
        once=once,
        dry_run=args.dry_run,
        max_idle_minutes=args.max_idle,
        # Polling and working through blockers are what make a run
        # "continuous"; a --once run keeps the original stop rules.
        poll_when_idle=bool(args.continuous) and not args.dry_run,
        stop_on_blocker=once or args.stop_on_blocker,
        **(
            {"max_failure_streak": args.max_failure_streak}
            if args.max_failure_streak is not None
            else {}
        ),
    )

    print(f"{BANNER}\n  worker: {config.worker_id}\n  repo:   {config.slug}")
    print(f"  mode:   {'once' if once else 'continuous'}"
          f"{'  [DRY RUN — nothing will be changed]' if config.dry_run else ''}")
    if not once:
        idle = f"{args.max_idle:g}m" if args.max_idle else "indefinitely"
        print(f"  idle:   poll every {config.poll_seconds:g}s, wait {idle}")
        print(f"  claims: taken over after {config.claim_stale_minutes:g}m of silence")
    print(f"  adapter: {getattr(adapter, 'name', '?')}")

    runner = WorkerRunner(
        config,
        client,
        adapter,
        limits=limits,
        git=Git(config.repo_root, dry_run=config.dry_run),
        validator=Validator(config.repo_root, dry_run=config.dry_run),
        allow_auto_merge=args.allow_auto_merge,
    )

    if args.task:
        runner.select_task = _single_task_selector(runner, int(args.task))  # type: ignore[method-assign]

    summary = runner.run()
    print("\n" + summary.render())
    if config.dry_run and getattr(client, "recorded", None):
        print("\nWrites that a live run would have made:")
        for call in client.recorded:
            print(f"  {call.describe()}")
    return summary.exit_code


def _single_task_selector(runner: WorkerRunner, issue_number: int):
    """Restrict a run to one issue, still subject to every eligibility gate."""
    original = runner.select_task

    def select(skip: set[int]):
        if issue_number in skip:
            return None, f"issue #{issue_number} already attempted in this run"
        task, reason = original(skip | _others(runner, issue_number))
        if task is None:
            return None, reason
        return task, ""

    return select


def _others(runner: WorkerRunner, keep: int) -> set[int]:
    tasks, _ = runner.fetch_candidates()
    return {task.issue_number for task in tasks if task.issue_number != keep}


def cmd_status(args) -> int:
    config = _make_config(args, dry_run=True)
    client = _make_client(config)
    runner = WorkerRunner(config, client, None, limits=RunLimits(dry_run=True), log=lambda *_: None)
    tasks, index = runner.fetch_candidates()
    if not tasks:
        print("No open tasks found.")
        return 0
    print(f"{'TASK':10} {'PRI':4} {'TYPE':12} {'EXEC':6} ELIGIBLE / REASON")
    for task in tasks:
        eligibility = check_eligibility(
            task,
            task_index=index,
            comments=client.list_comments(task.issue_number),
            worker_id=config.worker_id,
            claim_stale_minutes=config.claim_stale_minutes,
        )
        verdict = "yes" if eligibility.eligible else "no "
        detail = "" if eligibility.eligible else f"— {eligibility.reason}"
        print(f"{task.task_id:10} {task.priority:4} {task.task_type:12} "
              f"{task.execution_mode:6} {verdict} {detail}")
    return 0


def cmd_doctor(args) -> int:
    """Check everything a new machine needs, and say what to do about gaps."""
    problems: list[str] = []
    notes: list[str] = []

    try:
        root = find_repo_root()
        notes.append(f"repository: {root}")
    except ConfigError as error:
        print(f"FAIL  {error}")
        return 1

    try:
        config = _make_config(args, dry_run=True)
        notes.append(f"worker id:  {config.worker_id}")
        notes.append(f"repository slug: {config.slug}")
    except ConfigError as error:
        problems.append(str(error))
        config = None

    if config is not None:
        if config.token:
            try:
                probe = GitHubClient(config.owner, config.repo, config.token)
                issues = probe.list_issues(state="open")
                notes.append(f"GitHub: reachable, {len(issues)} open issue(s)")
            except GitHubError as error:
                problems.append(f"GitHub token present but the API rejected it: {error}")
        else:
            problems.append(
                "GITHUB_TOKEN is not set. Live runs need a repo-scoped token; "
                "--dry-run works without one."
            )

    adapter = ClaudeCodeAdapter()
    if adapter.available():
        notes.append(f"Claude Code CLI: found ({adapter.binary})")
    else:
        problems.append(
            f"the Claude Code CLI ({adapter.binary!r}) is not on PATH. Install it and "
            "run `claude` once to authenticate, or use --adapter mock."
        )

    git = Git(find_repo_root())
    branch = git.current_branch()
    notes.append(f"current branch: {branch}")
    if not git.is_clean():
        problems.append(
            "the working tree has uncommitted changes; the worker refuses to start "
            "a task on top of them. Commit or stash first."
        )

    for line in notes:
        print(f"ok    {line}")
    for line in problems:
        print(f"FAIL  {line}")
    if not problems:
        print("\nThis machine is ready. Try: worker start --once --dry-run")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {"start": cmd_start, "status": cmd_status, "doctor": cmd_doctor}
    try:
        return handlers[args.command](args)
    except ConfigError as error:
        print(f"\nconfiguration error: {error}", file=sys.stderr)
        return 2
    except GitHubError as error:
        print(f"\nGitHub error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:  # pragma: no cover - interactive
        print("\ninterrupted; nothing further was changed.", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
