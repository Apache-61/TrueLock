"""Deterministic signal → lead aggregation."""
from __future__ import annotations

from .aggregator import aggregate_signals
from .weights import CONTROL_RISK_CEILING, DETECTOR_WEIGHTS, PURSUE_THRESHOLD

__all__ = [
    "CONTROL_RISK_CEILING",
    "DETECTOR_WEIGHTS",
    "PURSUE_THRESHOLD",
    "aggregate_signals",
]
