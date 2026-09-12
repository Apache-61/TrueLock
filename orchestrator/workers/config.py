"""Worker identity and runtime configuration.

Resolution order for every setting: explicit CLI flag > process
environment > `.env` file at the repository root > documented default.
`.env` is never committed (`.gitignore`); `.env.example` documents every
key this module reads.

`WORKER_ID` is mandatory and has no default on purpose: the claim
protocol needs a stable identity that is *not* the GitHub account name,
because four workstations can push through the same token
(CONTRIBUTING.md 1).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

#: Matches WORKER-01 .. WORKER-99 and descriptive slugs like "laptop-ana".
WORKER_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,31}$")

DEFAULT_BASE_BRANCH = "main"

#: How long a claim may go without any further activity on its issue
#: before another worker may take the task. Generous on purpose: a single
#: task may legitimately run for `WORKER_AI_TIMEOUT` (default 1h), so this
#: is three times that. Too low and two machines do the same work; too
#: high and a crashed worker strands a critical-path task for hours.
DEFAULT_CLAIM_STALE_MINUTES = 180.0

#: How long a continuous worker waits before re-reading the queue when
#: nothing is eligible. Dependencies unlock when a human merges a PR, so
#: the wait is a poll against work that arrives on someone else's clock.
DEFAULT_POLL_SECONDS = 120.0


class ConfigError(RuntimeError):
    """Raised when the worker cannot establish a safe, complete identity."""


def parse_dotenv(text: str) -> dict[str, str]:
    """Parse the subset of `.env` syntax this project uses.

    Supports `KEY=value`, `export KEY=value`, `#` comments, blank lines,
    inline trailing comments after an unquoted value, and single/double
    quoted values. Deliberately not a full shell parser -- a worker that
    silently mis-reads a token is worse than one that refuses to start.
    """
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].strip()
        values[key] = value
    return values


def load_dotenv(repo_root: Path) -> dict[str, str]:
    env_file = repo_root / ".env"
    if not env_file.is_file():
        return {}
    return parse_dotenv(env_file.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class WorkerConfig:
    """Everything the worker needs to identify itself and reach GitHub."""

    worker_id: str
    repo_root: Path
    owner: str
    repo: str
    token: str = ""
    base_branch: str = DEFAULT_BASE_BRANCH
    adapter: str = "claude_code"
    model: str = ""
    dry_run: bool = False
    labels_available: bool = True
    claim_stale_minutes: float = DEFAULT_CLAIM_STALE_MINUTES
    poll_seconds: float = DEFAULT_POLL_SECONDS
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}"

    def requires_token(self) -> str:
        if not self.token:
            raise ConfigError(
                "GITHUB_TOKEN is required for live runs. Set it in the "
                "environment or .env (see .env.example), or pass --dry-run "
                "to exercise the loop without touching GitHub."
            )
        return self.token


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from `start` until a directory containing `.git` is found."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    raise ConfigError(
        f"not inside a git repository (searched upwards from {current}). "
        "Run the worker from a clone of the TrueLock repository."
    )


def validate_worker_id(worker_id: str) -> str:
    worker_id = (worker_id or "").strip()
    if not worker_id:
        raise ConfigError(
            "WORKER_ID is not set. Every machine sets its own stable worker "
            "identity once (CONTRIBUTING.md 1):\n\n"
            '    export WORKER_ID="WORKER-01"\n\n'
            "Do not reuse another workstation's ID -- the claim protocol "
            "uses it to attribute task ownership."
        )
    if not WORKER_ID_PATTERN.match(worker_id):
        raise ConfigError(
            f"WORKER_ID {worker_id!r} is not a valid identity. Use "
            "WORKER-01..WORKER-04 or a descriptive slug: 3-32 characters, "
            "starting with a letter, containing only letters, digits, '-' "
            "and '_'."
        )
    return worker_id


def _positive_float(raw: str, default: float, name: str) -> float:
    """A misconfigured interval must fail loudly, not silently disable a guard."""
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as error:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from error
    if value < 0:
        raise ConfigError(f"{name} must not be negative, got {value}")
    return value


def load_config(
    *,
    repo_root: Path | None = None,
    environ: dict[str, str] | None = None,
    overrides: dict[str, object] | None = None,
) -> WorkerConfig:
    """Build a `WorkerConfig`, raising `ConfigError` with actionable text."""
    overrides = overrides or {}
    root = repo_root or find_repo_root()
    env: dict[str, str] = {}
    env.update(load_dotenv(root))
    env.update(environ if environ is not None else dict(os.environ))

    def pick(name: str, default: str = "") -> str:
        override = overrides.get(name.lower())
        if override not in (None, ""):
            return str(override)
        return env.get(name, default)

    worker_id = validate_worker_id(pick("WORKER_ID"))
    owner = pick("GITHUB_OWNER")
    repo = pick("GITHUB_REPO")
    if not owner or not repo:
        raise ConfigError(
            "GITHUB_OWNER and GITHUB_REPO must be set (see .env.example). "
            "They identify the repository whose Issues are the source of "
            "truth for task claims (ADR-0003)."
        )

    return WorkerConfig(
        worker_id=worker_id,
        repo_root=root,
        owner=owner,
        repo=repo,
        token=pick("GITHUB_TOKEN"),
        base_branch=pick("WORKER_BASE_BRANCH", DEFAULT_BASE_BRANCH),
        adapter=pick("WORKER_ADAPTER", "claude_code"),
        model=pick("WORKER_MODEL"),
        dry_run=bool(overrides.get("dry_run", False)),
        labels_available=pick("WORKER_LABELS_AVAILABLE", "1") not in ("0", "false", "no"),
        claim_stale_minutes=_positive_float(
            pick("WORKER_CLAIM_STALE_MINUTES"), DEFAULT_CLAIM_STALE_MINUTES,
            "WORKER_CLAIM_STALE_MINUTES",
        ),
        poll_seconds=_positive_float(
            pick("WORKER_POLL_SECONDS"), DEFAULT_POLL_SECONDS, "WORKER_POLL_SECONDS"
        ),
        extra=env,
    )
