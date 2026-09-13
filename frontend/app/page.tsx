"use client";

import React, { useEffect, useState } from "react";
import { CaseFile, Evidence, InvestigationDetails, InvestigationStep, Lead } from "../types";
import { fetchHealth, fetchLeads, startInvestigation } from "../lib/api";
import { LeadsDashboard } from "../components/LeadsDashboard";
import { InvestigationTimeline } from "../components/InvestigationTimeline";
import { MoneyTrailGraph } from "../components/MoneyTrailGraph";
import { EvidencePanel } from "../components/EvidencePanel";
import { CaseFileView } from "../components/CaseFileView";
import { JudgeQAPanel } from "../components/JudgeQAPanel";

export default function Home() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [investigation, setInvestigation] = useState<InvestigationDetails | null>(null);
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState<{ status: string; gemini: { status: string; model: string } } | null>(null);

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: "offline", gemini: { status: "unreachable", model: "unknown" } }));

    fetchLeads()
      .then((data) => {
        setLeads(data);
        if (data.length > 0) setSelectedLeadId(data[0].lead_id);
      })
      .catch((err) => console.error("Could not load leads:", err));
  }, []);

  const handleInvestigate = async (leadId: string) => {
    setLoading(true);
    try {
      const details = await startInvestigation(leadId);
      setInvestigation(details);
      // Refresh leads to show updated status
      const updatedLeads = await fetchLeads();
      setLeads(updatedLeads);
    } catch (err) {
      console.error("Investigation failed:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: "1400px", margin: "0 auto", padding: "1.5rem" }}>
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: "1px solid #232d42",
          paddingBottom: "1rem",
          marginBottom: "1.5rem",
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: "1.5rem", color: "#38bdf8", fontWeight: 700 }}>
            TrueLock <span style={{ color: "#94a3b8", fontWeight: 400 }}>| Forensic Auditor</span>
          </h1>
          <p style={{ margin: "0.2rem 0 0 0", fontSize: "0.85rem", color: "#64748b" }}>
            Autonomous forensic intelligence for corporate fraud, rapid pass-through, and round-trip detection
          </p>
        </div>
        <div style={{ display: "flex", gap: "1rem", fontSize: "0.8rem", color: "#94a3b8" }}>
          <div>
            API: <span style={{ color: health?.status === "ok" ? "#10b981" : "#ef4444" }}>● {health?.status || "connecting"}</span>
          </div>
          <div>
            Gemini: <span style={{ color: health?.gemini.status === "connected" ? "#10b981" : "#f59e0b" }}>● {health?.gemini.model || "fallback"}</span>
          </div>
        </div>
      </header>

      {/* Money Trail Visualization Banner */}
      <div style={{ marginBottom: "1.5rem" }}>
        <MoneyTrailGraph caseId={investigation?.case.case_id || null} />
      </div>

      {/* Main Grid: Leads on Left, Investigation & Findings on Right */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.6fr", gap: "1.5rem" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <LeadsDashboard
            leads={leads}
            selectedLeadId={selectedLeadId}
            onSelectLead={setSelectedLeadId}
            onInvestigate={handleInvestigate}
            isLoading={loading}
          />
          <JudgeQAPanel caseId={investigation?.case.case_id || null} />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <CaseFileView caseFile={investigation?.case || null} />
          <InvestigationTimeline steps={investigation?.steps || []} />
          <EvidencePanel evidence={investigation?.evidence || []} />
        </div>
      </div>
    </div>
  );
}
