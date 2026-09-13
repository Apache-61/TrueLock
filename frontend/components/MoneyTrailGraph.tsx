"use client";

import React, { useEffect, useState } from "react";
import { fetchMoneyTrail } from "../lib/api";

type Trail = Awaited<ReturnType<typeof fetchMoneyTrail>>;

export function MoneyTrailGraph({ caseId }: { caseId: string | null }) {
  const [trail, setTrail] = useState<Trail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) {
      setTrail(null);
      return;
    }
    fetchMoneyTrail(caseId)
      .then((value) => {
        setTrail(value);
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Money trail unavailable"));
  }, [caseId]);

  return (
    <div style={{ background: "#121824", padding: "1.25rem", borderRadius: "8px", border: "1px solid #232d42" }}>
      <h3 style={{ margin: "0 0 1rem 0", fontSize: "1.1rem" }}>Money Trail Subgraph (Circular Fund Flow)</h3>
      {!caseId && <p style={{ color: "#94a3b8", margin: 0 }}>Select a persisted investigation to load its financial graph.</p>}
      {error && <p style={{ color: "#ef4444", margin: 0 }}>{error}</p>}
      {trail && (
        <div style={{ display: "grid", gap: "0.75rem" }}>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            {trail.nodes.map((node) => (
              <span key={node.entity_id} style={{ background: "#1a2438", border: "1px solid #2a3b5c", borderRadius: "6px", padding: "0.5rem", color: "#e2e8f0" }}>
                {node.canonical_name}
              </span>
            ))}
          </div>
          {trail.edges.map((edge) => (
            <div key={edge.bank_transaction_id} style={{ background: "#0d131f", borderRadius: "6px", padding: "0.75rem", color: "#cbd5e1" }}>
              <strong>{edge.component_type}</strong>: {edge.traced_amount_mxn.toLocaleString("es-MX", { style: "currency", currency: "MXN" })}
              <span style={{ color: "#64748b" }}> · {new Date(edge.booked_at).toLocaleString()}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
