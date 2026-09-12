# ADR-0004: Solana / ElevenLabs / Snowflake / MongoDB scope

**Status:** Accepted
**Date:** 2026-09-12
**Deciders:** bootstrap pass, per team planning context + Research &
Development Operating Pack §44, §45, §54

## Context

Sponsor technologies are available and can add judging value, but must
never displace time from the critical path (`ARCHITECTURE.md` §12). Each
must justify itself: what problem it solves, what it costs, what risk it
introduces, whether it improves the score.

## Decision

| Tech | Scope | Rationale |
|---|---|---|
| **Solana** | Optional. Hash the finalized case file (SHA-256) and anchor it in a devnet memo transaction, purely for tamper-evidence. No fraud logic on-chain. | Solves notarization/integrity, nothing else — it does not solve fraud detection, graph analysis, entity resolution, or reasoning. Bounded to `evidence/notarization` behind a feature flag. |
| **ElevenLabs** | Optional, wired last. Reads the final case conclusion aloud. | Accessibility/presentation value only; non-core, zero risk to the core loop if cut. |
| **Snowflake** | Not used unless a concrete, compelling data-processing need appears. | No volume or analytical need at hackathon scale; no team experience; would only cost time. |
| **MongoDB** | Not used. Case files are stored as `JSONB` in PostgreSQL instead. | Avoids running a second database for a "semi-structured documents" need that PostgreSQL's JSONB already covers. |

Both Solana and ElevenLabs are explicitly listed as "only if time remains"
in `research/rejected-ideas/README.md`'s time-sink classification, and are
implemented behind flags so cutting them never breaks the demo path.

## Consequences

Every sponsor integration attempted is additive and revertible; none of
them are on the path from "detector fires" to "case file exists." If time
runs out before Solana/ElevenLabs are wired, the demo is unaffected.

## Reversibility

Fully reversible — each is an isolated, flaggable module
(`evidence/notarization/`, a single narration call in the case-file
renderer) with no other module depending on it.
