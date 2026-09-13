"""Append-only observability events for live timelines and ops telemetry."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Protocol


class EventSink(Protocol):
    def persist_operational_event(self, event: dict[str, Any]) -> None: ...

    def list_operational_events(
        self, external_case_key: str, *, offset: int = 0, limit: int = 100
    ) -> list[dict[str, Any]]: ...


class ObservabilityService:
    """Dual-write event log: always memory; optionally PostgreSQL."""

    def __init__(self, sink: EventSink | None = None) -> None:
        self._events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._lock = Lock()
        self._sink = sink
        self._metrics: dict[str, Any] = {
            "detector_runs": 0,
            "investigations_started": 0,
            "routing_events": 0,
            "model_calls_ok": 0,
            "model_calls_fallback": 0,
        }

    def set_sink(self, sink: EventSink | None) -> None:
        self._sink = sink

    def emit(
        self,
        *,
        case_id: str,
        message: str,
        step_id: str | None = None,
        event_type: str = "investigation",
        attributes: dict[str, Any] | None = None,
        result_hash: str | None = None,
    ) -> dict[str, Any]:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "case_id": case_id,
            "message": message,
            "step_id": step_id,
            "event_type": event_type,
            "attributes": attributes or {},
            "result_hash": result_hash,
        }
        if result_hash:
            event["attributes"] = {**event["attributes"], "result_hash": result_hash}
        with self._lock:
            self._events[case_id].append(event)
            if event_type == "ROUTING_EVENT":
                self._metrics["routing_events"] += 1
            if event_type == "investigation_start":
                self._metrics["investigations_started"] += 1
            if event_type == "detector_run":
                self._metrics["detector_runs"] += 1
        if self._sink is not None:
            try:
                self._sink.persist_operational_event(event)
            except Exception:
                # Memory timeline must remain available even if DB write fails.
                pass
        return event

    def list_events(
        self, case_id: str, *, offset: int = 0, limit: int = 100
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 500))
        offset = max(0, offset)
        if self._sink is not None:
            try:
                persisted = self._sink.list_operational_events(
                    case_id, offset=offset, limit=limit
                )
                if persisted:
                    return persisted
            except Exception:
                pass
        with self._lock:
            return list(self._events.get(case_id, [])[offset : offset + limit])

    def clear(self, case_id: str | None = None) -> None:
        with self._lock:
            if case_id is None:
                self._events.clear()
            else:
                self._events.pop(case_id, None)

    def emit_investigation_steps(self, case_id: str, steps: list[dict[str, Any]]) -> None:
        for index, step in enumerate(steps, start=1):
            tool = step.get("tool") or step.get("tool_name") or "unknown"
            action = step.get("action") or "STEP"
            refs = step.get("result_refs") or []
            full_hash = next(
                (str(ref)[5:] for ref in refs if str(ref).startswith("HASH:")),
                None,
            )
            self.emit(
                case_id=case_id,
                step_id=str(step.get("step_id")),
                message=(
                    f"Step {index}: {action} via {tool} - "
                    f"{step.get('reason') or step.get('reason_summary') or ''}"
                ).strip(),
                event_type="investigation_step",
                result_hash=full_hash,
                attributes={"decision": step.get("decision"), "tool": tool},
            )

    def record_routing_event(self, event: dict[str, Any]) -> None:
        self.emit(
            case_id="OPS",
            message=(
                f"ROUTING_EVENT from={event.get('from')} to={event.get('to')} "
                f"reason={event.get('reason')}"
            ),
            event_type="ROUTING_EVENT",
            attributes=event,
        )

    def metrics_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._metrics)
