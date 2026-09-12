"""Git operations, with `main` treated as untouchable.

CONTRIBUTING.md 3: "Never commit directly to `main`." That is enforced
here rather than trusted, because an autonomous worker gets no second
chance to notice it was on the wrong branch.

Only the small set of git verbs the protocol needs is exposed. Anything
destructive to work that is not this run's (`push --force`, deleting
branches, `reset --hard` onto someone else's ref, `clean -x`) is absent
by construction -- see `safety.py` for the command-level refusal that
also covers what the AI adapter might try to run.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

PROTECTED_BRANCHES = frozenset({"main", "master", "develop", "release"})

#: Failures worth retrying: the network blinked, the far end was busy.
#: Anything else -- no such remote, rejected push, bad credentials -- will
#: fail identically on the fifth attempt, so retrying only delays the
#: report by half a minute and hides the real cause.
TRANSIENT_PUSH_SIGNS = (
    "could not resolve host",
    "connection timed out",
    "connection reset",
    "connection refused",
    "operation timed out",
    "temporary failure",
    "rpc failed",
    "early eof",
    "unexpected disconnect",
    "the remote end hung up",
    "ssl_error",
    "tls",
    "http 5",
    "502",
    "503",
    "504",
    "remote error: internal",
)


def is_transient(stderr: str) -> bool:
    """Is this push failure worth a retry?"""
    text = (stderr or "").lower()
    return any(sign in text for sign in TRANSIENT_PUSH_SIGNS)


class GitError(RuntimeError):
    """A git command failed, or was refused for safety."""


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class Git:
    """Thin wrapper over `git` for one working tree."""

    def __init__(self, repo_root: Path, *, dry_run: bool = False) -> None:
        self.repo_root = Path(repo_root)
        self.dry_run = dry_run
        self.recorded: list[list[str]] = []

    # -- plumbing -----------------------------------------------------
    def run(self, *args: str, check: bool = True, mutating: bool = False) -> CommandResult:
        command = ["git", *args]
        if mutating:
            self.recorded.append(command)
            if self.dry_run:
                return CommandResult(0, f"[dry-run] {' '.join(command)}", "")
        completed = subprocess.run(
            command,
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        result = CommandResult(completed.returncode, completed.stdout.strip(), completed.stderr.strip())
        if check and not result.ok:
            raise GitError(f"`{' '.join(command)}` failed ({result.returncode}): {result.stderr}")
        return result

    #: Directory names that are the worker's own mess: its runtime state,
    #: and the caches its validation gates create by running pytest, ruff
    #: and mypy. They must never reach a pull request and must never be
    #: mistaken for a dirty working tree.
    #:
    #: `.gitignore` covers all of these in the TrueLock repository. The
    #: worker does not rely on that: behaviour that depends on the host
    #: repo's ignore rules breaks silently wherever those rules differ,
    #: and the failure mode is someone's review filling up with `.pyc`
    #: files. Matched on any path segment, since `__pycache__` appears at
    #: every level of a tree, not just the root.
    SCRATCH_NAMES = frozenset({
        ".state",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    })

    @classmethod
    def is_scratch(cls, path: str) -> bool:
        """Is this path the worker's own artifact rather than task output?"""
        return any(
            segment in cls.SCRATCH_NAMES
            for segment in str(path).replace("\\", "/").split("/")
        )

    # -- reads --------------------------------------------------------
    def current_branch(self) -> str:
        return self.run("rev-parse", "--abbrev-ref", "HEAD").stdout

    def head_sha(self) -> str:
        return self.run("rev-parse", "HEAD").stdout

    def is_clean(self) -> bool:
        """Is the tree clean, ignoring the worker's own scratch?

        `.state/` is gitignored in this repository, so it never shows up
        here — but the worker must not depend on a host repo's ignore
        rules to decide whether it may start a task. It excludes its own
        runtime state on exactly the same terms it refuses to commit it
        (`SCRATCH_NAMES`); everything else still counts as dirty.
        """
        for line in self.run("status", "--porcelain", "-uall").stdout.splitlines():
            entry = line[3:].strip().strip('"') if len(line) > 3 else ""
            if not entry:
                continue
            if not self.is_scratch(entry):
                return False
        return True

    def branch_exists(self, name: str) -> bool:
        return self.run("rev-parse", "--verify", "--quiet", f"refs/heads/{name}", check=False).ok

    def changed_files(self, *, since: str = "") -> list[str]:
        """Every path this run touched: staged, unstaged, and untracked.

        `since` additionally includes files changed by commits made after
        that ref, so scope is checked against the whole run, not just the
        working tree at one instant.
        """
        paths: list[str] = []
        # `-uall` is essential, not cosmetic: plain `--porcelain` collapses a
        # wholly-untracked directory into a single `dir/` entry, which no
        # file glob matches, so the scope guard would be judging a
        # directory name instead of the files actually written.
        for line in self.run("status", "--porcelain", "-uall").stdout.splitlines():
            entry = line[3:].strip() if len(line) > 3 else ""
            if not entry:
                continue
            # Renames are reported as "old -> new"; both sides count.
            if " -> " in entry:
                old, _, new = entry.partition(" -> ")
                paths.extend([old.strip().strip('"'), new.strip().strip('"')])
            else:
                paths.append(entry.strip('"'))
        if since:
            diff = self.run("diff", "--name-only", f"{since}..HEAD", check=False)
            if diff.ok:
                paths.extend(line.strip() for line in diff.stdout.splitlines() if line.strip())
        seen: dict[str, None] = {}
        for path in paths:
            if path:
                seen.setdefault(path, None)
        return list(seen)

    # -- writes -------------------------------------------------------
    def create_branch(self, name: str, *, base: str) -> str:
        """Create and check out an isolated branch for one task.

        Refuses to produce a branch name that collides with a protected
        branch, and refuses to start from a dirty tree -- uncommitted
        work from a previous run would silently ride along into this
        task's PR.
        """
        if name in PROTECTED_BRANCHES:
            raise GitError(f"refusing to use protected branch name {name!r}")
        if not self.dry_run and not self.is_clean():
            raise GitError(
                "working tree is dirty; refusing to start a task on top of "
                "uncommitted changes. Commit, stash, or clean them first."
            )
        self.run("fetch", "origin", base, check=False, mutating=False)
        start_point = f"origin/{base}" if self.run(
            "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{base}", check=False
        ).ok else base
        if self.branch_exists(name):
            self.run("checkout", name, mutating=True)
        else:
            self.run("checkout", "-b", name, start_point, mutating=True)
        return name

    def assert_not_protected(self) -> None:
        """Hard stop if the worker is about to write to a protected branch."""
        if self.dry_run:
            return
        branch = self.current_branch()
        if branch in PROTECTED_BRANCHES:
            raise GitError(
                f"refusing to commit on protected branch {branch!r} "
                "(CONTRIBUTING.md 3: never commit directly to main)"
            )

    def commit_all(self, message: str, *, paths: list[str] | None = None) -> str | None:
        """Stage and commit. Returns the new SHA, or None if nothing changed."""
        self.assert_not_protected()
        if paths:
            self.run("add", "--", *paths, mutating=True)
        else:
            self.run("add", "-A", mutating=True)
        # Unstage the worker's own artifacts by exact path, so nested
        # `__pycache__` directories are caught as well as top-level ones.
        staged = self.run("diff", "--cached", "--name-only", check=False)
        scratch = [
            path for path in staged.stdout.splitlines() if path and self.is_scratch(path)
        ]
        if scratch:
            self.run("reset", "-q", "--", *scratch, check=False, mutating=True)
        if self.dry_run:
            return None
        if not self.run("diff", "--cached", "--quiet", check=False).ok:
            self.run("commit", "-m", message, mutating=True)
            return self.head_sha()
        return None

    def push(self, branch: str, *, remote: str = "origin", retries: int = 4) -> CommandResult:
        """Push, retrying only failures that retrying can actually fix.

        Never `--force`: this worker may share a branch with a human who
        pushed a fix, and overwriting that is exactly the kind of
        destruction it is not authorized to perform.
        """
        import time

        self.assert_not_protected()
        if branch in PROTECTED_BRANCHES:
            raise GitError(f"refusing to push to protected branch {branch!r}")
        if self.dry_run:
            self.recorded.append(["git", "push", "-u", remote, branch])
            return CommandResult(0, f"[dry-run] would push {branch}", "")

        delay = 2
        last = CommandResult(1, "", "not attempted")
        for attempt in range(retries + 1):
            last = self.run("push", "-u", remote, branch, check=False, mutating=True)
            if last.ok:
                return last
            if not is_transient(last.stderr):
                raise GitError(
                    f"push of {branch!r} failed and retrying cannot help: {last.stderr}"
                )
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
        raise GitError(f"push of {branch!r} failed after {retries + 1} attempts: {last.stderr}")
