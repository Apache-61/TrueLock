"""Formatter -> lint -> type check -> unit -> integration.

The contract this module exists to enforce: **a failing task never
produces a PR that looks like a passing one.** If a gate fails, the run
is recorded as FAILED, the failure text is carried into the handoff, the
history entry, and the PR body, and the PR (if one is opened at all) is a
draft marked as failing.

A missing tool is reported as `skipped`, never as `passed`. "We didn't
check" and "we checked and it was fine" are different claims, and
collapsing them is how a green PR ends up meaning nothing. `ok` counts
only gates that actually ran and passed, and `summary()` always says how
many were skipped.

Gate selection follows `docs/testing.md`: unit and contract always run;
integration, e2e, and scenario tests run when those directories contain
tests.
"""
from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_TIMEOUT = 1800


@dataclass
class GateResult:
    """One validation step."""

    name: str
    status: str  # "passed" | "failed" | "skipped"
    command: str = ""
    output: str = ""
    duration_s: float = 0.0
    required: bool = True

    @property
    def failed(self) -> bool:
        return self.status == "failed"

    def render(self) -> str:
        icon = {"passed": "PASS", "failed": "FAIL", "skipped": "SKIP"}[self.status]
        line = f"[{icon}] {self.name}"
        if self.command:
            line += f"  `{self.command}`"
        return line


@dataclass
class ValidationReport:
    """The whole pipeline's verdict."""

    gates: list[GateResult] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    skipped: int = 0

    @property
    def ok(self) -> bool:
        """True only if no required gate failed."""
        return not any(gate.failed and gate.required for gate in self.gates)

    @property
    def verified(self) -> bool:
        """True only if something actually ran and passed.

        A run where every gate was skipped -- no pytest on the machine, no
        tests in the tree -- is `ok` (nothing failed) but not `verified`
        (nothing was checked). The distinction decides whether a PR looks
        review-ready: an unverified change is a draft, because presenting
        "we ran nothing" as "it passes" is the exact failure this pipeline
        exists to prevent.
        """
        return self.ok and self.passed > 0

    def add(self, gate: GateResult) -> GateResult:
        self.gates.append(gate)
        if gate.status == "passed":
            self.passed += 1
        elif gate.status == "failed":
            self.failed += 1
        else:
            self.skipped += 1
        return gate

    def failures(self) -> list[GateResult]:
        return [gate for gate in self.gates if gate.failed]

    def summary(self) -> str:
        if not self.ok:
            verdict = "FAILED"
        elif not self.verified:
            verdict = "NOT VERIFIED (nothing ran)"
        else:
            verdict = "PASSED"
        return (
            f"{verdict} -- {self.passed} gate(s) passed, {self.failed} failed, "
            f"{self.skipped} skipped"
        )

    def render(self) -> str:
        lines = [self.summary(), ""]
        lines.extend(gate.render() for gate in self.gates)
        for gate in self.failures():
            lines.append("")
            lines.append(f"--- {gate.name} output ---")
            lines.append(gate.output.strip()[-4000:])
        return "\n".join(lines)

    def pytest_counts(self) -> tuple[int, int, int]:
        """Best-effort passed/failed/skipped totals parsed from pytest output."""
        import re

        passed = failed = skipped = 0
        for gate in self.gates:
            if "pytest" not in gate.command:
                continue
            for count, label in re.findall(r"(\d+) (passed|failed|skipped|error)", gate.output):
                value = int(count)
                if label == "passed":
                    passed += value
                elif label in ("failed", "error"):
                    failed += value
                elif label == "skipped":
                    skipped += value
        return passed, failed, skipped


def _has_tests(directory: Path) -> bool:
    return directory.is_dir() and any(directory.rglob("test_*.py"))


class Validator:
    """Runs the validation pipeline in one repository checkout."""

    def __init__(self, repo_root: Path, *, timeout: int = DEFAULT_TIMEOUT, dry_run: bool = False) -> None:
        self.repo_root = Path(repo_root)
        self.timeout = timeout
        self.dry_run = dry_run

    def _run(self, name: str, command: list[str], *, required: bool = True,
             skip_reason: str = "") -> GateResult:
        if skip_reason:
            return GateResult(name, "skipped", " ".join(command), skip_reason, required=required)
        if shutil.which(command[0]) is None:
            return GateResult(
                name,
                "skipped",
                " ".join(command),
                f"{command[0]!r} is not installed on this worker -- gate not run, "
                "which is NOT the same as passing",
                required=required,
            )
        if self.dry_run:
            return GateResult(name, "skipped", " ".join(command), "dry run", required=required)

        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            output = f"{completed.stdout}\n{completed.stderr}".strip()
            status = "passed" if completed.returncode == 0 else "failed"
        except subprocess.TimeoutExpired:
            output = f"timed out after {self.timeout}s"
            status = "failed"
        return GateResult(
            name,
            status,
            " ".join(command),
            output,
            duration_s=time.monotonic() - started,
            required=required,
        )

    def run(self, *, changed_paths: list[str] | None = None) -> ValidationReport:
        report = ValidationReport()
        python_changed = [p for p in (changed_paths or []) if p.endswith(".py")]
        targets = python_changed or ["."]

        # 1. Formatter -- advisory. A formatting difference is a nit, not a
        #    reason to withhold a correct implementation from review.
        if (self.repo_root / "pyproject.toml").is_file() or shutil.which("ruff"):
            report.add(self._run("formatter (ruff format --check)",
                                 ["ruff", "format", "--check", *targets], required=False))
        else:
            report.add(self._run("formatter (black --check)",
                                 ["black", "--check", *targets], required=False))

        # 2. Lint -- advisory for the same reason, and because this
        #    repository has no ruff configuration yet, so its defaults
        #    would speak for rules the team never agreed to.
        report.add(self._run("lint (ruff check)", ["ruff", "check", *targets], required=False))

        # 3. Type check -- advisory until the project adopts a mypy config.
        report.add(
            self._run(
                "type check (mypy)",
                ["mypy", "--ignore-missing-imports", *targets],
                required=False,
            )
        )

        # 4. Unit + contract tests -- required. These are the gates
        #    docs/testing.md calls the baseline, and CI runs them too.
        report.add(self._run("unit tests (pytest tests/unit)",
                             ["pytest", "-q", "tests/unit"],
                             skip_reason="" if _has_tests(self.repo_root / "tests/unit")
                             else "no tests under tests/unit"))
        report.add(self._run("contract tests (pytest tests/contract)",
                             ["pytest", "-q", "tests/contract"],
                             skip_reason="" if _has_tests(self.repo_root / "tests/contract")
                             else "no tests under tests/contract"))

        # 5. Integration and above -- required when they exist.
        for label, relative in (
            ("integration tests", "tests/integration"),
            ("end-to-end tests", "tests/e2e"),
            ("scenario tests", "tests/scenarios"),
        ):
            directory = self.repo_root / relative
            report.add(
                self._run(
                    f"{label} (pytest {relative})",
                    ["pytest", "-q", relative],
                    skip_reason="" if _has_tests(directory) else f"no tests under {relative}",
                )
            )
        return report
