# scripts/ingest/

**Purpose:** defensive parsers turning raw sources (CFDI XML, CSV bank
exports) into canonical records matching `domain/schemas/`.

**What goes here:** one parser per source format. Reject malformed
records rather than best-effort-guessing (`SECURITY.md`).

**Depends on:** `domain/entities/`.

## Implemented (TASK-001)

| Module | Source | Produces |
|---|---|---|
| `cfdi.py` | CFDI 4.0 XML | `Invoice` |
| `bank_csv.py` | bank CSV export | `Transaction` |
| `errors.py` | — | `IngestResult`, `Rejection`, `IngestError` |

```python
from scripts.ingest import parse_cfdi_directory, parse_bank_csv

result = parse_cfdi_directory("data/raw/cfdi/")
print(result.render())      # "412 accepted, 3 rejected" + each reason
if not result.ok:
    ...                     # a caller that tolerates rejections must look at them
```

## Reject, never guess

Every parser follows the same rule, and each rejection carries a source,
a locator (line number or file) and a reason — so a human can find the
record again.

A guessed field becomes a fact three layers later, when a case file cites
it and nothing remembers it was a guess. Concretely:

- A CFDI with no `TimbreFiscalDigital` UUID is rejected. The folio is the
  join key everything else uses; a missing one would fail to join
  *silently*, reading downstream as "no duplicates found".
- An unparseable amount is rejected, never zeroed — a zero would shrink
  every total downstream without a trace.
- A parenthesised negative in a bank export is left to fail, because
  different banks mean different things by it.

## Rejections are reported, not swallowed

`IngestResult` carries both halves and `ok` is true only when nothing was
refused. "We ingested 9,900 of 10,000 rows" is a finding about the data,
and the 100 that were dropped may be the interesting ones.

## One bad record vs. one bad source

The distinction is deliberate:

- **`Rejection`** — this record is unusable; keep going. Malformed XML in
  one file out of thousands must not fail the directory.
- **`IngestError`** — the *source* is unusable; stop. A bank CSV missing
  its `amount` column is a mapping error, not a data error, and the right
  response is to fix `BankCsvMapping` rather than ingest a partial table.

## Adding a bank

Bank exports are the least standardised source here — every institution
names its columns differently. Pass a `BankCsvMapping` rather than
teaching the parser to guess which column holds the amount:

```python
mapping = BankCsvMapping(
    transaction_id="ref", from_account="debit_account",
    to_account="credit_account", transaction_date="value_date",
    amount="importe", related_payment_id=None,
)
parse_bank_csv(path, mapping=mapping)
```

Unmapped extra columns are ignored — an export carrying more than we need
is normal. A *missing* required column fails the file.
