# detection/graph/

**Purpose:** NetworkX-based graph construction and analysis over the
canonical entity graph (`docs/contracts/domain.md` → graph edges), used by
both graph detectors (`FAN_IN`, `FAN_OUT`, `CIRCULAR_FLOW`) and, later,
the agent's graph-traversal tools (`docs/contracts/agent-tools.md`).

**What goes here:** graph-building from canonical entities, and the
traversal/cycle/degree operations listed in
`research/graph/README.md` §Operations needed. Bound every traversal
(depth/hop limits) — see `docs/investigation/protocol.md` §Termination
guarantees.

**What does not go here:** detector-specific thresholding (→
`detection/scoring/`), UI rendering (→ `frontend/`, using Cytoscape.js).

**Depends on:** `domain/entities/`, `research/graph/README.md`.
