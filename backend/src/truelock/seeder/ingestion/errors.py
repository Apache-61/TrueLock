"""How ingestion reports what it would not accept.

The rule from `SECURITY.md` and TASK-001: **reject malformed records
rather than best-effort-guessing.** A guessed field becomes a fact three
layers later, when a case file cites it and nobody remembers it was a
guess.

Rejection is not silent either. A run reports every record it refused and
why, because "we ingested 9,900 of 10,000 rows" is a finding about the
data, and the 100 it dropped may be the interesting ones.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Rejection:
    """One record that could not be normalized, and why."""

    source: str
    #: Line number, row index, or the record's own id -- whatever lets a
    #: human find it again in the source file.
    locator: str
    reason: str

    def render(self) -> str:
        return f"{self.source}:{self.locator}: {self.reason}"


@dataclass
class IngestResult:
    """What one normalization pass produced, and what it refused."""

    records: list = field(default_factory=list)
    rejections: list[Rejection] = field(default_factory=list)

    @property
    def accepted(self) -> int:
        return len(self.records)

    @property
    def rejected(self) -> int:
        return len(self.rejections)

    @property
    def ok(self) -> bool:
        """True only if nothing was refused.

        Deliberately strict: a caller that wants to tolerate rejections
        has to look at them and say so, rather than defaulting into it.
        """
        return not self.rejections

    def render(self) -> str:
        lines = [f"{self.accepted} accepted, {self.rejected} rejected"]
        lines.extend(f"  REJECTED {rejection.render()}" for rejection in self.rejections)
        return "\n".join(lines)


class IngestError(RuntimeError):
    """The source itself could not be read — not one bad record, but all of them."""
