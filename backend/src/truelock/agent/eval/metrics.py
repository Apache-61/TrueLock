"""Per-run evaluation metrics for the forensic investigator (Fase 6)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RunMetrics:
    corpus_id: str
    split: str
    policy_version: str
    model: str
    eval_seed: str
    valid_args_rate: float
    repeated_tool_calls: int
    source_coverage: float
    terminal_decision: str
    terminal_ok: bool
    case_status: str
    exposure_ok: bool | None
    invented_sources: int
    step_count: int
    qa_refs_ok: bool | None = None
    gates_passed: bool = False
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def score_investigation(
    *,
    corpus: dict[str, Any],
    split: str,
    case: dict[str, Any],
    steps: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    known_source_ids: set[str],
    policy_version: str,
    model: str,
    eval_seed: str,
    thresholds: dict[str, Any],
    qa_payload: dict[str, Any] | None = None,
) -> RunMetrics:
    """Score one investigation against a corpus pack and promotion thresholds."""
    failures: list[str] = []
    gates = thresholds.get("gates", thresholds)

    tool_steps = [s for s in steps if s.get("tool") not in {"step_budget_guard", "time_budget_guard"}]
    # Args validity: steps that ran have inputs; escalate-from-invalid counted separately
    invalid = sum(1 for s in steps if "invalid" in str(s.get("reason", "")).lower() and s.get("decision") == "ESCALATE")
    valid_args_rate = 1.0 if not steps else max(0.0, 1.0 - (invalid / len(steps)))

    call_keys: list[str] = []
    repeated = 0
    seen: set[str] = set()
    for step in tool_steps:
        key = f"{step.get('tool')}|{sorted((step.get('inputs') or {}).items())}"
        if key in seen:
            repeated += 1
        seen.add(key)
        call_keys.append(key)

    expected_trail = list(corpus.get("expected_trail") or [])
    evidence_sources = {str(e.get("source_id")) for e in evidence if e.get("source_id")}
    result_refs = {
        str(ref)
        for step in steps
        for ref in (step.get("result_refs") or [])
    }
    touched = evidence_sources | result_refs
    if expected_trail:
        hits = sum(1 for tx in expected_trail if any(tx in item for item in touched))
        source_coverage = hits / len(expected_trail)
    else:
        source_coverage = 1.0

    invented = sorted(sid for sid in evidence_sources if sid and sid not in known_source_ids and not sid.startswith("ENT-"))
    # Allow entity IDs and RFCs that appear in pack notes; filter TX-/PMT-/UUID-like
    invented_tx = [sid for sid in invented if sid.startswith("TX-") or sid.startswith("PMT-") or "-" in sid and len(sid) > 20]

    terminal = str(steps[-1].get("decision") if steps else "ESCALATE")
    expected_terminal = str(corpus.get("expected_terminal_decision", ""))
    terminal_ok = (not expected_terminal) or terminal == expected_terminal

    case_status = str(case.get("status", ""))
    expected_status = corpus.get("expected_case_status")
    if expected_status and case_status != expected_status:
        failures.append(f"case_status {case_status} != {expected_status}")

    exposure_ok: bool | None = None
    expected_amount = corpus.get("expected_amount_involved")
    if expected_amount is not None:
        actual = float(case.get("amount_involved") or 0.0)
        exposure_ok = abs(actual - float(expected_amount)) < 0.01
        if gates.get("require_exposure_match") and not exposure_ok:
            failures.append(f"exposure {actual} != {expected_amount}")

    qa_refs_ok: bool | None = None
    if qa_payload is not None:
        questions = corpus.get("audit_questions") or []
        must_ref = any(q.get("must_include_evidence_refs") for q in questions)
        refs = qa_payload.get("evidence_refs") or []
        if must_ref:
            qa_refs_ok = bool(refs)
            if gates.get("require_qa_evidence_refs_when_requested") and not qa_refs_ok:
                failures.append("Q&A missing evidence_refs")
        else:
            qa_refs_ok = True

    if gates.get("require_no_invented_sources") and invented_tx:
        failures.append(f"invented_sources={invented_tx}")
    if gates.get("max_repeated_tool_calls", 0) < repeated:
        failures.append(f"repeated_tool_calls={repeated}")
    if valid_args_rate < float(gates.get("min_valid_args_rate", 1.0)):
        failures.append(f"valid_args_rate={valid_args_rate}")
    if source_coverage < float(gates.get("min_source_coverage", 0.0)) and expected_trail:
        failures.append(f"source_coverage={source_coverage:.2f}")
    if gates.get("require_terminal_match") and expected_terminal and not terminal_ok:
        failures.append(f"terminal {terminal} != {expected_terminal}")
    if int(gates.get("max_steps", 10)) < len(steps):
        failures.append(f"step_count={len(steps)}")

    lead = corpus.get("input_lead") or {}
    detector = str(lead.get("detector_id", ""))
    if gates.get("forbid_substantiated_on_control") and "CONTROL" in detector:
        if case_status == "SUBSTANTIATED":
            failures.append("control pack substantiated")
    if gates.get("forbid_substantiated_on_efos_only") and detector == "69B_CORRELATION":
        if case_status == "SUBSTANTIATED":
            failures.append("efos-only pack substantiated")

    metrics = RunMetrics(
        corpus_id=str(corpus.get("corpus_id", "unknown")),
        split=split,
        policy_version=policy_version,
        model=model,
        eval_seed=eval_seed,
        valid_args_rate=valid_args_rate,
        repeated_tool_calls=repeated,
        source_coverage=source_coverage,
        terminal_decision=terminal,
        terminal_ok=terminal_ok,
        case_status=case_status,
        exposure_ok=exposure_ok,
        invented_sources=len(invented_tx),
        step_count=len(steps),
        qa_refs_ok=qa_refs_ok,
        failures=failures,
    )
    metrics.gates_passed = not failures
    return metrics
