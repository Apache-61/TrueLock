"""Which provider handles a call, and why -- logged, never silent.

`orchestrator/policies/provider-pool.yaml` states the rule this module
implements: "Every switch must be logged as ROUTING_EVENT { from, to,
reason } so spend stays auditable. Never switch silently."

The pool file is read with PyYAML when it is installed and with a small
targeted reader when it is not. Adding a dependency is a decision that
needs human sign-off (CONTRIBUTING.md 5), and a worker whose ability to
start depends on an un-agreed package is a worker that cannot be relied
on for the first run on a new machine.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_POLICY_PATH = Path("orchestrator/policies/provider-pool.yaml")


@dataclass(frozen=True)
class Provider:
    """One authorized provider/project the team already has budget for."""

    id: str
    provider: str
    key_env: str = ""
    max_session_budget_usd: float = 0.0


@dataclass(frozen=True)
class RoutingEvent:
    """A provider selection or switch, in the audit format."""

    from_provider: str
    to_provider: str
    reason: str

    def render(self) -> str:
        return (
            f"ROUTING_EVENT from={self.from_provider or 'none'} "
            f"to={self.to_provider} reason={self.reason}"
        )


def parse_provider_pool(text: str) -> dict:
    """Read the provider pool file.

    Uses PyYAML when available. The fallback understands exactly the
    subset this one file uses -- a `providers:` list of flat mappings
    plus top-level scalars -- and is intentionally narrow: a parser that
    quietly mis-reads a budget limit is more dangerous than one that
    handles less.
    """
    try:
        import yaml  # type: ignore[import-untyped]

        loaded = yaml.safe_load(text)
        if isinstance(loaded, dict):
            return loaded
    except ImportError:
        pass
    return _parse_minimal_yaml(text)


def _coerce(value: str) -> object:
    value = value.strip().strip('"').strip("'")
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def _parse_minimal_yaml(text: str) -> dict:
    result: dict = {}
    providers: list[dict] = []
    current: dict | None = None
    in_providers = False

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip() if not raw_line.strip().startswith("#") else ""
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()

        if indent == 0 and stripped.rstrip(":") == "providers":
            in_providers = True
            current = None
            continue
        if indent == 0 and ":" in stripped:
            in_providers = False
            current = None
            key, _, value = stripped.partition(":")
            if value.strip():
                result[key.strip()] = _coerce(value)
            continue
        if in_providers and stripped.startswith("- "):
            current = {}
            providers.append(current)
            stripped = stripped[2:].strip()
        if current is not None and ":" in stripped:
            key, _, value = stripped.partition(":")
            current[key.strip()] = _coerce(value)

    if providers:
        result["providers"] = providers
    return result


@dataclass
class ProviderRouter:
    """Selects a provider and records every decision.

    `select()` logs a `ROUTING_EVENT` on *every* call, not only on a
    switch, so the log answers "who served this task?" without the reader
    having to replay earlier events to infer the current provider.
    """

    providers: list[Provider] = field(default_factory=list)
    hard_budget_stop_usd: float = 0.0
    events: list[RoutingEvent] = field(default_factory=list)
    current: str = ""
    _log: object = None

    @classmethod
    def from_policy(cls, path: Path | str = DEFAULT_POLICY_PATH, *, logger=None) -> "ProviderRouter":
        policy_path = Path(path)
        data: dict = {}
        if policy_path.is_file():
            data = parse_provider_pool(policy_path.read_text(encoding="utf-8")) or {}
        providers = [
            Provider(
                id=str(entry.get("id", "")),
                provider=str(entry.get("provider", "")),
                key_env=str(entry.get("key_env", "")),
                max_session_budget_usd=float(entry.get("max_session_budget_usd", 0) or 0),
            )
            for entry in data.get("providers", [])
            if entry.get("id")
        ]
        return cls(
            providers=providers,
            hard_budget_stop_usd=float(data.get("hard_budget_stop_usd", 0) or 0),
            _log=logger,
        )

    def register(self, provider: Provider) -> Provider:
        """Add a provider that is not in the pool file.

        The Claude Code CLI is registered this way: it is authenticated
        per workstation rather than by a pooled API key, so it has no row
        in `provider-pool.yaml`, which describes the Gemini key pool.
        """
        if not any(existing.id == provider.id for existing in self.providers):
            self.providers.append(provider)
        return provider

    def get(self, provider_id: str) -> Provider | None:
        for provider in self.providers:
            if provider.id == provider_id:
                return provider
        return None

    def select(self, provider_id: str, *, reason: str) -> Provider:
        """Choose a provider, logging the decision."""
        provider = self.get(provider_id)
        if provider is None:
            raise KeyError(
                f"provider {provider_id!r} is not in the authorized pool "
                f"({', '.join(p.id for p in self.providers) or 'empty'}). This "
                "router only ever selects providers the team already has "
                "budget for -- see orchestrator/policies/provider-pool.yaml."
            )
        event = RoutingEvent(from_provider=self.current, to_provider=provider_id, reason=reason)
        self.events.append(event)
        if self._log is not None:
            self._log(event.render())  # type: ignore[operator]
        self.current = provider_id
        return provider

    def budget_exceeded(self, spent_usd: float) -> bool:
        return bool(self.hard_budget_stop_usd) and spent_usd >= self.hard_budget_stop_usd
