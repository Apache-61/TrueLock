"""Provider routing and spend accounting for the development workers.

Scope note: this MVP registers exactly one provider (the Claude Code
CLI). The routing *machinery* -- selection, `ROUTING_EVENT` logging,
usage ledger -- is real and tested, so adding Gemini later is a
registration, not a rewrite. Multi-provider routing itself is
deliberately deferred: the end-to-end loop
(TASK -> CLAIM -> BRANCH -> CLAUDE -> TEST -> HISTORY -> PR) has to work
first.
"""

from .ledger import LedgerEntry, UsageLedger
from .router import ProviderRouter, RoutingEvent, Provider

__all__ = ["LedgerEntry", "UsageLedger", "ProviderRouter", "RoutingEvent", "Provider"]
