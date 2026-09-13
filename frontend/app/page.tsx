"use client";

import React, { useEffect, useState } from "react";
import { InvestigationDetails, Lead } from "../types";
import { fetchHealth, fetchLeads, startInvestigation, fetchInvestigationEvents } from "../lib/api";
import { LeadsDashboard } from "../components/LeadsDashboard";
import { InvestigationTimeline } from "../components/InvestigationTimeline";
import { MoneyTrailGraph } from "../components/MoneyTrailGraph";
import { EvidencePanel } from "../components/EvidencePanel";
import { CaseFileView } from "../components/CaseFileView";
import { JudgeQAPanel } from "../components/JudgeQAPanel";
import { JudgeInjectPanel } from "../components/JudgeInjectPanel";
import { DatasetUploadPanel } from "../components/DatasetUploadPanel";
import { DiscardedLeadsPanel } from "../components/DiscardedLeadsPanel";

export default function Home() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [investigation, setInvestigation] = useState<InvestigationDetails | null>(null);
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState<{ status: string; gemini: { status: string; model: string } } | null>(null);
  const [liveEvents, setLiveEvents] = useState<Array<{ timestamp: string; message: string }>>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: "offline", gemini: { status: "unreachable", model: "unknown" } }));

    fetchLeads()
      .then((data) => {
        setLeads(data);
        if (data.length > 0) setSelectedLeadId(data[0].lead_id);
        setError(null);
      })
      .catch((err) => {
        setError(`Could not load leads: ${err instanceof Error ? err.message : String(err)}`);
      });
  }, []);

  const handleInvestigate = async (leadId: string) => {
    setLoading(true);
    setError(null);
    setLiveEvents([
      {
        timestamp: new Date().toISOString(),
        message: `Opening investigation for lead ${leadId}...`,
      },
    ]);

    const pendingKey = `PENDING-${leadId}`;
    const pollId = window.setInterval(() => {
      fetchInvestigationEvents(pendingKey)
        .then((events) => {
          if (events.length > 0) {
            setLiveEvents(
              events.map((event) => ({ timestamp: event.timestamp, message: event.message }))
            );
          }
        })
        .catch(() => {
          /* keep last known events while request is in flight */
        });
    }, 400);

    try {
      const details = await startInvestigation(leadId);
      setInvestigation(details);
      const updatedLeads = await fetchLeads();
      setLeads(updatedLeads);
      if (details.case?.case_id) {
        const events = await fetchInvestigationEvents(details.case.case_id);
        setLiveEvents(events.map((event) => ({ timestamp: event.timestamp, message: event.message })));
      }
    } catch (err) {
      setError(`Investigation failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      window.clearInterval(pollId);
      setLoading(false);
    }
  };

  useEffect(() => {
    const caseId = investigation?.case?.case_id;
    if (!caseId) return;
    let ticks = 0;
    const id = window.setInterval(() => {
      ticks += 1;
      fetchInvestigationEvents(caseId)
        .then((events) => {
          setLiveEvents(events.map((event) => ({ timestamp: event.timestamp, message: event.message })));
        })
        .catch(() => undefined);
      if (ticks >= 15) window.clearInterval(id);
    }, 2000);
    return () => window.clearInterval(id);
  }, [investigation?.case?.case_id]);

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
        <div style={{ display: "flex", gap: "1rem", fontSize: "0.8rem", color: "#94a3b8", alignItems: "center" }}>
          <a href="/docs" style={{ color: "#5eead4", textDecoration: "none", fontWeight: 600 }}>
            Docs
          </a>
          <div>
            API: <span style={{ color: health?.status === "ok" ? "#10b981" : "#ef4444" }}>● {health?.status || "connecting"}</span>
          </div>
          <div>
            Gemini: <span style={{ color: health?.gemini.status === "connected" ? "#10b981" : "#f59e0b" }}>● {health?.gemini.model || "fallback"}</span>
          </div>
        </div>
      </header>

      {error && (
        <div
          role="alert"
          style={{
            marginBottom: "1rem",
            padding: "0.85rem 1rem",
            borderRadius: "8px",
            border: "1px solid #7f1d1d",
            background: "#1f1215",
            color: "#fca5a5",
            fontSize: "0.9rem",
          }}
        >
          {error}
        </div>
      )}

      <div style={{ marginBottom: "1.5rem" }}>
        <MoneyTrailGraph caseId={investigation?.case.case_id || null} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.6fr", gap: "1.5rem" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <LeadsDashboard
            leads={leads}
            selectedLeadId={selectedLeadId}
            onSelectLead={setSelectedLeadId}
            onInvestigate={handleInvestigate}
            isLoading={loading}
          />
          <JudgeInjectPanel
            onInjected={async () => {
              try {
                const updatedLeads = await fetchLeads();
                setLeads(updatedLeads);
                setInvestigation(null);
                setLiveEvents([]);
                setError(null);
              } catch (err) {
                setError(`Inject refresh failed: ${err instanceof Error ? err.message : String(err)}`);
              }
            }}
            onCleared={async () => {
              try {
                setLeads([]);
                setSelectedLeadId(null);
                setInvestigation(null);
                setLiveEvents([]);
                setError(null);
              } catch (err) {
                setError(`Clear refresh failed: ${err instanceof Error ? err.message : String(err)}`);
              }
            }}
            onDemoLoaded={async () => {
              try {
                const updatedLeads = await fetchLeads();
                setLeads(updatedLeads);
                setSelectedLeadId(updatedLeads[0]?.lead_id || null);
                setInvestigation(null);
                setLiveEvents([]);
                setError(null);
              } catch (err) {
                setError(`Load demo failed: ${err instanceof Error ? err.message : String(err)}`);
              }
            }}
          />
          <DatasetUploadPanel
            onImported={async () => {
              try {
                const updatedLeads = await fetchLeads();
                setLeads(updatedLeads);
                setError(null);
              } catch (err) {
                setError(`Import refresh failed: ${err instanceof Error ? err.message : String(err)}`);
              }
            }}
          />
          <JudgeQAPanel caseId={investigation?.case.case_id || null} />
          <DiscardedLeadsPanel discarded={investigation?.case.discarded_leads || []} />
          {liveEvents.length > 0 && (
            <div style={{ background: "#121824", padding: "1.25rem", borderRadius: "8px", border: "1px solid #232d42" }}>
              <h3 style={{ margin: "0 0 0.75rem 0", fontSize: "1.1rem" }}>Live Investigation Events</h3>
              {liveEvents.map((event, index) => (
                <div key={`${event.timestamp}-${index}`} style={{ fontSize: "0.8rem", color: "#94a3b8", marginBottom: "0.35rem" }}>
                  <span style={{ color: "#64748b" }}>{new Date(event.timestamp).toLocaleTimeString()}</span> — {event.message}
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <InvestigationTimeline steps={investigation?.steps || []} />
          <EvidencePanel evidence={investigation?.evidence || []} />
          <CaseFileView caseFile={investigation?.case || null} />
        </div>
      </div>
    </div>
  );
}
