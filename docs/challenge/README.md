# Challenge brief

**Status: incomplete.** The official Infosys "The Forensic Auditor"
challenge PDF was not available during the research/bootstrap phase. What
follows is the working requirement set derived from the team's own
planning context, not the official scoring document.

## Working requirement summary

The system must:

1. Find possible fraud signals.
2. Investigate those signals.
3. Follow relationships between invoices, suppliers, payments, and
   companies.
4. Follow the money.
5. Build a chain of evidence.
6. Justify why it followed particular leads.
7. Determine when there is enough evidence to sustain an accusation.
8. Reject an accusation when the evidence is insufficient.
9. Generate a final case file a human auditor can understand.
10. Answer questions about the reasoning it used.

It must handle previously unseen records, and the demo must let judges
introduce or hide a new fraud pattern in the data and watch the agent find
and follow it. Final output must include: the fraud scheme, providers
involved, evidence chain, monetary amount involved, and discarded leads
with the reason they weren't pursued.

Data sources mentioned by the challenge: SAT Article 69-B / EFOS, CFDI
4.0, IBM AMLSim, public financial-fraud datasets, ledger/invoice/bank
records, supplier lists.

## Before freezing anything against this brief

- [ ] Obtain the official challenge PDF and reconcile every requirement
      above against it — especially anything scoring-specific.
- [ ] Record any discrepancies in `docs/decisions.md` if it changes something already
      built.
