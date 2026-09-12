# Payment complement

Sourcing: `research/sat/README.md`. Implements
`domain/schemas/payment.schema.json` and `transaction.schema.json`.

SAT's payment-complement materials expose: payment date, form, currency,
amount, related invoice UUID, payment method, installment information,
previous balance, amount paid, and remaining balance.

## Implementation rule

Keep `INVOICE → PAYMENT → TRANSACTION` as three distinct records
(`docs/contracts/domain.md` explains why). A `Payment` references exactly
one `Invoice` (`related_invoice_uuid`) and zero or more underlying
`Transaction`s (`transaction_ids`); a `Transaction` may reference zero
Payments (a bare fund movement, e.g. layering between shell accounts —
often the most evidentially important kind, see `docs/detection/rules.md`
→ "rapid pass-through").
