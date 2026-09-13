"use client";

import React from "react";

export function MoneyTrailGraph() {
  return (
    <div style={{ background: "#121824", padding: "1.25rem", borderRadius: "8px", border: "1px solid #232d42" }}>
      <h3 style={{ margin: "0 0 1rem 0", fontSize: "1.1rem" }}>Money Trail Subgraph (Circular Fund Flow)</h3>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "1.5rem",
          background: "#0d131f",
          borderRadius: "6px",
          border: "1px dashed #2d3b55",
          textAlign: "center",
          gap: "1rem",
        }}
      >
        <div style={{ flex: 1, padding: "1rem", background: "#1a2438", borderRadius: "8px", border: "1px solid #2a3b5c" }}>
          <div style={{ fontSize: "0.8rem", color: "#94a3b8" }}>Originating Company</div>
          <div style={{ fontWeight: 700, fontSize: "0.95rem", color: "#38bdf8" }}>Empresa Operadora Nacional</div>
          <div style={{ fontSize: "0.75rem", color: "#64748b" }}>Acc: ...0001 (BBVA)</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
          <span style={{ fontSize: "0.75rem", color: "#ef4444", fontWeight: 700 }}>$1,000,000 MXN</span>
          <span style={{ fontSize: "1.2rem", color: "#ef4444" }}>&rarr;</span>
          <span style={{ fontSize: "0.7rem", color: "#64748b" }}>Root Invoice PMT</span>
        </div>

        <div style={{ flex: 1, padding: "1rem", background: "#1a2438", borderRadius: "8px", border: "1px solid #2a3b5c" }}>
          <div style={{ fontSize: "0.8rem", color: "#94a3b8" }}>Primary Vendor</div>
          <div style={{ fontWeight: 700, fontSize: "0.95rem", color: "#f59e0b" }}>Constructora Primaria</div>
          <div style={{ fontSize: "0.75rem", color: "#64748b" }}>Acc: ...0002 (BBVA)</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
          <span style={{ fontSize: "0.75rem", color: "#f59e0b", fontWeight: 700 }}>$920,000 MXN</span>
          <span style={{ fontSize: "1.2rem", color: "#f59e0b" }}>&rarr;</span>
          <span style={{ fontSize: "0.7rem", color: "#64748b" }}>Pass-Through (&lt;2h)</span>
        </div>

        <div style={{ flex: 1, padding: "1rem", background: "#1a2438", borderRadius: "8px", border: "1px solid #2a3b5c" }}>
          <div style={{ fontSize: "0.8rem", color: "#ef4444" }}>Intermediary / Shell</div>
          <div style={{ fontWeight: 700, fontSize: "0.95rem", color: "#ef4444" }}>Logística Fantasma</div>
          <div style={{ fontSize: "0.75rem", color: "#64748b" }}>SAT 69-B: DEFINITIVO</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
          <span style={{ fontSize: "0.75rem", color: "#10b981", fontWeight: 700 }}>$740,000 MXN</span>
          <span style={{ fontSize: "1.2rem", color: "#10b981" }}>&#8634;</span>
          <span style={{ fontSize: "0.7rem", color: "#64748b" }}>Return to Origin</span>
        </div>
      </div>
      <div style={{ marginTop: "1rem", display: "flex", gap: "2rem", justifyContent: "center", fontSize: "0.85rem" }}>
        <div><strong style={{ color: "#94a3b8" }}>Root Exposure:</strong> <span style={{ color: "#ef4444", fontWeight: 700 }}>$1,000,000 MXN</span></div>
        <div><strong style={{ color: "#94a3b8" }}>Verified Returned:</strong> <span style={{ color: "#10b981", fontWeight: 700 }}>$740,000 MXN</span></div>
        <div><strong style={{ color: "#94a3b8" }}>Net Unrecovered:</strong> <span style={{ color: "#f59e0b", fontWeight: 700 }}>$260,000 MXN</span></div>
      </div>
    </div>
  );
}
