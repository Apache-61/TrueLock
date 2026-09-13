"use client";

import React from "react";

interface Props {
  discarded: Array<{ lead_id: string; reason: string }>;
}

export function DiscardedLeadsPanel({ discarded }: Props) {
  if (!discarded.length) {
    return (
      <div style={{ background: "#121824", padding: "1.25rem", borderRadius: "8px", border: "1px solid #232d42" }}>
        <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "1.1rem" }}>Discarded Leads</h3>
        <p style={{ margin: 0, fontSize: "0.85rem", color: "#8b9bb4" }}>
          When the auditor rejects a hypothesis, the discard reason appears here.
        </p>
      </div>
    );
  }

  return (
    <div style={{ background: "#121824", padding: "1.25rem", borderRadius: "8px", border: "1px solid #232d42" }}>
      <h3 style={{ margin: "0 0 1rem 0", fontSize: "1.1rem" }}>Discarded Leads ({discarded.length})</h3>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
        {discarded.map((item) => (
          <div
            key={item.lead_id}
            style={{ padding: "0.75rem", borderRadius: "6px", background: "#0d131f", border: "1px solid #1f293d" }}
          >
            <div style={{ fontWeight: 600, fontSize: "0.85rem", color: "#10b981", marginBottom: "0.25rem" }}>
              {item.lead_id}
            </div>
            <p style={{ margin: 0, fontSize: "0.8rem", color: "#94a3b8" }}>{item.reason}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
