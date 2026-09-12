# Decision records (ADRs)

Full records for every entry in the root `DECISIONS.md` index. One file per
decision, numbered sequentially, never renumbered or deleted — a superseded
decision gets a new ADR that says "supersedes ADR-000X" and the old one is
marked `Superseded` (not removed).

## Template

```markdown
# ADR-XXXX: <short title>

**Status:** Proposed | Accepted | Superseded by ADR-YYYY | Rejected
**Date:** YYYY-MM-DD
**Deciders:** <names/handles>

## Context
What problem forced this decision? What constraints applied (31-hour
budget, team skills, sponsor requirements)?

## Options considered
| Option | Pros | Cons |
|---|---|---|

## Decision
What we chose, in one paragraph.

## Consequences
What this makes easier, what it makes harder, what it forecloses.

## Reversibility
How expensive would it be to reverse this later?
```

Link every ADR from the task/PR that implements it, and from any module
README whose "depends on" section references the decision.
