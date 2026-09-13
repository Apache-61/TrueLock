"""Tool declarations and dispatch for bounded forensic agent.

Tools are strictly read-only and operate on parameterized repository methods.
Gemini never gets raw SQL access or execution privileges.

Minimum executable surface (Hito A / Fase 2): five tools. The full fourteen-tool
catalogue remains deferred until this surface is proven under the state machine.
"""
from __future__ import annotations

import time
from typing import Any, Callable

from truelock.database.repositories.interfaces import (
    AccountRepository,
    EntityRepository,
    InvoiceRepository,
    PaymentRepository,
    ProviderRepository,
    TransactionRepository,
)

# Documented aliases only — normalized before schema validation and never
# forwarded to handlers.
_TRACE_ALIASES = {
    "account_no": "account_id",
    "max_hops": "max_depth",
    "depth": "max_depth",
}

TOOL_DEFINITIONS = [
    {
        "name": "trace_outgoing_funds",
        "description": (
            "Trace downstream bank transaction flow from a root account "
            "to identify rapid pass-through or circular returns."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "account_id": {
                    "type": "STRING",
                    "description": "Account number to trace outward from.",
                },
                "max_depth": {
                    "type": "INTEGER",
                    "description": "Maximum path hops (default 3, capped at 5).",
                },
            },
            "required": ["account_id"],
        },
    },
    {
        "name": "inspect_counterparties",
        "description": (
            "Retrieve legal identity, registration, entity type, and tax "
            "identifier (RFC) for counterparties."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "rfcs": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "List of RFCs to inspect.",
                },
            },
            "required": ["rfcs"],
        },
    },
    {
        "name": "inspect_invoices",
        "description": "Inspect CFDI 4.0 electronic invoices associated with providers.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "provider_rfc": {
                    "type": "STRING",
                    "description": "Provider RFC to query invoices for.",
                },
            },
            "required": ["provider_rfc"],
        },
    },
    {
        "name": "check_regulatory_status",
        "description": (
            "Check contextual tax status (SAT Art. 69-B EFOS publication). "
            "Note: Non-gating contextual evidence only."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "rfc": {
                    "type": "STRING",
                    "description": "RFC of the taxpayer to verify.",
                },
            },
            "required": ["rfc"],
        },
    },
    {
        "name": "calculate_exposure",
        "description": (
            "Calculate root-flow exposure without double-counting intermediate "
            "hops in the transfer graph."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "root_transaction_id": {
                    "type": "STRING",
                    "description": "ID of the root originating transaction.",
                },
                "returned_transaction_id": {
                    "type": "STRING",
                    "description": "ID of the return transaction if circular flow found.",
                },
            },
            "required": ["root_transaction_id"],
        },
    },
]

_TOOL_BY_NAME = {t["name"]: t for t in TOOL_DEFINITIONS}
ENVELOPE_KEYS = ("result", "provenance", "source_ids", "execution_time", "errors")


def make_envelope(
    *,
    result: Any,
    provenance: str,
    source_ids: list[str] | None = None,
    execution_time: float = 0.0,
    errors: str | None = None,
) -> dict[str, Any]:
    """Build the mandatory tool response envelope."""
    return {
        "result": result,
        "provenance": provenance,
        "source_ids": list(source_ids or []),
        "execution_time": round(float(execution_time), 6),
        "errors": errors,
    }


