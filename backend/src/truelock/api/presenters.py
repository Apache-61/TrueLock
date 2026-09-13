"""Normalize investigation payloads for API consumers and the frontend."""
from __future__ import annotations

from typing import Any

from truelock.domain.models.investigation import Lead, LeadStatus


_STEP_DECISION_FROM_DB = {
    "CONTINUE": "FOLLOW",
    "SUPPORT": "CONCLUDE",
    "REJECT": "DISCARD",
    "ESCALATE": "ESCALATE",
    "STOP": "CONCLUDE",
    "ERROR": "ESCALATE",
}

_EVIDENCE_TYPE_TO_FRONTEND = {
    "BANK_TRANSACTION": "TRANSACTION",
    "INVOICE": "INVOICE",
    "SAT_69B_RECORD": "REGULATORY_STATUS",
    "ENTITY_RELATIONSHIP": "RELATIONSHIP",
    "PAYMENT_COMPLEMENT": "DOCUMENT",
    "PAYMENT_DOCUMENT": "DOCUMENT",
    "OTHER": "DOCUMENT",
}


def present_lead(lead: Lead | dict[str, Any]) -> dict[str, Any]:
    if isinstance(lead, Lead):
        return lead.to_dict()
    return dict(lead)


def present_discarded_leads(leads: list[Lead | dict[str, Any]], *, active_lead_id: str | None = None) -> list[dict[str, str]]:
    discarded: list[dict[str, str]] = []
    for lead in leads:
        row = present_lead(lead)
        if active_lead_id and row.get("lead_id") == active_lead_id:
            continue
        status = str(row.get("status", ""))
        risk = float(row.get("risk_score") or 0)
        is_control = "CONTROL" in str(row.get("detector_id", "")).upper()
        if status == LeadStatus.DISCARDED.value or is_control or risk < 0.45:
            discarded.append(
                {
                    "lead_id": str(row.get("lead_id")),
                    "reason": str(row.get("discard_reason") or row.get("reason") or "Lead deprioritized after review."),
                }
            )
    return discarded


def present_step(step: dict[str, Any]) -> dict[str, Any]:
    result = step.get("result") if isinstance(step.get("result"), dict) else step.get("result_summary") or {}
    if not isinstance(result, dict):
        result = {}
    inputs = step.get("inputs") if isinstance(step.get("inputs"), dict) else step.get("tool_inputs") or {}
    decision = step.get("decision")
    if decision in _STEP_DECISION_FROM_DB:
        decision = _STEP_DECISION_FROM_DB[decision]
    result_refs = step.get("result_refs")
    if not result_refs:
        result_refs = result.get("result_refs") or step.get("evidence_ids") or []
    return {
        "step_id": str(step.get("step_id")),
        "lead_id": str(step.get("lead_id") or ""),
        "action": step.get("action") or "",
        "tool": step.get("tool") or step.get("tool_name") or "",
        "reason": step.get("reason") or step.get("reason_summary") or "",
        "inputs": inputs,
        "result_refs": [str(value) for value in result_refs],
        "decision": decision or "FOLLOW",
        "next_action": result.get("next_action"),
    }


def present_evidence(item: dict[str, Any]) -> dict[str, Any]:
    facts = item.get("facts") or {}
    if not isinstance(facts, dict):
        facts = {}
    raw_type = item.get("type") or item.get("evidence_type") or "DOCUMENT"
    frontend_type = _EVIDENCE_TYPE_TO_FRONTEND.get(str(raw_type), str(raw_type))
    if frontend_type not in {"TRANSACTION", "INVOICE", "REGULATORY_STATUS", "RELATIONSHIP", "DOCUMENT"}:
        frontend_type = "DOCUMENT"
    claim = (
        facts.get("claim")
        or item.get("claim")
        or _default_claim(item)
    )
    return {
        "evidence_id": str(item.get("evidence_id")),
        "type": frontend_type,
        "source_type": facts.get("source_type") or str(raw_type),
        "source_id": str(facts.get("source_id") or item.get("source_id") or item.get("record_id") or ""),
        "claim": claim,
        "strength": facts.get("strength") or item.get("role") or item.get("strength") or "CORROBORATING",
        "gathered_by_step_id": facts.get("gathered_by_step_id") or item.get("created_by") or item.get("gathered_by_step_id"),
        "record_hash": item.get("source_record_sha256") or item.get("record_hash"),
    }


def present_investigation_details(
    details: dict[str, Any],
    *,
    all_leads: list[Lead | dict[str, Any]] | None = None,
    active_lead_id: str | None = None,
) -> dict[str, Any]:
    case = dict(details.get("case") or {})
    steps = [present_step(step) for step in details.get("steps") or []]
    evidence = [present_evidence(item) for item in details.get("evidence") or []]
    if all_leads is not None:
        case["discarded_leads"] = present_discarded_leads(all_leads, active_lead_id=active_lead_id)
    elif "discarded_leads" not in case:
        case["discarded_leads"] = []
    return {
        "case": case,
        "steps": steps,
        "evidence": evidence,
        "finding": details.get("finding"),
        "thread_id": details.get("thread_id"),
    }


def present_evidence_for_qa(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize evidence for Q&A without dropping already-presented claims."""
    return [present_evidence(item) for item in evidence]


def _default_claim(item: dict[str, Any]) -> str:
    facts = item.get("facts") or {}
    if isinstance(facts, dict) and facts:
        return ", ".join(f"{key}={value}" for key, value in facts.items())
    return f"Record {item.get('source_id') or item.get('record_id') or item.get('evidence_id')}"
