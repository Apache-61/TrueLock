"""Multi-project Gemini provider router with budget and failover."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from truelock.agent.usage_ledger import UsageEntry, UsageLedger, new_request_id, utc_now

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CONFIG = ROOT / "config" / "agent-providers.json"

RoutingListener = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class ProviderEndpoint:
    id: str
    provider: str
    key_env: str
    max_session_budget_usd: float
    fallback_env: str | None = None

    def resolve_api_key(self) -> str:
        key = os.getenv(self.key_env, "").strip()
        if key:
            return key
        if self.fallback_env:
            return os.getenv(self.fallback_env, "").strip()
        return ""


class ProviderRouter:
    """Select among authorized Gemini projects; never exceed hard budget."""

    def __init__(
        self,
        *,
        config_path: Path | None = None,
        ledger: UsageLedger | None = None,
        on_routing_event: RoutingListener | None = None,
    ) -> None:
        self.config_path = config_path or DEFAULT_CONFIG
        self.ledger = ledger or UsageLedger()
        self.on_routing_event = on_routing_event
        self._config = self._load_config(self.config_path)
        self._providers = [
            ProviderEndpoint(
                id=item["id"],
                provider=item.get("provider", "google"),
                key_env=item["key_env"],
                max_session_budget_usd=float(item.get("max_session_budget_usd", 75)),
                fallback_env=item.get("fallback_env"),
            )
            for item in self._config.get("providers", [])
        ]
        self.hard_budget_stop_usd = float(self._config.get("hard_budget_stop_usd", 280))
        self.estimated_cost_per_call_usd = float(
            self._config.get("estimated_cost_per_call_usd", 0.002)
        )
        self._failed: set[str] = set()
        self._active_id: str | None = None

    @staticmethod
    def _load_config(path: Path) -> dict[str, Any]:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        # Safe defaults when config is missing in slim containers
        return {
            "providers": [
                {
                    "id": "gemini-default",
                    "provider": "google",
                    "key_env": "GEMINI_API_KEY",
                    "max_session_budget_usd": 75,
                }
            ],
            "hard_budget_stop_usd": 280,
            "estimated_cost_per_call_usd": 0.002,
        }

    @property
    def active_provider_id(self) -> str | None:
        return self._active_id

    def budget_exhausted(self) -> bool:
        return self.ledger.total_spend_usd() >= self.hard_budget_stop_usd

    def remaining_budget_usd(self) -> float:
        return max(0.0, self.hard_budget_stop_usd - self.ledger.total_spend_usd())

    def configured_providers(self) -> list[ProviderEndpoint]:
        return [p for p in self._providers if p.resolve_api_key()]

    def select_provider(self) -> ProviderEndpoint | None:
        if self.budget_exhausted():
            self._emit_routing(
                frm=self._active_id,
                to=None,
                reason="hard_budget_stop",
            )
            return None

        spend = self.ledger.spend_by_project()
        candidates = []
        for provider in self._providers:
            if provider.id in self._failed:
                continue
            if not provider.resolve_api_key():
                continue
            used = spend.get(provider.id, 0.0)
            if used >= provider.max_session_budget_usd:
                continue
            candidates.append((used, provider.id, provider))

        if not candidates:
            self._emit_routing(
                frm=self._active_id,
                to=None,
                reason="no_healthy_authorized_provider",
            )
            return None

        candidates.sort(key=lambda item: (item[0], item[1]))
        chosen = candidates[0][2]
        if self._active_id and self._active_id != chosen.id:
            self._emit_routing(
                frm=self._active_id,
                to=chosen.id,
                reason="failover_or_rebalance",
            )
        elif self._active_id is None:
            self._emit_routing(frm=None, to=chosen.id, reason="initial_select")
        self._active_id = chosen.id
        return chosen

    def mark_failure(self, provider_id: str, *, reason: str) -> ProviderEndpoint | None:
        self._failed.add(provider_id)
        self._emit_routing(frm=provider_id, to=None, reason=reason)
        nxt = self.select_provider()
        if nxt:
            self._emit_routing(frm=provider_id, to=nxt.id, reason=reason)
        return nxt

    def record_success(
        self,
        provider: ProviderEndpoint,
        *,
        model: str,
        status: str = "ok",
        error: str | None = None,
        estimated_cost: float | None = None,
    ) -> UsageEntry:
        cost = (
            self.estimated_cost_per_call_usd
            if estimated_cost is None and status == "ok"
            else estimated_cost
        )
        return self.ledger.record(
            UsageEntry(
                provider=provider.provider,
                project=provider.id,
                model=model,
                request_id=new_request_id(),
                timestamp=utc_now(),
                status=status,
                estimated_cost=cost,
                error=error,
            )
        )

    def status(self) -> dict[str, Any]:
        return {
            "active_provider": self._active_id,
            "hard_budget_stop_usd": self.hard_budget_stop_usd,
            "remaining_budget_usd": self.remaining_budget_usd(),
            "configured_providers": [p.id for p in self.configured_providers()],
            "failed_providers": sorted(self._failed),
            "ledger": self.ledger.snapshot(),
        }

    def _emit_routing(self, *, frm: str | None, to: str | None, reason: str) -> None:
        event = {
            "event_type": "ROUTING_EVENT",
            "from": frm,
            "to": to,
            "reason": reason,
            "timestamp": utc_now(),
        }
        logger.info("ROUTING_EVENT %s", event)
        if self.on_routing_event:
            self.on_routing_event(event)
