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
    #: The model the CLI actually served the turn on, which is not
    #: necessarily the one requested -- the runtime can fall back. The
    #: ledger records what ran, not what was asked for.
    model: str = ""


@dataclass
class ClaudeCodeAdapter:
    """Runs one task through the Claude Code CLI."""

    name: str = "claude_code"
    binary: str = field(default_factory=lambda: os.environ.get("CLAUDE_CLI_BIN", "claude"))
    model: str = ""
    extra_args: tuple[str, ...] = ()
    last_usage: Usage = field(default_factory=Usage)
    last_duration_s: float = 0.0
    last_error: str = ""
    last_permission_denials: list[str] = field(default_factory=list)

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
        self.last_error = ""
        self.last_permission_denials = []
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
        if self.last_error:
            # The CLI reports some failures in the envelope while still
            # exiting 0. Trusting the exit code alone would turn a failed
            # run into a confident "DONE".
            raise AdapterError(
                f"the Claude Code CLI reported an error for {task_id}: "
                f"{self.last_error} -- output: {text.strip()[:400]}"
            )

        result = extract_result(text, task_id=task_id)
        if self.last_permission_denials:
            # The AI was blocked from doing something it tried to do, so
            # the task is very likely incomplete even if it says DONE.
            denials = ", ".join(self.last_permission_denials[:5])
            result.known_issues.append(
                f"The CLI denied {len(self.last_permission_denials)} permission "
                f"request(s) during this run ({denials}). The implementation may "
                "be incomplete; check the diff before trusting the status."
            )
            result.requires_human_review = True
        return result

    @staticmethod
    def _served_model(envelope: dict) -> str:
        """The model the CLI actually used, per its `modelUsage` map."""
        model_usage = envelope.get("modelUsage")
        if isinstance(model_usage, dict) and model_usage:
            # One key per model used; the busiest is the one that did the work.
            def output_tokens(item) -> int:
                _, stats = item
                return int(stats.get("outputTokens", 0)) if isinstance(stats, dict) else 0

            return str(max(model_usage.items(), key=output_tokens)[0])
        return str(envelope.get("model", "") or "")

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
                model=self._served_model(envelope),
            )

        if envelope.get("is_error"):
            self.last_error = str(
                envelope.get("api_error_status")
                or envelope.get("subtype")
                or envelope.get("terminal_reason")
                or "is_error was set in the CLI result envelope"
            )
        denials = envelope.get("permission_denials")
        if isinstance(denials, list) and denials:
            self.last_permission_denials = [
                str(denial.get("tool_name", denial)) if isinstance(denial, dict) else str(denial)
                for denial in denials
            ]

        for key in ("result", "text", "content", "response"):
            value = envelope.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return text
