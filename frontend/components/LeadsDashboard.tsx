"use client";

import React from "react";
import { Lead } from "../types";

interface Props {
  leads: Lead[];
  selectedLeadId: string | null;
  onSelectLead: (leadId: string) => void;
  onInvestigate: (leadId: string) => void;
  isLoading: boolean;
}

export function LeadsDashboard({
  leads,
  selectedLeadId,
  onSelectLead,
  onInvestigate,
  isLoading,
}: Props) {
  return (
    <div style={{ background: "#121824", padding: "1.25rem", borderRadius: "8px", border: "1px solid #232d42" }}>
      <h3 style={{ margin: "0 0 1rem 0", fontSize: "1.1rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span>Prioritized Fraud Leads</span>
        <span style={{ fontSize: "0.85rem", color: "#8b9bb4" }}>{leads.length} Signals Scored</span>
      </h3>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        {leads.length === 0 && (
          <p style={{ margin: 0, fontSize: "0.85rem", color: "#8b9bb4" }}>
            No leads yet. Use <strong style={{ color: "#e2e8f0" }}>Load demo</strong> or upload a dataset
            under Add Dataset.
          </p>
        )}
        {leads.map((lead) => {
          const isHighRisk = lead.risk_score >= 0.7;
          const isSelected = selectedLeadId === lead.lead_id;

          return (
            <div
              key={lead.lead_id}
              onClick={() => onSelectLead(lead.lead_id)}
              style={{
                padding: "0.85rem",
                borderRadius: "6px",
                border: isSelected ? "1px solid #3b82f6" : "1px solid #1f293d",
                background: isSelected ? "#1b253b" : "#0d131f",
                cursor: "pointer",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
                <span style={{ fontWeight: 600, fontSize: "0.95rem" }}>{lead.detector_id}</span>
                <span
                  style={{
                    padding: "2px 8px",
                    borderRadius: "4px",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    background: isHighRisk ? "rgba(239, 68, 68, 0.2)" : "rgba(16, 185, 129, 0.2)",
                    color: isHighRisk ? "#ef4444" : "#10b981",
                  }}
                >
                  Risk: {(lead.risk_score * 100).toFixed(0)}%
                </span>
              </div>
              <p style={{ margin: "0 0 0.6rem 0", fontSize: "0.85rem", color: "#cbd5e1" }}>{lead.reason}</p>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "0.75rem", color: "#8b9bb4" }}>Status: {lead.status}</span>
                <button
                  disabled={isLoading}
                  onClick={(e) => {
                    e.stopPropagation();
                    onInvestigate(lead.lead_id);
                  }}
                  style={{
                    padding: "4px 12px",
                    background: "#3b82f6",
                    color: "#fff",
                    fontSize: "0.8rem",
                    borderRadius: "4px",
                  }}
                >
                  {isLoading && isSelected ? "Auditing..." : "Investigate Lead"}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
