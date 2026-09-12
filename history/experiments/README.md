# Experiment board

Tracks time-boxed spikes run to validate a risky assumption before
committing engineering time to it. Copied from the Research & Development
Operating Pack's experiment board (§47) as the starting set — update
statuses as experiments actually run.

| Experiment | Hypothesis | Action | Max time | GO signal | NO-GO signal | If NO-GO | Status |
|---|---|---|---:|---|---|---|---|
| Gemini tools | Model can use typed tools reliably | Wire 3 mock tools, run 10 calls | 20m | Valid structured calls | Malformed/hallucinated args | Freeze a stricter schema, retry with lower temperature | Not run |
| PostgreSQL | Plain SQL is enough for demo scale | Load a fixture dataset, run the planned queries | 20m | Acceptable latency | Slow on realistic joins | Add indexes / reduce scope | Not run |
| NetworkX | Graph ops are fast enough | Run path/cycle/fan-in-out on the synthetic graph | 15m | Fast (<1s typical) | Slow | Limit subgraph size before traversal | Not run |
| Cytoscape.js | Graph is readable in the UI | Render 50-200 nodes | 20m | Readable | Visual clutter | Add filtering/clustering | Not run |
| AMLSim | Scenarios are reproducible fixtures | Generate 3 known patterns | 30m | Repeatable output | Setup failure | Fall back to hand-built fixtures | Not run |
| RAG | Local retrieval over the regulatory corpus is sufficient | Answer 10 known regulatory questions | 20m | Reliable | Weak/wrong answers | Fall back to keyword search over static docs | Not run |
| Orchestrator | AI-to-AI handoff can be automated | Run 2 workers through claim → task → handoff | 45m | Handoff works end to end | Too much coordination friction | Simplify to manual claim-by-comment | Not run |
| Provider router | Legitimate failover works safely | Simulate a 429 and a budget threshold | 30m | Router switches correctly, logs `ROUTING_EVENT` | Router leaves inconsistent state | Harden the policy before relying on it live | Not run |

Add a row for any new risky assumption before spending more than ~30
minutes building on top of it unverified.
