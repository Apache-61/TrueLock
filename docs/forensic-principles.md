# Forensic Principles & Invariants

TrueLock follows five core forensic accounting principles synthesized from Mexican fiscal standards (CFF Art. 69-B, CFDI 4.0) and corporate fraud investigation methodologies.

---

## 1. Deterministic Authority Boundary

The LLM is an investigator and narrator, never the judge or accountant:
- **Code owns arithmetic**: Sums, balances, flow timing, and exposure calculations are computed in Python. The LLM is never prompted to compute monetary sums.
- **Code owns parsing**: XML and CSV inputs are ingested with strict Pydantic validation (`extra="forbid"`).
- **Code owns tool execution**: Gemini only outputs structured tool selections (`name`, `arguments`). Python validates parameters against repository interfaces before running queries.

---

## 2. Proof Before Accusation

Every investigation must culminate in one of three auditable outcomes:
- `SUPPORTED`: Direct transactional evidence proves the fraudulent movement or circular scheme.
- `REJECTED`: The hypothesis is contradicted by evidence or proven to be legitimate commercial activity.
- `INSUFFICIENT_EVIDENCE`: Anomalies exist, but records are inadequate to meet the standard of proof.

### The Legitimate Control Invariant
To ensure the system does not produce runaway false positives, TrueLock includes a deliberate control case:
- Two independent suppliers share a commercial building address (`Av. Reforma 222, CDMX`).
- Both suppliers have separate RFCs, distinct bank accounts, different legal representatives, and zero inter-supplier fund transfers.
- **Rule**: Shared commercial address alone is never sufficient to assert economic linkage or fraud.

---

## 3. Exposure Accounting: No Edge Double-Counting

In cyclical and pass-through fund routing schemes (e.g., Company $1,000,000 \to$ Vendor $920,000 \to$ Shell $740,000 \to$ Company):
- **False Accounting**: Summing all graph edges ($1,000,000 + 920,000 + 740,000 = \$2,660,000$) double-counts the same economic capital as it circulates.
- **TrueLock Invariant**:
  - **Supported Exposure**: The unique root originating disbursement from the company ($\$1,000,000\text{ MXN}$).
  - **Downstream Flow**: Separately tracked as velocity/routing evidence ($\$920,000\text{ MXN}$).
  - **Verified Returned Amount**: Confirmed circular recovery ($\$740,000\text{ MXN}$).
  - **Net Unrecovered Exposure**: $\text{Root} - \text{Returned} = \$260,000\text{ MXN}$.

---

## 4. SAT 69-B as Contextual Evidence Only

Publication on the SAT Article 69-B EFOS list (Empresas que Facturan Operaciones Simuladas):
- **Contextual Evidence**: Suggests heightened scrutiny and supports lead prioritization.
- **Non-Gating / Non-Proof**: An EFOS listing alone is not legal or forensic proof that *this specific invoice* lacked material backing. The money trail must corroborate the absence of goods/services or circular return of funds.

---

## 5. Bounded Agent Constraints & Safety

- **Read-Only Tools**: The agent access layer is strictly read-only (`trace_outgoing_funds`, `inspect_counterparties`, `inspect_invoices`, `check_regulatory_status`, `calculate_exposure`).
- **No Raw SQL or Shell Access**: The agent cannot run custom database queries or system commands.
- **Step Cap**: Maximum of 10 investigation steps per thread to guarantee termination and budget containment.
- **Outage Fallback**: If Gemini or external networks are unavailable, TrueLock defaults to a deterministic investigation path, ensuring the demo never halts.
