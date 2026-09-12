# Data model overview

Quick visual index. The authoritative contracts are
`domain/schemas/*.schema.json`, explained in `docs/contracts/domain.md`;
this page is a map, not a source of truth.

```
Entity (company | individual)
  ├─ Provider (rfc, efos_status)         [when entity is a supplier]
  └─ Account (account_no)

Invoice (uuid, provider_rfc, receiver_rfc, amount)
  └─ Payment (related_invoice_uuid, amount)
        └─ Transaction (from_account, to_account, amount)   [0..n]

Detection layer:
  DetectorSignal --(aggregated by risk score)--> Lead
  Lead --(investigated via)--> InvestigationStep --(produces)--> Evidence
  Evidence --(assembled into)--> Case
```

See `research/graph/README.md` for how these become graph nodes/edges for
traversal and visualization.
