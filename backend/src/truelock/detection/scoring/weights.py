"""Deterministic detector weights and pursue threshold.

Documented for judges in ``detection/scoring/README.md``.
"""
from __future__ import annotations

# Weights map 1:1 to lead risk_score for a single signal (clamped to [0, 1]).
# Extra signals in the same cluster add 15% of base weight each.
DETECTOR_WEIGHTS: dict[str, float] = {
    # Existing demo IDs — preserve prior demo score bands
    "DET-ROUND-TRIP-CYCLE": 0.98,
    "DET-RAPID-PASS-THROUGH": 0.88,
    "DET-DUPLICATE-PAYMENT": 0.85,
    "DET-SHARED-ADDRESS-CONTROL": 0.35,
    # Documented library IDs (docs/detection/rules.md)
    "CIRCULAR_FLOW": 0.98,
    "RAPID_PASS_THROUGH": 0.88,
    "DUPLICATE_PAYMENT": 0.85,
    "DUPLICATE_INVOICE": 0.85,
    "UNUSUAL_AMOUNT": 0.62,
    "SUPPLIER_CONCENTRATION": 0.70,
    "INVOICE_PAYMENT_MISMATCH": 0.80,
    "FAN_IN": 0.72,
    "FAN_OUT": 0.72,
    "SHELL_NETWORK": 0.78,
    "69B_CORRELATION": 0.35,  # contextual; alone must not accuse
    "UNUSUAL_TIMING": 0.55,
}

#: Agent pursue threshold (docs/contracts/leads.md). Below = discard candidate.
PURSUE_THRESHOLD = 0.60

#: Control / co-location alone must stay below this.
CONTROL_RISK_CEILING = 0.50
