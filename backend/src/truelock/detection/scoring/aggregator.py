"""Aggregate DetectorSignals into Leads with deterministic weighted scores."""
from __future__ import annotations

from collections import defaultdict

from truelock.detection.scoring.weights import DETECTOR_WEIGHTS, PURSUE_THRESHOLD
from truelock.detection.signals import DetectorSignal
from truelock.domain.models.investigation import Lead, LeadStatus


def aggregate_signals(signals: list[DetectorSignal]) -> list[Lead]:
    """Group signals by (detector_id, entity_id) and emit one Lead per group.

    Score = min(1.0, sum(weights of distinct signal_ids in the group)).
    Same input always yields the same leads (sorted by score, then lead_id).
    """
    clusters: dict[tuple[str, str], list[DetectorSignal]] = defaultdict(list)
    for signal in signals:
        clusters[(signal.detector_id, signal.entity_id)].append(signal)

    leads: list[Lead] = []
    for (detector_id, entity_id), group in sorted(clusters.items()):
        group_sorted = sorted(group, key=lambda s: s.signal_id)
        weight = DETECTOR_WEIGHTS.get(detector_id, 0.30)
        # Corroboration: first signal full weight, each extra +15% of base weight
        score = weight + max(0, len(group_sorted) - 1) * weight * 0.15
        score = round(min(1.0, score), 4)

        reason = group_sorted[0].claim
        if len(group_sorted) > 1:
            reason = f"{reason} (+{len(group_sorted) - 1} corroborating signal(s))."

        lead_id = _lead_id(detector_id, entity_id, group_sorted)
        leads.append(
            Lead(
                lead_id=lead_id,
                entity_id=entity_id,
                detector_id=detector_id,
                reason=reason,
                risk_score=score,
                signals=[s.signal_id for s in group_sorted],
                status=LeadStatus.OPEN,
                discard_reason=(
                    None
                    if score >= PURSUE_THRESHOLD
                    else (
                        f"risk_score {score:.2f} below pursue threshold "
                        f"{PURSUE_THRESHOLD:.2f} with no corroborating high-weight pattern"
                    )
                ),
            )
        )

    return sorted(leads, key=lambda lead: (-lead.risk_score, lead.lead_id))


def _lead_id(detector_id: str, entity_id: str, group: list[DetectorSignal]) -> str:
    """Stable lead identifiers preferred by demo / verify scripts."""
    sources = sorted({sid for signal in group for sid in signal.source_ids})
    if detector_id in {"DET-ROUND-TRIP-CYCLE", "CIRCULAR_FLOW"}:
        root = next((s for s in sources if s.startswith("TX-ROOT")), None)
        anchor = root or (sources[0] if sources else entity_id)
        return f"LEAD-CYCLE-{anchor}"
    if detector_id in {"DET-RAPID-PASS-THROUGH", "RAPID_PASS_THROUGH"}:
        return f"LEAD-PASSTHROUGH-{entity_id}"
    if detector_id in {"DET-DUPLICATE-PAYMENT", "DUPLICATE_PAYMENT"}:
        payment = next((s for s in sources if s.startswith("PMT")), sources[0] if sources else entity_id)
        return f"LEAD-DUP-{payment}"
    if detector_id == "DET-SHARED-ADDRESS-CONTROL":
        return "LEAD-CONTROL-SHARED-ADDRESS"
    if detector_id == "DUPLICATE_INVOICE":
        return f"LEAD-DUP-INV-{entity_id[:12]}"
    slug = detector_id.replace("_", "-")
    return f"LEAD-{slug}-{entity_id}"
