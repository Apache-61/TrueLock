"""Detector registry — every pattern from docs/detection/rules.md."""
from __future__ import annotations

from collections.abc import Callable

from truelock.detection.dataset import CanonicalDataset
from truelock.detection.rules import (
    circular_flow,
    correlation_69b,
    duplicate_invoice,
    duplicate_payment,
    fan_in,
    fan_out,
    invoice_payment_mismatch,
    rapid_pass_through,
    shared_address_control,
    shell_network,
    supplier_concentration,
    unusual_amount,
    unusual_timing,
)
from truelock.detection.signals import DetectorSignal

DetectFn = Callable[[CanonicalDataset], list[DetectorSignal]]

#: Ordered registry. Order is stable for determinism of concatenated signals.
DETECTOR_REGISTRY: list[tuple[str, DetectFn]] = [
    ("DET-ROUND-TRIP-CYCLE", circular_flow.detect),
    ("DET-RAPID-PASS-THROUGH", rapid_pass_through.detect),
    ("DET-DUPLICATE-PAYMENT", duplicate_payment.detect),
    ("DUPLICATE_INVOICE", duplicate_invoice.detect),
    ("UNUSUAL_AMOUNT", unusual_amount.detect),
    ("SUPPLIER_CONCENTRATION", supplier_concentration.detect),
    ("INVOICE_PAYMENT_MISMATCH", invoice_payment_mismatch.detect),
    ("FAN_IN", fan_in.detect),
    ("FAN_OUT", fan_out.detect),
    ("SHELL_NETWORK", shell_network.detect),
    ("69B_CORRELATION", correlation_69b.detect),
    ("UNUSUAL_TIMING", unusual_timing.detect),
    ("DET-SHARED-ADDRESS-CONTROL", shared_address_control.detect),
]


def run_all_detectors(dataset: CanonicalDataset) -> list[DetectorSignal]:
    """Execute every registered detector; same dataset → same signal list."""
    signals: list[DetectorSignal] = []
    for _name, fn in DETECTOR_REGISTRY:
        signals.extend(fn(dataset))
    return sorted(signals, key=lambda s: (s.detector_id, s.signal_id))
