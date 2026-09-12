"""Claude Code CLI adapter.

Invokes the locally installed `claude` binary in non-interactive mode and
parses the structured result out of its JSON envelope.

Why the CLI rather than the API: the CLI already has file editing, test
running, and repository awareness, which is exactly the tool surface a
development worker needs. Re-implementing that against the raw API would
be new infrastructure for no gain (CONTRIBUTING.md 5 -- adding one is
a decision, not a detail).

Everything version-specific is configurable, because the CLI's flags move
between releases and a worker that hard-codes them breaks silently on
upgrade:

    CLAUDE_CLI_BIN          binary to invoke            (default: claude)
    CLAUDE_CLI_EXTRA_ARGS   shell-split extra arguments (default: none)
    WORKER_MODEL            --model value               (default: CLI default)
    WORKER_AI_TIMEOUT       seconds before giving up    (default: 3600)
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass, field

from .base import AdapterError, AIResult, extract_result

DEFAULT_TIMEOUT = 3600

#: The CLI is asked for JSON so the worker gets usage metadata alongside
#: the answer; `acceptEdits` lets it write files without a human at the
#: keyboard, which is the whole point of an autonomous worker, while
#: still stopping short of bypassing every permission check.
DEFAULT_ARGS = ("-p", "--output-format", "json", "--permission-mode", "acceptEdits")


@dataclass
class Usage:
    """Token counts for the usage ledger (`usage-ledger.schema.json`)."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    estimated_cost: float | None = None
    request_id: str = ""


@dataclass
class ClaudeCodeAdapter:
    """Runs one task through the Claude Code CLI."""

    name: str = "claude_code"
    binary: str = field(default_factory=lambda: os.environ.get("CLAUDE_CLI_BIN", "claude"))
    model: str = ""
    extra_args: tuple[str, ...] = ()
    last_usage: Usage = field(default_factory=Usage)
    last_duration_s: float = 0.0

    def __post_init__(self) -> None:
        if not self.extra_args:
            raw = os.environ.get("CLAUDE_CLI_EXTRA_ARGS", "")
            self.extra_args = tuple(shlex.split(raw)) if raw else ()

    def available(self) -> bool:
        return shutil.which(self.binary) is not None

    def build_command(self) -> list[str]:
        command = [self.binary, *DEFAULT_ARGS]
        if self.model:
            command += ["--model", self.model]
        command += list(self.extra_args)
        return command

    def execute(self, prompt: str, *, task_id: str, workdir: str, timeout: int = DEFAULT_TIMEOUT) -> AIResult:
        if not self.available():
            raise AdapterError(
                f"the Claude Code CLI ({self.binary!r}) is not on PATH. Install it "
                "and authenticate it once on this machine -- see "
                "docs/orchestration/worker-setup.md -- or run with "
                "--adapter mock to rehearse the loop without it."
            )

        command = self.build_command()
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=workdir,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AdapterError(
                f"the Claude Code CLI exceeded the {timeout}s budget for {task_id}. "
                "The branch is left as-is for inspection; nothing was merged."
            ) from exc
        finally:
            self.last_duration_s = time.monotonic() - started

        if completed.returncode != 0:
            raise AdapterError(
                f"the Claude Code CLI exited {completed.returncode} for {task_id}: "
                f"{(completed.stderr or completed.stdout or '').strip()[:600]}"
            )

        text = self._unwrap(completed.stdout)
        return extract_result(text, task_id=task_id)

    def _unwrap(self, stdout: str) -> str:
        """Pull the assistant's text out of `--output-format json`.

        Falls back to the raw stdout when the envelope is not what this
        version of the CLI produced -- the result parser is tolerant, and
        guessing wrong here should degrade rather than fail.
        """
        text = (stdout or "").strip()
        if not text:
            return text
        try:
            envelope = json.loads(text)
        except json.JSONDecodeError:
            return text
        if not isinstance(envelope, dict):
            return text

        usage = envelope.get("usage") or {}
        if isinstance(usage, dict):
            self.last_usage = Usage(
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                cached_tokens=(
                    usage.get("cache_read_input_tokens")
                    or usage.get("cached_tokens")
                ),
                estimated_cost=envelope.get("total_cost_usd"),
                request_id=str(envelope.get("session_id", "")),
            )

        for key in ("result", "text", "content", "response"):
            value = envelope.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return text
