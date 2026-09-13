"""Tool declarations and dispatch for bounded forensic agent.

Tools are strictly read-only and operate on parameterized repository methods.
Gemini never gets raw SQL access or execution privileges.
"""
from __future__ import annotations

from typing import Any, Callable

from truelock.database.repositories.interfaces import (
    AccountRepository,
    EntityRepository,
    InvoiceRepository,
    PaymentRepository,
    ProviderRepository,
    TransactionRepository,
)

TOOL_DEFINITIONS = [
    {
        "name": "trace_outgoing_funds",
        "description": "Trace downstream bank transaction flow from a root account or transaction to identify rapid pass-through or circular returns.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "account_id": {"type": "STRING", "description": "Account number to trace outward from."},
                "max_depth": {"type": "INTEGER", "description": "Maximum path hops (default 3, capped at 5)."},
            },
            "required": ["account_id"],
        },
    },
    {
        "name": "inspect_counterparties",
        "description": "Retrieve legal identity, registration, entity type, and tax identifier (RFC) for counterparties.",
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
        "description": "Inspect CFDI 4.0 electronic invoices associated with transactions or providers.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "provider_rfc": {"type": "STRING", "description": "Provider RFC to query invoices for."},
            },
            "required": ["provider_rfc"],
        },
    },
    {
        "name": "check_regulatory_status",
        "description": "Check contextual tax status (SAT Art. 69-B EFOS publication). Note: Non-gating contextual evidence only.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "rfc": {"type": "STRING", "description": "RFC of the taxpayer to verify."},
            },
            "required": ["rfc"],
        },
    },
    {
        "name": "calculate_exposure",
        "description": "Calculate root-flow exposure without double-counting intermediate hops in the transfer graph.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "root_transaction_id": {"type": "STRING", "description": "ID of the root originating transaction."},
                "returned_transaction_id": {"type": "STRING", "description": "ID of the return transaction if circular flow found."},
            },
            "required": ["root_transaction_id"],
        },
    },
]


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

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Validate tool name against allowlist and execute."""
        dispatch: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "trace_outgoing_funds": self._trace_outgoing_funds,
            "inspect_counterparties": self._inspect_counterparties,
            "inspect_invoices": self._inspect_invoices,
            "check_regulatory_status": self._check_regulatory_status,
            "calculate_exposure": self._calculate_exposure,
        }
        handler = dispatch.get(tool_name)
        if not handler:
            return {"error": f"Tool '{tool_name}' is not in the authorized tool allowlist."}
        try:
            return handler(arguments)
        except Exception as exc:
            return {"error": f"Execution error in '{tool_name}': {exc}"}

    def _trace_outgoing_funds(self, args: dict[str, Any]) -> dict[str, Any]:
        account_id = args.get("account_id", "")
        max_depth = min(int(args.get("max_depth", 3)), 5)

        visited_txs = []
        queue = [(account_id, 0)]
        seen_accounts = {account_id}

        while queue:
            curr_acc, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            txs = self.transactions.list_outgoing(curr_acc)
            for tx in txs:
                visited_txs.append(tx.to_dict())
                if tx.to_account not in seen_accounts:
                    seen_accounts.add(tx.to_account)
                    queue.append((tx.to_account, depth + 1))

        return {
            "root_account": account_id,
            "depth_reached": max_depth,
            "flow_count": len(visited_txs),
            "transactions": visited_txs,
        }

    def _inspect_counterparties(self, args: dict[str, Any]) -> dict[str, Any]:
        rfcs = args.get("rfcs", [])
        results = []
        for rfc in rfcs:
            entity = self.entities.get_by_rfc(rfc)
            provider = self.providers.get(rfc)
            results.append({
                "rfc": rfc,
                "entity": entity.to_dict() if entity else None,
                "provider": provider.to_dict() if provider else None,
            })
        return {"counterparties": results}

    def _inspect_invoices(self, args: dict[str, Any]) -> dict[str, Any]:
        provider_rfc = args.get("provider_rfc", "")
        invoices = self.invoices.list_by_provider(provider_rfc)
        return {
            "provider_rfc": provider_rfc,
            "invoice_count": len(invoices),
            "invoices": [inv.to_dict() for inv in invoices],
        }

    def _check_regulatory_status(self, args: dict[str, Any]) -> dict[str, Any]:
        rfc = args.get("rfc", "")
        provider = self.providers.get(rfc)
        if not provider:
            return {"rfc": rfc, "status": "UNKNOWN", "note": "RFC not found in local provider registry"}
        return {
            "rfc": rfc,
            "efos_status": provider.efos_status.value,
            "legal_name": provider.legal_name,
            "note": "Contextual regulatory evidence only. Does not constitute standalone proof of fraud.",
        }

    def _calculate_exposure(self, args: dict[str, Any]) -> dict[str, Any]:
        root_tx_id = args.get("root_transaction_id", "")
        returned_tx_id = args.get("returned_transaction_id")

        root_tx = self.transactions.get(root_tx_id)
        if not root_tx:
            return {"error": f"Root transaction {root_tx_id} not found"}

        root_amount = root_tx.amount
        returned_amount = 0.0
        if returned_tx_id:
            ret_tx = self.transactions.get(returned_tx_id)
            if ret_tx:
                returned_amount = ret_tx.amount

        # Policy: Supported exposure = root originating payment. Net exposure = root - returned
        return {
            "root_transaction_id": root_tx_id,
            "root_amount": root_amount,
            "returned_amount": returned_amount,
            "supported_exposure": root_amount,
            "net_exposure": max(0.0, root_amount - returned_amount),
            "policy": "ROOT_FLOW_UNDUPLICATED",
        }
