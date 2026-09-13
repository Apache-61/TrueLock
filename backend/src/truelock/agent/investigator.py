"""Forensic investigator runner: coordinates bounded loop between Gemini and tools."""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from truelock.agent.gemini_client import GeminiClient
from truelock.agent.policy import POLICY_VERSION, load_policy
from truelock.agent.tools import TOOL_DEFINITIONS, ToolRegistry, validate_tool_args
from truelock.domain.models.investigation import (
    Case,
    Evidence,
    EvidenceStrength,
    EvidenceType,
    Finding,
    InvestigationStep,
    Lead,
    Outcome,
    StepDecision,
)
from truelock.evidence.exposure import EvidenceCollector, ExposureCalculator
from truelock.settings import settings

_TX_ID_RE = re.compile(r"TX-[A-Z0-9-]+")


@dataclass
class PlannedAction:
    """Deterministic or model-selected tool invocation before validation."""

    tool_name: str
    tool_args: dict[str, Any]
    reason: str
    source: str = "deterministic"  # deterministic | gemini | fallback


@dataclass
class TurnRecord:
    """Per-turn audit payload retained across the investigation loop."""

    step_id: str
    tool_name: str
    normalized_args: dict[str, Any]
    result_hash: str
    source_ids: list[str]
    new_source_ids: list[str]
    result_summary: dict[str, Any]
    hypothesis_after: str
    decision: StepDecision
    audit_note: str | None = None


@dataclass
class InvestigationContext:
    """Resolved investigation state used to assemble evidence and the final case.

    Never carries detector risk_score into case construction.
    """

    account_id: str
    seen_source_ids: set[str] = field(default_factory=set)
    seen_call_keys: set[str] = field(default_factory=set)
    seen_result_hashes: set[str] = field(default_factory=set)
    turn_records: list[TurnRecord] = field(default_factory=list)
    transaction_ids: list[str] = field(default_factory=list)
    downstream_amounts: list[float] = field(default_factory=list)
    counterparty_rfcs: list[str] = field(default_factory=list)
    root_transaction_id: str | None = None
    returned_transaction_id: str | None = None
    root_amount: float | None = None
    returned_amount: float | None = None
    supported_exposure: float | None = None
    net_exposure: float | None = None
    providers_involved: list[str] = field(default_factory=list)
    payment_id: str | None = None
    invoice_uuid: str | None = None
    hypothesis: str = ""
    escalate_reason: str | None = None
    empty_trace: bool = False
    finding: Finding | None = None
    audit_notes: list[str] = field(default_factory=list)


# Backward-compatible alias for internal callers/tests.
_InvestigationContext = InvestigationContext


