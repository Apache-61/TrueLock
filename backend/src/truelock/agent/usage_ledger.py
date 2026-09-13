"""Session usage ledger for provider budget enforcement."""
from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class UsageEntry:
    provider: str
    project: str
    model: str
    request_id: str
    timestamp: str
    status: str
    estimated_cost: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class UsageLedger:
    """Thread-safe in-process ledger; optionally mirrored to a JSONL file."""

    def __init__(self, path: Path | None = None) -> None:
        self._entries: list[UsageEntry] = []
        self._lock = threading.Lock()
        self._path = path

    def record(self, entry: UsageEntry) -> UsageEntry:
        with self._lock:
            self._entries.append(entry)
            if self._path is not None:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        return entry

    def total_spend_usd(self) -> float:
        with self._lock:
            return round(
                sum(float(item.estimated_cost or 0.0) for item in self._entries),
                6,
            )

    def spend_by_project(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        with self._lock:
            for item in self._entries:
                totals[item.project] = totals.get(item.project, 0.0) + float(
                    item.estimated_cost or 0.0
                )
        return {key: round(value, 6) for key, value in totals.items()}

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            entries = [item.to_dict() for item in self._entries]
        return {
            "total_spend_usd": self.total_spend_usd(),
            "by_project": self.spend_by_project(),
            "entry_count": len(entries),
            "entries": entries[-50:],
        }

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


def new_request_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
