"use client";

import React from "react";
import { Evidence } from "../types";

interface Props {
  evidence: Evidence[];
}

export function EvidencePanel({ evidence }: Props) {
  if (!evidence || evidence.length === 0) {
    return (
      <div style={{ background: "#121824", padding: "1.25rem", borderRadius: "8px", border: "1px solid #232d42" }}>
        <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "1.1rem" }}>Evidence & Provenance Chain</h3>
        <p style={{ color: "#8b9bb4", fontSize: "0.85rem" }}>No evidence gathered yet. Execute an investigation to record evidence.</p>
      </div>
    );
  }

  return (
    <div style={{ background: "#121824", padding: "1.25rem", borderRadius: "8px", border: "1px solid #232d42" }}>
      <h3 style={{ margin: "0 0 1rem 0", fontSize: "1.1rem", display: "flex", justifyContent: "space-between" }}>
        <span>Evidence & Provenance Chain</span>
        <span style={{ fontSize: "0.85rem", color: "#8b9bb4" }}>{evidence.length} Admissible Records</span>
      </h3>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
        {evidence.map((ev) => (
          <div
            key={ev.evidence_id}
            style={{
              padding: "0.75rem",
              borderRadius: "6px",
              background: "#0d131f",
              border: "1px solid #1f293d",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.2rem" }}>
              <span style={{ fontWeight: 600, fontSize: "0.85rem", color: "#f1f5f9" }}>
                [{ev.evidence_id}] {ev.type}
              </span>
              <span
                style={{
                  fontSize: "0.7rem",
                  padding: "1px 6px",
                  borderRadius: "3px",
                  background: ev.strength === "DIRECT" ? "rgba(239, 68, 68, 0.2)" : "rgba(245, 158, 11, 0.2)",
                  color: ev.strength === "DIRECT" ? "#ef4444" : "#f59e0b",
                }}
              >
                {ev.strength}
              </span>
            </div>
            <p style={{ margin: "0 0 0.3rem 0", fontSize: "0.8rem", color: "#94a3b8" }}>{ev.claim}</p>
            <div style={{ fontSize: "0.7rem", color: "#64748b" }}>
              <span>Source: <code>{ev.source_type}</code></span>
              {ev.record_hash && <span> | Hash: <code>{ev.record_hash}</code></span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
