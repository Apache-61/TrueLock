"use client";

import React from "react";
import { InvestigationStep } from "../types";

interface Props {
  steps: InvestigationStep[];
}

export function InvestigationTimeline({ steps }: Props) {
  if (!steps || steps.length === 0) {
    return (
      <div style={{ background: "#121824", padding: "1.25rem", borderRadius: "8px", border: "1px solid #232d42" }}>
        <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "1.1rem" }}>What the Auditor Did</h3>
        <p style={{ color: "#8b9bb4", fontSize: "0.85rem" }}>Select a lead and click "Investigate Lead" to trace actions.</p>
      </div>
    );
  }

  return (
    <div style={{ background: "#121824", padding: "1.25rem", borderRadius: "8px", border: "1px solid #232d42" }}>
      <h3 style={{ margin: "0 0 1rem 0", fontSize: "1.1rem" }}>What the Auditor Did (Investigation Steps)</h3>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        {steps.map((step, idx) => (
          <div
            key={step.step_id}
            style={{
              padding: "0.85rem",
              borderRadius: "6px",
              background: "#0d131f",
              border: "1px solid #1f293d",
              position: "relative",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.3rem" }}>
              <span style={{ fontWeight: 600, color: "#38bdf8", fontSize: "0.9rem" }}>
                Step {idx + 1}: {step.action}
              </span>
              <span
                style={{
                  fontSize: "0.75rem",
                  padding: "2px 6px",
                  borderRadius: "4px",
                  background: step.decision === "CONCLUDE" ? "rgba(16, 185, 129, 0.2)" : "rgba(59, 130, 246, 0.2)",
                  color: step.decision === "CONCLUDE" ? "#10b981" : "#3b82f6",
                }}
              >
                {step.decision}
              </span>
            </div>
            <p style={{ margin: "0 0 0.4rem 0", fontSize: "0.82rem", color: "#94a3b8" }}>
              <strong>Tool:</strong> <code>{step.tool}</code> | <strong>Inputs:</strong> {JSON.stringify(step.inputs)}
            </p>
            {step.result_refs && step.result_refs.length > 0 && (
              <p style={{ margin: 0, fontSize: "0.75rem", color: "#64748b" }}>
                <strong>Provenance:</strong> {step.result_refs.join(", ")}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
