"""Exposure accounting and evidence collection."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from truelock.domain.models.investigation import (
    Evidence,
    EvidenceStrength,
    EvidenceType,
    Exposure,
    Finding,
    Outcome,
)


class ExposureCalculator:
    """Calculates financial exposure without double-counting edges in cyclical/downstream flows."""

    @staticmethod
    def calculate_root_flow_exposure(
        root_flow_id: str,
        root_amount: float,
        downstream_transfers: list[float],
        returned_amount: float = 0.0,
    ) -> Exposure:
        """Root-flow exposure calculation.

        Invariants:
        - Downstream transfers do not increase exposure (avoids 1M + 920k double count).
        - Supported exposure is the root economic payment made.
        - Net exposure is supported exposure minus verified returned amount.
        """
        downstream_total = sum(downstream_transfers)
        net_exposure = max(0.0, root_amount - returned_amount)
        return Exposure(
            root_flow_id=root_flow_id,
            root_amount=root_amount,
            downstream_flow=downstream_total,
            verified_returned_amount=returned_amount,
            supported_exposure=root_amount,
            net_exposure=net_exposure,
            policy_applied="ROOT_FLOW_UNDUPLICATED_WITH_RETURN_OFFSET",
        )


class EvidenceCollector:
    """Collects and validates forensic evidence records."""

    def __init__(self) -> None:
        self.evidence: list[Evidence] = []

    def add_record(
        self,
        evidence_id: str,
        ev_type: EvidenceType,
        source_type: str,
        source_id: str,
        claim: str,
        strength: EvidenceStrength,
        raw_payload: dict[str, Any] | None = None,
        gathered_by_step_id: str | None = None,
    ) -> Evidence:
        """Create a verifiable Evidence item with payload hash."""
        record_hash = None
        if raw_payload is not None:
            serialized = json.dumps(raw_payload, sort_keys=True)
            record_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        item = Evidence(
            evidence_id=evidence_id,
            type=ev_type,
            source_type=source_type,
            source_id=source_id,
            claim=claim,
            strength=strength,
            gathered_by_step_id=gathered_by_step_id,
            record_hash=record_hash,
        )
        self.evidence.append(item)
        return item

    def evaluate_finding(
        self,
        finding_id: str,
        lead_id: str,
        statement: str,
        required_direct_evidence_count: int = 1,
    ) -> Finding:
        """Evaluate finding admissibility: requires at least one DIRECT evidence record."""
        direct_count = sum(1 for e in self.evidence if e.strength == EvidenceStrength.DIRECT)
        if direct_count >= required_direct_evidence_count:
            outcome = Outcome.SUPPORTED
            rationale = f"Supported by {direct_count} direct evidence items."
        elif len(self.evidence) > 0:
            outcome = Outcome.INSUFFICIENT_EVIDENCE
            rationale = "Circumstantial indicators present, but no direct economic transaction linkage."
        else:
            outcome = Outcome.REJECTED
            rationale = "No corroborating evidence found; hypothesis disproven or unevidenced."

        return Finding(
            finding_id=finding_id,
            lead_id=lead_id,
            outcome=outcome,
            statement=statement,
            evidence_ids=[e.evidence_id for e in self.evidence],
            rationale=rationale,
        )