def normalize_tool_args(tool_name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    """Coerce documented aliases before schema validation; drop alias keys."""
    args = dict(arguments or {})
    if tool_name == "trace_outgoing_funds":
        for alias, canonical in _TRACE_ALIASES.items():
            if canonical not in args and alias in args:
                args[canonical] = args.pop(alias)
            elif alias in args:
                args.pop(alias)
    return args


def validate_tool_args(
    tool_name: str, arguments: dict[str, Any] | None
) -> tuple[dict[str, Any] | None, str | None]:
    """Validate and normalize arguments against TOOL_DEFINITIONS.

    Rejects unknown tools, undeclared keys, bad types, and invalid limits.
    Returns (normalized_args, error_message). On failure, normalized_args is None.
    """
    definition = _TOOL_BY_NAME.get(tool_name)
    if definition is None:
        return None, f"Tool '{tool_name}' is not in the authorized tool allowlist."

    args = normalize_tool_args(tool_name, arguments)
    params = definition.get("parameters", {})
    properties: dict[str, Any] = params.get("properties", {})
    required = params.get("required", [])

    undeclared = sorted(set(args.keys()) - set(properties.keys()))
    if undeclared:
        return (
            None,
            f"Undeclared argument(s) {undeclared} for tool '{tool_name}'.",
        )

    for key in required:
        if key not in args or args[key] in (None, "", []):
            return None, f"Missing required argument '{key}' for tool '{tool_name}'."

    for key, value in list(args.items()):
        expected = properties[key].get("type", "").upper()
        if expected == "STRING":
            if not isinstance(value, str):
                return None, f"Argument '{key}' must be a string for tool '{tool_name}'."
        elif expected == "INTEGER":
            if isinstance(value, bool) or not isinstance(value, int):
                try:
                    args[key] = int(value)
                except (TypeError, ValueError):
                    return None, f"Argument '{key}' must be an integer for tool '{tool_name}'."
        elif expected == "ARRAY":
            if not isinstance(value, list):
                return None, f"Argument '{key}' must be an array for tool '{tool_name}'."
            item_type = (properties[key].get("items") or {}).get("type", "").upper()
            if item_type == "STRING" and any(not isinstance(v, str) for v in value):
                return None, f"Argument '{key}' must be an array of strings for tool '{tool_name}'."

    if tool_name == "trace_outgoing_funds":
        depth = int(args.get("max_depth", 3))
        if depth < 1:
            return None, "max_depth must be at least 1."
        args["max_depth"] = min(depth, 5)

    return args, None


class ToolRegistry:
    """Dispatches tool calls safely to typed repositories."""

    def __init__(
        self,
        entities: EntityRepository,
        providers: ProviderRepository,
        accounts: AccountRepository,
        transactions: TransactionRepository,
        invoices: InvoiceRepository,
        payments: PaymentRepository,
    ) -> None:
        self.entities = entities
        self.providers = providers
        self.accounts = accounts
        self.transactions = transactions
        self.invoices = invoices
        self.payments = payments

    def execute(self, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Validate tool name/args against allowlist and execute with contract envelope."""
        started = time.perf_counter()
        args, error = validate_tool_args(tool_name, arguments)
        if error:
            return make_envelope(
                result=None,
                provenance="tool_registry.validation",
                source_ids=[],
                execution_time=time.perf_counter() - started,
                errors=error,
            )

        dispatch: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "trace_outgoing_funds": self._trace_outgoing_funds,
            "inspect_counterparties": self._inspect_counterparties,
            "inspect_invoices": self._inspect_invoices,
            "check_regulatory_status": self._check_regulatory_status,
            "calculate_exposure": self._calculate_exposure,
        }
        handler = dispatch.get(tool_name)
        if handler is None:
            return make_envelope(
                result=None,
                provenance="tool_registry.dispatch",
                execution_time=time.perf_counter() - started,
                errors=f"Tool '{tool_name}' is not in the authorized tool allowlist.",
            )
        try:
            payload = handler(args)  # type: ignore[arg-type]
            # Ensure envelope completeness even if a handler forgets a key.
            return make_envelope(
                result=payload.get("result"),
                provenance=payload.get("provenance") or f"tool_registry.{tool_name}",
                source_ids=payload.get("source_ids") or [],
                execution_time=time.perf_counter() - started,
                errors=payload.get("errors"),
            )
        except Exception as exc:
            return make_envelope(
                result=None,
                provenance=f"tool_registry.{tool_name}",
                source_ids=[],
                execution_time=time.perf_counter() - started,
                errors=f"Execution error in '{tool_name}': {exc}",
            )

    def _trace_outgoing_funds(self, args: dict[str, Any]) -> dict[str, Any]:
        account_id = args["account_id"]
        max_depth = int(args.get("max_depth", 3))

        visited_txs: list[dict[str, Any]] = []
        source_ids: list[str] = []
        seen_tx_ids: set[str] = set()
        queue = [(account_id, 0)]
        seen_accounts = {account_id}
        hops_walked = 0

        while queue:
            curr_acc, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            txs = self.transactions.list_outgoing(curr_acc)
            for tx in txs:
                if tx.id in seen_tx_ids:
                    continue
                seen_tx_ids.add(tx.id)
                visited_txs.append(tx.to_dict())
                source_ids.append(tx.id)
                hops_walked = max(hops_walked, depth + 1)
                if tx.to_account not in seen_accounts:
                    seen_accounts.add(tx.to_account)
                    queue.append((tx.to_account, depth + 1))

        return make_envelope(
            result={
                "root_account": account_id,
                "depth_limit": max_depth,
                "depth_reached": min(hops_walked, max_depth),
                "flow_count": len(visited_txs),
                "transactions": visited_txs,
            },
            provenance="TransactionRepository.list_outgoing",
            source_ids=source_ids,
        )

    def _inspect_counterparties(self, args: dict[str, Any]) -> dict[str, Any]:
        rfcs = args.get("rfcs", [])
        results = []
        source_ids: list[str] = []
        for rfc in rfcs:
            entity = self.entities.get_by_rfc(rfc)
            provider = self.providers.get(rfc)
            if entity:
                source_ids.append(entity.id)
            if provider:
                source_ids.append(provider.rfc)
            results.append(
                {
                    "rfc": rfc,
                    "entity": entity.to_dict() if entity else None,
                    "provider": provider.to_dict() if provider else None,
                }
            )
        return make_envelope(
            result={"counterparties": results},
            provenance="EntityRepository.get_by_rfc+ProviderRepository.get",
            source_ids=source_ids,
        )

    def _inspect_invoices(self, args: dict[str, Any]) -> dict[str, Any]:
        provider_rfc = args["provider_rfc"]
        invoices = self.invoices.list_by_provider(provider_rfc)
        return make_envelope(
            result={
                "provider_rfc": provider_rfc,
                "invoice_count": len(invoices),
                "invoices": [inv.to_dict() for inv in invoices],
            },
            provenance="InvoiceRepository.list_by_provider",
            source_ids=[inv.uuid for inv in invoices],
        )

    def _check_regulatory_status(self, args: dict[str, Any]) -> dict[str, Any]:
        rfc = args["rfc"]
        provider = self.providers.get(rfc)
        if not provider:
            return make_envelope(
                result={
                    "rfc": rfc,
                    "status": "UNKNOWN",
                    "note": "RFC not found in local provider registry",
                },
                provenance="ProviderRepository.get",
                source_ids=[],
            )
        return make_envelope(
            result={
                "rfc": rfc,
                "efos_status": provider.efos_status.value,
                "legal_name": provider.name,
                "note": (
                    "Contextual regulatory evidence only. "
                    "Does not constitute standalone proof of fraud."
                ),
            },
            provenance="ProviderRepository.get",
            source_ids=[provider.rfc],
        )

    def _calculate_exposure(self, args: dict[str, Any]) -> dict[str, Any]:
        root_tx_id = args["root_transaction_id"]
        returned_tx_id = args.get("returned_transaction_id")

        root_tx = self.transactions.get(root_tx_id)
        if not root_tx:
            return make_envelope(
                result=None,
                provenance="TransactionRepository.get",
                source_ids=[],
                errors=f"Root transaction {root_tx_id} not found",
            )

        root_amount = root_tx.amount
        returned_amount = 0.0
        source_ids = [root_tx.id]
        if returned_tx_id:
            ret_tx = self.transactions.get(returned_tx_id)
            if ret_tx:
                returned_amount = ret_tx.amount
                source_ids.append(ret_tx.id)

        return make_envelope(
            result={
                "root_transaction_id": root_tx_id,
                "root_amount": root_amount,
                "returned_amount": returned_amount,
                "supported_exposure": root_amount,
                "net_exposure": max(0.0, root_amount - returned_amount),
                "policy": "ROOT_FLOW_UNDUPLICATED_WITH_RETURN_OFFSET",
            },
            provenance="TransactionRepository.get+ROOT_FLOW_UNDUPLICATED_WITH_RETURN_OFFSET",
            source_ids=source_ids,
        )
