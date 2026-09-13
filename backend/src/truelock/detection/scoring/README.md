# Detection scoring

Signals from `detection/rules/` are aggregated here into `Lead` records.

## Formula

```
risk_score = min(1.0, base_weight + (n_signals - 1) * base_weight * 0.15)
```

Grouped by `(detector_id, entity_id)`. Identical datasets always produce
identical scores and lead IDs.

## Weights

| Detector ID | Weight | Notes |
|---|---|---|
| `DET-ROUND-TRIP-CYCLE` / `CIRCULAR_FLOW` | 0.98 | Demo cycle band |
| `DET-RAPID-PASS-THROUGH` / `RAPID_PASS_THROUGH` | 0.88 | Requires temporal order + ≤24h window |
| `DET-DUPLICATE-PAYMENT` / `DUPLICATE_PAYMENT` | 0.85 | |
| `DUPLICATE_INVOICE` | 0.85 | |
| `INVOICE_PAYMENT_MISMATCH` | 0.80 | |
| `SHELL_NETWORK` | 0.78 | Multi-factor only (not address alone) |
| `FAN_IN` / `FAN_OUT` | 0.72 | |
| `SUPPLIER_CONCENTRATION` | 0.70 | |
| `UNUSUAL_AMOUNT` | 0.62 | Median/MAD |
| `UNUSUAL_TIMING` | 0.55 | Below pursue alone |
| `69B_CORRELATION` | 0.35 | Contextual; alone does not accuse |
| `DET-SHARED-ADDRESS-CONTROL` | 0.35 | Negative control |

## Thresholds

- **Pursue threshold:** `0.60` — agent should investigate at or above.
- **Control ceiling:** `0.50` — shared-address control must stay below.

Source of truth: `weights.py`.
