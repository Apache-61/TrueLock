"""Per-call usage ledger.

One row per model API call, in the shape frozen by
`orchestrator/policies/usage-ledger.schema.json`. TASK-007 requires it:
"Records token usage per call against the usage ledger schema."

Written as JSON Lines under `.state/` (gitignored, never a source of
truth -- `orchestrator/state/README.md`), because an append-only log
survives a crashed run, which a rewritten JSON document does not.

Cost is recorded as reported by the provider and left `null` when the
provider does not report it. The worker never invents a cost estimate:
a made-up number in a budget ledger is worse than an honest gap.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

VALID_STATUSES = ("ok", "error", "retried", "routed")

DEFAULT_LEDGER_PATH = Path(".state/usage.jsonl")


@dataclass
class LedgerEntry:
    """One row, conforming to usage-ledger.schema.json."""

    provider: str
    project: str
    model: str
    request_id: str
    timestamp: str
    status: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    estimated_cost: float | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        if data["status"] not in VALID_STATUSES:
            data["status"] = "error"
        return data


class UsageLedger:
    """Append-only JSONL writer for `LedgerEntry` rows."""

    def __init__(self, path: Path | str = DEFAULT_LEDGER_PATH, *, dry_run: bool = False) -> None:
        self.path = Path(path)
        self.dry_run = dry_run
        self.entries: list[LedgerEntry] = []

    def record(
        self,
        *,
        provider: str,
        project: str,
        model: str,
        status: str = "ok",
        request_id: str = "",
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cached_tokens: int | None = None,
        estimated_cost: float | None = None,
        error: str | None = None,
    ) -> LedgerEntry:
        entry = LedgerEntry(
            provider=provider,
            project=project,
            model=model or "unspecified",
            request_id=request_id or str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            status=status if status in VALID_STATUSES else "error",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            estimated_cost=estimated_cost,
            error=error,
        )
        self.entries.append(entry)
        if not self.dry_run:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry.to_dict()) + "\n")
        return entry

    def total_cost(self) -> float:
        return sum(entry.estimated_cost or 0.0 for entry in self.entries)