class ForensicInvestigator:
    """Bounded, auditable investigator running Gemini function calling over deterministic tools."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        gemini_client: GeminiClient | None = None,
        max_steps: int | None = None,
        max_seconds: float | None = None,
    ) -> None:
        self.tools = tool_registry
        self.gemini = gemini_client or GeminiClient()
        self.max_steps = max_steps or settings.max_investigation_steps
        self.max_seconds = (
            max_seconds
            if max_seconds is not None
            else settings.max_investigation_seconds
        )
        self.policy = load_policy(POLICY_VERSION)

    def investigate(self, lead: Lead) -> tuple[Case, list[InvestigationStep], list[Evidence]]:
        """Run an evidence-backed investigation for a given lead.

        State machine phases per turn:
        select → validate → execute → reduce → decide (or terminal transition).
        Gemini and the deterministic fallback share the same validate/execute path.
        """
        steps: list[InvestigationStep] = []
        collector = EvidenceCollector()
        ctx = InvestigationContext(
            account_id=self._resolve_account_id(lead),
            hypothesis=lead.reason,
            root_transaction_id=self._infer_root_tx_from_lead(lead),
        )
        started_at = time.monotonic()
        system_instruction = self.policy.system_instruction()
        model_label = (
            getattr(self.gemini, "model", None)
            or ("offline-fallback" if not self.gemini.is_configured else "gemini")
        )
        run_meta = self.policy.run_metadata(
            model=str(model_label),
            seed=None,
        )

        concluded = False
        step_count = 0

        while step_count < self.max_steps and not concluded:
            elapsed = time.monotonic() - started_at
            if elapsed >= self.max_seconds:
                step_count += 1
                step_id = f"STEP-{lead.lead_id}-{step_count:02d}-TIME"
                ctx.escalate_reason = (
                    f"Time budget of {self.max_seconds:.1f}s exhausted "
                    f"after {elapsed:.2f}s without conclusive evidence."
                )
                steps.append(
                    self._make_escalate_step(
                        step_id=step_id,
                        lead=lead,
                        tool_name="time_budget_guard",
                        tool_args={
                            "max_seconds": self.max_seconds,
                            "elapsed_seconds": round(elapsed, 3),
                        },
                        reason=ctx.escalate_reason,
                    )
                )
                concluded = True
                break

            step_count += 1
            step_id = f"STEP-{lead.lead_id}-{step_count:02d}"

            planned = self._select_action(lead, ctx, step_count)
            if planned is None:
                break

            action, audit_note = self._maybe_apply_gemini(
                planned=planned,
                lead=lead,
                ctx=ctx,
                steps=steps,
                evidence=collector.evidence,
                system_instruction=system_instruction,
            )

            normalized, validation_error = validate_tool_args(
                action.tool_name, action.tool_args
            )
            if validation_error or normalized is None:
                ctx.escalate_reason = (
                    f"Tool validation failed for '{action.tool_name}': {validation_error}"
                )
                steps.append(
                    self._make_escalate_step(
                        step_id=step_id,
                        lead=lead,
                        tool_name=action.tool_name,
                        tool_args=action.tool_args,
                        reason=ctx.escalate_reason,
                    )
                )
                concluded = True
                break

            call_key = self._call_key(action.tool_name, normalized)
            if call_key in ctx.seen_call_keys:
                ctx.escalate_reason = (
                    f"Repeated tool call '{action.tool_name}' without new evidence or "
                    "narrowed hypothesis."
                )
                steps.append(
                    self._make_escalate_step(
                        step_id=step_id,
                        lead=lead,
                        tool_name=action.tool_name,
                        tool_args=normalized,
                        reason=ctx.escalate_reason,
                    )
                )
                concluded = True
                break

            ctx.seen_call_keys.add(call_key)

            # Same validate → execute path for Gemini and deterministic fallback.
            raw_result = self.tools.execute(action.tool_name, normalized)
            result_hash = self._stable_result_hash(raw_result)
            source_ids = list(raw_result.get("source_ids") or [])
            new_sources = [sid for sid in source_ids if sid not in ctx.seen_source_ids]

            if result_hash in ctx.seen_result_hashes:
                ctx.escalate_reason = (
                    f"Repeated tool result for '{action.tool_name}' "
                    f"(hash {result_hash[:16]}…) without progress."
                )
                steps.append(
                    self._make_escalate_step(
                        step_id=step_id,
                        lead=lead,
                        tool_name=action.tool_name,
                        tool_args=normalized,
                        reason=ctx.escalate_reason,
                    )
                )
                concluded = True
                break

            ctx.seen_result_hashes.add(result_hash)

            hypothesis_before = ctx.hypothesis
            if raw_result.get("errors"):
                decision = StepDecision.ESCALATE
                ctx.escalate_reason = str(raw_result["errors"])
                concluded = True
                new_evidence: list[Evidence] = []
            else:
                self._update_context_from_tool(ctx, action.tool_name, raw_result)
                new_evidence = self._materialize_evidence(
                    collector=collector,
                    lead=lead,
                    step_id=step_id,
                    tool_name=action.tool_name,
                    tool_args=normalized,
                    raw_result=raw_result,
                    new_sources=new_sources,
                    ctx=ctx,
                )
                if action.tool_name == "trace_outgoing_funds" and not ctx.empty_trace:
                    new_evidence.extend(
                        self._materialize_linked_payment_invoice(
                            collector=collector,
                            lead=lead,
                            step_id=step_id,
                            ctx=ctx,
                        )
                    )
                for sid in source_ids:
                    ctx.seen_source_ids.add(sid)

                decision = self._decide_step(
                    lead=lead,
                    ctx=ctx,
                    step_count=step_count,
                    tool_name=action.tool_name,
                    new_evidence_count=len(new_evidence),
                    new_sources=new_sources,
                    hypothesis_before=hypothesis_before,
                )
                if decision in (
                    StepDecision.CONCLUDE,
                    StepDecision.DISCARD,
                    StepDecision.ESCALATE,
                ):
                    concluded = True

            reason = action.reason
            if audit_note:
                reason = f"{reason} | {audit_note}"
                ctx.audit_notes.append(audit_note)

            result_refs = list(source_ids) + [f"HASH:{result_hash}"]
            step = InvestigationStep(
                step_id=step_id,
                lead_id=lead.lead_id,
                action=action.tool_name.upper(),
                tool=action.tool_name,
                reason=reason,
                inputs=normalized,
                result_refs=result_refs,
                decision=decision,
            )
            steps.append(step)
            ctx.turn_records.append(
                TurnRecord(
                    step_id=step_id,
                    tool_name=action.tool_name,
                    normalized_args=normalized,
                    result_hash=result_hash,
                    source_ids=source_ids,
                    new_source_ids=new_sources,
                    result_summary={
                        "errors": raw_result.get("errors"),
                        "source_count": len(source_ids),
                        "provenance": raw_result.get("provenance"),
                    },
                    hypothesis_after=ctx.hypothesis,
                    decision=decision,
                    audit_note=audit_note,
                )
            )

        if not concluded and step_count >= self.max_steps:
            step_id = f"STEP-{lead.lead_id}-{step_count:02d}-ESCALATE"
            ctx.escalate_reason = (
                ctx.escalate_reason
                or f"Step budget of {self.max_steps} exhausted without conclusive evidence."
            )
            steps.append(
                self._make_escalate_step(
                    step_id=step_id,
                    lead=lead,
                    tool_name="step_budget_guard",
                    tool_args={"max_steps": self.max_steps},
                    reason=ctx.escalate_reason,
                )
            )

        case = self.build_case(lead, ctx, collector, steps, run_meta=run_meta)
        return case, steps, list(collector.evidence)

    def _select_action(
        self,
        lead: Lead,
        ctx: InvestigationContext,
        step_count: int,
    ) -> PlannedAction | None:
        """Choose the next deterministic tool action, or None when the plan is exhausted."""
        planned = self._next_deterministic_action(lead, ctx, step_count)
        if planned is None:
            return None
        tool_name, tool_args, reason = planned
        source = "fallback" if not self.gemini.is_configured else "deterministic"
        return PlannedAction(
            tool_name=tool_name,
            tool_args=tool_args,
            reason=reason,
            source=source,
        )

    def _maybe_apply_gemini(
        self,
        planned: PlannedAction,
        lead: Lead,
        ctx: InvestigationContext,
        steps: list[InvestigationStep],
        evidence: list[Evidence],
        system_instruction: str,
    ) -> tuple[PlannedAction, str | None]:
        """Optionally override the planned action with a validated Gemini call.

        Invalid Gemini proposals are discarded; the deterministic plan is kept and
        an audit note is returned. Offline/fallback never injects a function_call.
        """
        if not self.gemini.is_configured:
            return planned, "offline_fallback: using deterministic tool plan"

        prompt = self._build_prompt(lead, ctx, steps, evidence)
        resp = self.gemini.generate(
            prompt=prompt,
            system_instruction=system_instruction,
            tools=TOOL_DEFINITIONS,
        )
        if resp.is_fallback or not resp.function_call:
            return planned, "gemini_fallback: using deterministic tool plan"

        candidate_name = resp.function_call.get("name", planned.tool_name)
        candidate_args = resp.function_call.get("args", {}) or {}
        normalized, err = validate_tool_args(candidate_name, candidate_args)
        if err is not None or normalized is None:
            return (
                planned,
                f"gemini_invalid_args rejected ({err}); kept deterministic plan",
            )

        return (
            PlannedAction(
                tool_name=candidate_name,
                tool_args=normalized,
                reason=planned.reason,
                source="gemini",
            ),
            None,
        )

    # ------------------------------------------------------------------
    # Case construction (Phase 1 — evidence-derived, never risk_score)
    # ------------------------------------------------------------------

    def build_case(
        self,
        lead: Lead,
        ctx: InvestigationContext,
        collector: EvidenceCollector,
        steps: list[InvestigationStep],
        *,
        run_meta: dict[str, str] | None = None,
    ) -> Case:
        """Assemble Case strictly from resolved trail context and evaluated finding.

        Does not read ``lead.risk_score``. Status, providers, and amount come from
        evidence, exposure, and the terminal investigation decision.
        """
        finding = collector.evaluate_finding(
            finding_id=f"FINDING-{lead.lead_id}",
            lead_id=lead.lead_id,
            statement=ctx.hypothesis or lead.reason,
        )
        ctx.finding = finding

        terminal = steps[-1].decision if steps else StepDecision.ESCALATE
        status, confidence, amount = self._map_finding_to_case_fields(
            finding=finding,
            ctx=ctx,
            terminal=terminal,
        )

        limitations = [
            "Analysis bounded by available bank statements and CFDI repository.",
        ]
        meta = run_meta or self.policy.run_metadata(model="unknown")
        limitations.append(
            "agent_run:"
            + ",".join(f"{key}={value}" for key, value in sorted(meta.items()))
        )
        if ctx.escalate_reason:
            limitations.append(ctx.escalate_reason)
        if finding.rationale:
            limitations.append(f"Finding: {finding.rationale}")
        for note in ctx.audit_notes:
            limitations.append(f"Orchestration: {note}")

        providers = self._providers_from_context(ctx)
        evidence_ids = [e.evidence_id for e in collector.evidence]
        evidence_hash = self._canonical_evidence_hash(collector.evidence)

        return Case(
            case_id=f"CASE-{lead.lead_id}",
            status=status,
            hypothesis=ctx.hypothesis or f"Investigation into {lead.reason}",
            providers_involved=providers,
            amount_involved=amount,
            supporting_evidence=evidence_ids,
            confidence_level=confidence,
            limitations=limitations,
            citations=[
                "CFF Art. 69-B",
                "SAT CFDI 4.0 Standard",
                f"agent-policy:{meta.get('policy_version', POLICY_VERSION)}",
            ],
            generated_at=datetime.now(timezone.utc).isoformat(),
            evidence_hash=evidence_hash,
        )

    def _map_finding_to_case_fields(
        self,
        finding: Finding,
        ctx: InvestigationContext,
        terminal: StepDecision,
    ) -> tuple[str, str, float]:
        """Map Finding + terminal step to Case status/confidence/amount."""
        exposure_ready = (
            ctx.supported_exposure is not None and ctx.root_transaction_id is not None
        )

        if terminal == StepDecision.ESCALATE:
            return (
                "INSUFFICIENT_EVIDENCE",
                "LOW",
                float(ctx.supported_exposure or 0.0),
            )

        if terminal == StepDecision.DISCARD or ctx.empty_trace:
            return "UNSUBSTANTIATED", "MEDIUM", 0.0

        if finding.outcome == Outcome.REJECTED:
            return "UNSUBSTANTIATED", "MEDIUM", 0.0

        if (
            finding.outcome == Outcome.SUPPORTED
            and exposure_ready
            and terminal == StepDecision.CONCLUDE
        ):
            return "SUBSTANTIATED", "HIGH", float(ctx.supported_exposure or 0.0)

        if finding.outcome == Outcome.SUPPORTED and not exposure_ready:
            # Direct records without a calculated root exposure remain insufficient.
            return (
                "INSUFFICIENT_EVIDENCE",
                "LOW",
                float(ctx.supported_exposure or 0.0),
            )

        if finding.outcome == Outcome.INSUFFICIENT_EVIDENCE:
            return (
                "INSUFFICIENT_EVIDENCE",
                "LOW",
                float(ctx.supported_exposure or 0.0),
            )

        return "UNSUBSTANTIATED", "MEDIUM", float(ctx.supported_exposure or 0.0)

    @staticmethod
    def _providers_from_context(ctx: InvestigationContext) -> list[str]:
        """RFCs only — never account numbers or bare entity IDs from the lead."""
        return list(ctx.providers_involved)

    @staticmethod
    def _canonical_evidence_hash(evidence: list[Evidence]) -> str:
        payload = [
            {
                "evidence_id": e.evidence_id,
                "type": e.type.value if hasattr(e.type, "value") else e.type,
                "source_type": e.source_type,
                "source_id": e.source_id,
                "claim": e.claim,
                "strength": e.strength.value if hasattr(e.strength, "value") else e.strength,
                "record_hash": e.record_hash,
            }
            for e in evidence
        ]
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    def _next_deterministic_action(
        self,
        lead: Lead,
        ctx: InvestigationContext,
        step_count: int,
    ) -> tuple[str, dict[str, Any], str] | None:
        if ctx.empty_trace:
            return None

        if "trace_outgoing_funds" not in {k.split("|")[0] for k in ctx.seen_call_keys}:
            return (
                "trace_outgoing_funds",
                {"account_id": ctx.account_id, "max_depth": 3},
                f"Trace outgoing funds from account {ctx.account_id} for {lead.detector_id}",
            )

        if ctx.counterparty_rfcs:
            inspect_key = self._call_key(
                "inspect_counterparties", {"rfcs": sorted(ctx.counterparty_rfcs)}
            )
            if inspect_key not in ctx.seen_call_keys:
                return (
                    "inspect_counterparties",
                    {"rfcs": sorted(set(ctx.counterparty_rfcs))},
                    "Identify legal counterparties on the money trail",
                )

            for rfc in ctx.counterparty_rfcs:
                reg_key = self._call_key("check_regulatory_status", {"rfc": rfc})
                if reg_key not in ctx.seen_call_keys and step_count <= self.max_steps - 1:
                    if not any(k.startswith("check_regulatory_status|") for k in ctx.seen_call_keys):
                        return (
                            "check_regulatory_status",
                            {"rfc": rfc},
                            f"Check contextual SAT 69-B status for {rfc}",
                        )

        if ctx.root_transaction_id:
            exp_args: dict[str, Any] = {"root_transaction_id": ctx.root_transaction_id}
            if ctx.returned_transaction_id:
                exp_args["returned_transaction_id"] = ctx.returned_transaction_id
            exp_key = self._call_key("calculate_exposure", exp_args)
            if exp_key not in ctx.seen_call_keys:
                return (
                    "calculate_exposure",
                    exp_args,
                    "Calculate root-flow exposure without double-counting hops",
                )

        return None

    def _decide_step(
        self,
        lead: Lead,
        ctx: InvestigationContext,
        step_count: int,
        tool_name: str,
        new_evidence_count: int,
        new_sources: list[str],
        hypothesis_before: str,
    ) -> StepDecision:
        if ctx.empty_trace:
            return StepDecision.DISCARD

        if tool_name == "calculate_exposure" and ctx.supported_exposure is not None:
            return StepDecision.CONCLUDE

        hypothesis_narrowed = (
            bool(ctx.hypothesis)
            and ctx.hypothesis != hypothesis_before
            and ctx.hypothesis != lead.reason
        ) or (ctx.hypothesis != hypothesis_before and bool(ctx.hypothesis))

        if new_evidence_count > 0 or new_sources or hypothesis_narrowed:
            remaining = self._next_deterministic_action(lead, ctx, step_count + 1)
            if remaining is None and ctx.supported_exposure is not None:
                return StepDecision.CONCLUDE
            if remaining is None and not ctx.transaction_ids:
                return StepDecision.DISCARD
            if remaining is None:
                return StepDecision.CONCLUDE
            return StepDecision.FOLLOW

        ctx.escalate_reason = (
            "Step produced neither new evidence nor a narrowed hypothesis."
        )
        return StepDecision.ESCALATE

    # ------------------------------------------------------------------
    # Context / evidence materialization
    # ------------------------------------------------------------------

    def _update_context_from_tool(
        self,
        ctx: InvestigationContext,
        tool_name: str,
        raw_result: dict[str, Any],
    ) -> None:
        result = raw_result.get("result") or {}
        if tool_name == "trace_outgoing_funds":
            txs = result.get("transactions") or []
            if not txs:
                ctx.empty_trace = True
                return
            root_account = result.get("root_account") or ctx.account_id
            cycle_txs = self._select_cycle_path(txs, root_account)
            focus_txs = cycle_txs or txs

            tx_ids = [t["id"] for t in focus_txs if t.get("id")]
            ctx.transaction_ids = tx_ids

            payment_linked = [
                t for t in focus_txs if t.get("related_payment_id") and t.get("id")
            ]
            if not payment_linked:
                payment_linked = [
                    t for t in txs if t.get("related_payment_id") and t.get("id")
                ]
            if payment_linked:
                root_tx = payment_linked[0]
                ctx.root_transaction_id = root_tx["id"]
                ctx.root_amount = float(root_tx.get("amount") or 0.0)
                ctx.payment_id = root_tx.get("related_payment_id")
            elif not ctx.root_transaction_id and tx_ids:
                ctx.root_transaction_id = tx_ids[0]
                ctx.root_amount = float(focus_txs[0].get("amount") or 0.0)
            elif ctx.root_transaction_id and ctx.root_amount is None:
                root_tx = next(
                    (t for t in txs if t.get("id") == ctx.root_transaction_id), None
                )
                if root_tx:
                    ctx.root_amount = float(root_tx.get("amount") or 0.0)

            origin_account = root_account
            if ctx.root_transaction_id:
                root_tx = next(
                    (t for t in txs if t.get("id") == ctx.root_transaction_id),
                    None,
                )
                if root_tx and root_tx.get("from_account"):
                    origin_account = root_tx["from_account"]

            downstream: list[float] = []
            for tx in focus_txs:
                if tx.get("id") == ctx.root_transaction_id:
                    continue
                if (
                    tx.get("to_account") == origin_account
                    and tx.get("id") != ctx.root_transaction_id
                ):
                    ctx.returned_transaction_id = tx["id"]
                    ctx.returned_amount = float(tx.get("amount") or 0.0)
                else:
                    downstream.append(float(tx.get("amount") or 0.0))
            ctx.downstream_amounts = downstream

            if ctx.payment_id:
                payment = self.tools.payments.get(ctx.payment_id)
                if payment:
                    ctx.invoice_uuid = payment.related_invoice_uuid

            accounts_seen: set[str] = set()
            for tx in focus_txs:
                for acc in (tx.get("from_account"), tx.get("to_account")):
                    if acc and acc != origin_account:
                        accounts_seen.add(acc)
            rfcs: list[str] = []
            for acc_no in sorted(accounts_seen):
                account = self.tools.accounts.get(acc_no)
                if not account:
                    continue
                entity = self.tools.entities.get(account.entity_id)
                if entity and entity.rfc:
                    rfcs.append(entity.rfc)
                    provider = self.tools.providers.get(entity.rfc)
                    if provider and entity.rfc not in ctx.providers_involved:
                        ctx.providers_involved.append(entity.rfc)
            ctx.counterparty_rfcs = rfcs
            ctx.hypothesis = (
                f"Funds leaving {ctx.account_id} via "
                f"{', '.join(tx_ids[:3])} warrant counterparty and exposure analysis"
            )

        elif tool_name == "inspect_counterparties":
            for item in result.get("counterparties") or []:
                rfc = item.get("rfc")
                if rfc and rfc not in ctx.providers_involved and item.get("provider"):
                    ctx.providers_involved.append(rfc)
            ctx.hypothesis = (
                f"Counterparties {', '.join(ctx.counterparty_rfcs) or 'unknown'} "
                "identified on the money trail"
            )

        elif tool_name == "calculate_exposure":
            root_amount = float(
                result.get("root_amount")
                if result.get("root_amount") is not None
                else (ctx.root_amount or 0.0)
            )
            returned_amount = float(
                result.get("returned_amount")
                if result.get("returned_amount") is not None
                else (ctx.returned_amount or 0.0)
            )
            exposure = ExposureCalculator.calculate_root_flow_exposure(
                root_flow_id=result.get("root_transaction_id")
                or ctx.root_transaction_id
                or "UNKNOWN",
                root_amount=root_amount,
                downstream_transfers=list(ctx.downstream_amounts),
                returned_amount=returned_amount,
            )
            ctx.root_amount = exposure.root_amount
            ctx.returned_amount = exposure.verified_returned_amount
            ctx.supported_exposure = exposure.supported_exposure
            ctx.net_exposure = exposure.net_exposure
            if result.get("root_transaction_id"):
                ctx.root_transaction_id = result["root_transaction_id"]
            ctx.hypothesis = (
                f"Root-flow exposure {ctx.supported_exposure:,.2f} MXN "
                f"(net {ctx.net_exposure:,.2f} MXN) without hop double-counting"
            )

    def _materialize_evidence(
        self,
        collector: EvidenceCollector,
        lead: Lead,
        step_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
        raw_result: dict[str, Any],
        new_sources: list[str],
        ctx: InvestigationContext,
    ) -> list[Evidence]:
        created: list[Evidence] = []
        result = raw_result.get("result") or {}
        provenance = raw_result.get("provenance") or tool_name
        focus_ids = set(ctx.transaction_ids) if tool_name == "trace_outgoing_funds" else None

        if tool_name == "trace_outgoing_funds":
            for tx in result.get("transactions") or []:
                tx_id = tx.get("id")
                if not tx_id or any(e.source_id == tx_id for e in collector.evidence):
                    continue
                if focus_ids is not None and tx_id not in focus_ids:
                    continue
                strength = self._transaction_evidence_strength(tx_id, ctx)
                claim = (
                    f"Transaction {tx_id}: {tx.get('amount'):,.2f} MXN from "
                    f"{tx.get('from_account')} to {tx.get('to_account')} "
                    f"on {tx.get('transaction_date')} (provenance: {provenance})."
                )
                created.append(
                    collector.add_record(
                        evidence_id=f"EVD-{lead.lead_id}-{tx_id}",
                        ev_type=EvidenceType.TRANSACTION,
                        source_type="BANK_RECORD",
                        source_id=tx_id,
                        claim=claim,
                        strength=strength,
                        raw_payload=tx,
                        gathered_by_step_id=step_id,
                    )
                )

        elif tool_name == "inspect_counterparties":
            for item in result.get("counterparties") or []:
                rfc = item.get("rfc") or "UNKNOWN"
                provider = item.get("provider")
                entity = item.get("entity")
                if any(e.source_id == rfc for e in collector.evidence):
                    continue
                name = None
                if provider:
                    name = provider.get("legal_name") or provider.get("name")
                elif entity:
                    name = entity.get("name")
                claim = (
                    f"Counterparty RFC {rfc}"
                    + (f" ({name})" if name else "")
                    + f" resolved on money trail (provenance: {provenance})."
                )
                created.append(
                    collector.add_record(
                        evidence_id=f"EVD-{lead.lead_id}-CPTY-{rfc}",
                        ev_type=EvidenceType.RELATIONSHIP,
                        source_type="ENTITY_REGISTRY",
                        source_id=rfc,
                        claim=claim,
                        strength=EvidenceStrength.CORROBORATING,
                        raw_payload=item,
                        gathered_by_step_id=step_id,
                    )
                )

        elif tool_name == "check_regulatory_status":
            rfc = result.get("rfc") or tool_args.get("rfc") or "UNKNOWN"
            if any(e.source_id == f"EFOS:{rfc}" for e in collector.evidence):
                return created
            claim = (
                f"SAT 69-B contextual status for {rfc}: "
                f"{result.get('efos_status') or result.get('status')}. "
                f"{result.get('note', '')}"
            )
            created.append(
                collector.add_record(
                    evidence_id=f"EVD-{lead.lead_id}-EFOS-{rfc}",
                    ev_type=EvidenceType.REGULATORY_STATUS,
                    source_type="SAT_69B",
                    source_id=f"EFOS:{rfc}",
                    claim=claim.strip(),
                    strength=EvidenceStrength.CIRCUMSTANTIAL,
                    raw_payload=result,
                    gathered_by_step_id=step_id,
                )
            )

        elif tool_name == "calculate_exposure":
            root_id = ctx.root_transaction_id or result.get("root_transaction_id") or "UNKNOWN"
            if any(e.source_id == f"EXPOSURE:{root_id}" for e in collector.evidence):
                return created
            exposure = ExposureCalculator.calculate_root_flow_exposure(
                root_flow_id=root_id,
                root_amount=float(ctx.root_amount or result.get("root_amount") or 0.0),
                downstream_transfers=list(ctx.downstream_amounts),
                returned_amount=float(
                    ctx.returned_amount
                    if ctx.returned_amount is not None
                    else (result.get("returned_amount") or 0.0)
                ),
            )
            claim = (
                f"Root-flow exposure for {root_id}: supported "
                f"{exposure.supported_exposure:,.2f} MXN, net "
                f"{exposure.net_exposure:,.2f} MXN "
                f"(returned {exposure.verified_returned_amount:,.2f} MXN; "
                f"policy {exposure.policy_applied}; provenance: {provenance})."
            )
            created.append(
                collector.add_record(
                    evidence_id=f"EVD-{lead.lead_id}-EXPOSURE-{root_id}",
                    ev_type=EvidenceType.TRANSACTION,
                    source_type="EXPOSURE_CALCULATION",
                    source_id=f"EXPOSURE:{root_id}",
                    claim=claim,
                    strength=EvidenceStrength.DIRECT,
                    raw_payload={
                        "root_transaction_id": root_id,
                        "root_amount": exposure.root_amount,
                        "downstream_flow": exposure.downstream_flow,
                        "returned_amount": exposure.verified_returned_amount,
                        "supported_exposure": exposure.supported_exposure,
                        "net_exposure": exposure.net_exposure,
                        "policy": exposure.policy_applied,
                    },
                    gathered_by_step_id=step_id,
                )
            )

        elif tool_name == "inspect_invoices":
            for inv in result.get("invoices") or []:
                uuid = inv.get("uuid")
                if not uuid or any(e.source_id == uuid for e in collector.evidence):
                    continue
                claim = (
                    f"Invoice {uuid} for {inv.get('amount'):,.2f} "
                    f"{inv.get('currency', 'MXN')} issued by {inv.get('provider_rfc')} "
                    f"to {inv.get('receiver_rfc')} on {inv.get('issue_date')}."
                )
                created.append(
                    collector.add_record(
                        evidence_id=f"EVD-{lead.lead_id}-INV-{uuid[:8]}",
                        ev_type=EvidenceType.INVOICE,
                        source_type="CFDI",
                        source_id=uuid,
                        claim=claim,
                        strength=EvidenceStrength.CORROBORATING,
                        raw_payload=inv,
                        gathered_by_step_id=step_id,
                    )
                )

        return created

    def _materialize_linked_payment_invoice(
        self,
        collector: EvidenceCollector,
        lead: Lead,
        step_id: str,
        ctx: InvestigationContext,
    ) -> list[Evidence]:
        """Attach CFDI/payment records linked from the economic root transaction."""
        created: list[Evidence] = []
        if ctx.payment_id:
            payment = self.tools.payments.get(ctx.payment_id)
            if payment and not any(e.source_id == payment.id for e in collector.evidence):
                payload = payment.to_dict()
                created.append(
                    collector.add_record(
                        evidence_id=f"EVD-{lead.lead_id}-PMT-{payment.id}",
                        ev_type=EvidenceType.DOCUMENT,
                        source_type="PAYMENT_RECORD",
                        source_id=payment.id,
                        claim=(
                            f"Payment {payment.id} of {payment.amount:,.2f} MXN on "
                            f"{payment.payment_date} settles invoice "
                            f"{payment.related_invoice_uuid}."
                        ),
                        strength=EvidenceStrength.CORROBORATING,
                        raw_payload=payload,
                        gathered_by_step_id=step_id,
                    )
                )
                ctx.seen_source_ids.add(payment.id)
                ctx.invoice_uuid = payment.related_invoice_uuid

        invoice_uuid = ctx.invoice_uuid
        if invoice_uuid:
            invoice = self.tools.invoices.get(invoice_uuid)
            if invoice and not any(e.source_id == invoice.uuid for e in collector.evidence):
                payload = invoice.to_dict()
                created.append(
                    collector.add_record(
                        evidence_id=f"EVD-{lead.lead_id}-INV-{invoice.uuid[:8]}",
                        ev_type=EvidenceType.INVOICE,
                        source_type="CFDI",
                        source_id=invoice.uuid,
                        claim=(
                            f"Invoice {invoice.uuid} for {invoice.amount:,.2f} "
                            f"{invoice.currency} issued by {invoice.provider_rfc} "
                            f"to {invoice.receiver_rfc} on {invoice.issue_date}."
                        ),
                        strength=EvidenceStrength.CORROBORATING,
                        raw_payload=payload,
                        gathered_by_step_id=step_id,
                    )
                )
                ctx.seen_source_ids.add(invoice.uuid)
        return created

    @staticmethod
    def _transaction_evidence_strength(
        tx_id: str, ctx: InvestigationContext
    ) -> EvidenceStrength:
        """Root, continuing hops, and return legs are DIRECT economic linkage."""
        if tx_id == ctx.root_transaction_id or tx_id == ctx.returned_transaction_id:
            return EvidenceStrength.DIRECT
        if tx_id in ctx.transaction_ids:
            return EvidenceStrength.DIRECT
        return EvidenceStrength.CORROBORATING

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_account_id(self, lead: Lead) -> str:
        entity_id = (lead.entity_id or "").strip()
        if entity_id:
            if self.tools.accounts.get(entity_id):
                return entity_id
            accounts = self.tools.accounts.list_for_entity(entity_id)
            if accounts:
                return accounts[0].account_no
            return entity_id

        for prefix in (
            "LEAD-PASSTHROUGH-",
            "LEAD-FAN-OUT-",
            "LEAD-FAN-IN-",
            "LEAD-SUPPLIER-CONCENTRATION-",
        ):
            if lead.lead_id.startswith(prefix):
                candidate = lead.lead_id[len(prefix) :]
                if candidate:
                    return candidate

        root = self._infer_root_tx_from_lead(lead)
        if root:
            tx = self.tools.transactions.get(root)
            if tx and tx.from_account:
                return tx.from_account
        return entity_id

    def _infer_root_tx_from_lead(self, lead: Lead) -> str | None:
        match = _TX_ID_RE.search(lead.lead_id) or _TX_ID_RE.search(lead.reason)
        if match:
            return match.group(0)
        for signal in lead.signals:
            match = _TX_ID_RE.search(signal)
            if match:
                return match.group(0)
        return None

    @staticmethod
    def _select_cycle_path(
        txs: list[dict[str, Any]], start_account: str
    ) -> list[dict[str, Any]]:
        adjacency: dict[str, list[dict[str, Any]]] = {}
        for tx in txs:
            frm = tx.get("from_account")
            if frm:
                adjacency.setdefault(frm, []).append(tx)

        stack: list[tuple[str, list[dict[str, Any]], set[str]]] = [
            (start_account, [], set())
        ]
        while stack:
            current, path, visited_edges = stack.pop()
            for tx in adjacency.get(current, []):
                tx_id = tx.get("id")
                if not tx_id or tx_id in visited_edges:
                    continue
                nxt = tx.get("to_account")
                new_path = path + [tx]
                if nxt == start_account and len(new_path) >= 2:
                    return new_path
                if nxt and len(new_path) < 5:
                    stack.append((nxt, new_path, visited_edges | {tx_id}))
        return []

    def _build_prompt(
        self,
        lead: Lead,
        ctx: InvestigationContext,
        steps: list[InvestigationStep],
        evidence: list[Evidence],
    ) -> str:
        return (
            f"Investigating Lead {lead.lead_id} on Entity/Account {lead.entity_id}.\n"
            f"Resolved account_id for tracing: {ctx.account_id}.\n"
            f"Detector: {lead.detector_id}. Reason: {lead.reason}.\n"
            f"Hypothesis: {ctx.hypothesis}\n"
            f"Prior Steps Taken: {len(steps)}. Evidence Collected: {len(evidence)} items.\n"
            f"Known transaction IDs: {ctx.transaction_ids}\n"
            f"Known counterparty RFCs: {ctx.counterparty_rfcs}\n"
            "Select the next tool to verify facts or identify counterparties. "
            "Always include required arguments (e.g. account_id for trace_outgoing_funds)."
        )

    def _hypothesis_narrowed(self, ctx: InvestigationContext, lead: Lead) -> bool:
        return bool(ctx.hypothesis) and ctx.hypothesis != lead.reason

    @staticmethod
    def _call_key(tool_name: str, args: dict[str, Any]) -> str:
        return f"{tool_name}|{json.dumps(args, sort_keys=True, default=str)}"

    @staticmethod
    def _stable_result_hash(payload: dict[str, Any]) -> str:
        """Hash tool result without execution_time so timing cannot mask duplicates."""
        stable = {
            "result": payload.get("result"),
            "provenance": payload.get("provenance"),
            "source_ids": payload.get("source_ids"),
            "errors": payload.get("errors"),
        }
        serialized = json.dumps(stable, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _full_hash(payload: dict[str, Any]) -> str:
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _make_escalate_step(
        self,
        step_id: str,
        lead: Lead,
        tool_name: str,
        tool_args: dict[str, Any],
        reason: str,
    ) -> InvestigationStep:
        return InvestigationStep(
            step_id=step_id,
            lead_id=lead.lead_id,
            action="ESCALATE",
            tool=tool_name,
            reason=reason,
            inputs=tool_args,
            result_refs=[],
            decision=StepDecision.ESCALATE,
        )
