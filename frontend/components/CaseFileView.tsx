"use client";

import React from "react";
import { CaseFile } from "../types";

interface Props {
  caseFile: CaseFile | null;
}

export function CaseFileView({ caseFile }: Props) {
  if (!caseFile) {
    return (
      <div style={{ background: "#121824", padding: "1.25rem", borderRadius: "8px", border: "1px solid #232d42" }}>
        <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "1.1rem" }}>Audited Case File</h3>
        <p style={{ color: "#8b9bb4", fontSize: "0.85rem" }}>Complete an investigation to generate a substantiated case file.</p>
      </div>
    );
  }

  const isSubstantiated = caseFile.status === "SUBSTANTIATED";

  return (
    <div style={{ background: "#121824", padding: "1.25rem", borderRadius: "8px", border: "1px solid #232d42" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <h3 style={{ margin: 0, fontSize: "1.1rem" }}>Case File: {caseFile.case_id}</h3>
        <span
          style={{
            padding: "4px 10px",
            borderRadius: "4px",
            fontSize: "0.8rem",
            fontWeight: 700,
            background: isSubstantiated ? "rgba(239, 68, 68, 0.2)" : "rgba(16, 185, 129, 0.2)",
            color: isSubstantiated ? "#ef4444" : "#10b981",
          }}
        >
          {caseFile.status}
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", fontSize: "0.85rem" }}>
        <div>
          <strong style={{ color: "#94a3b8" }}>Hypothesis:</strong>
          <p style={{ margin: "0.2rem 0 0 0", color: "#f8fafc" }}>{caseFile.hypothesis}</p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          <div>
            <strong style={{ color: "#94a3b8" }}>Supported Exposure:</strong>
            <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "#ef4444" }}>
              ${caseFile.amount_involved.toLocaleString()} MXN
            </div>
          </div>
          <div>
            <strong style={{ color: "#94a3b8" }}>Confidence Level:</strong>
            <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "#38bdf8" }}>
              {caseFile.confidence_level}
            </div>
          </div>
        </div>

        <div>
          <strong style={{ color: "#94a3b8" }}>Statutory & Forensic Citations:</strong>
          <p style={{ margin: "0.2rem 0 0 0", color: "#cbd5e1" }}>{caseFile.citations.join(", ")}</p>
        </div>

        <div>
          <strong style={{ color: "#94a3b8" }}>Limitations & Caveats:</strong>
          <ul style={{ margin: "0.2rem 0 0 0", paddingLeft: "1.2rem", color: "#94a3b8" }}>
            {caseFile.limitations.map((lim, i) => (
              <li key={i}>{lim}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
