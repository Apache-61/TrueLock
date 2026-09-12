# orchestrator/routing/

**Purpose:** implements the routing algorithm documented in
`orchestrator/policies/provider-pool.yaml` — which provider/project/model
handles a given call, with legitimate failover (never quota
circumvention, see `research/ai/README.md` and the operating pack §14).

**Not yet built.** Needed once `orchestrator/workers/` exists and makes
real API calls. Until then, each worker manually picks a configured
provider.

**Depends on:** `orchestrator/policies/provider-pool.yaml`,
`orchestrator/policies/usage-ledger.schema.json`.
