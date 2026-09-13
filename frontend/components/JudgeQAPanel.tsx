"use client";

import React, { useState } from "react";
import { askQuestion } from "../lib/api";
import { canAskQuestion, formatEvidenceRefs } from "../lib/investigationUi.mjs";

interface Props {
  caseId: string | null;
}

export function JudgeQAPanel({ caseId }: Props) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [model, setModel] = useState<string | null>(null);
  const [evidenceRefs, setEvidenceRefs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canAskQuestion(caseId, question, loading)) return;

    setLoading(true);
    setAnswer(null);
    setEvidenceRefs([]);
    try {
      const res = await askQuestion(caseId as string, question);
      setAnswer(res.answer);
      setModel(res.model);
      setEvidenceRefs(res.evidence_refs || []);
    } catch (err: unknown) {
      setAnswer(`Error asking question: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ background: "#121824", padding: "1.25rem", borderRadius: "8px", border: "1px solid #232d42" }}>
      <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "1.1rem" }}>Judge & Auditor Q&A Assistant</h3>
      <p style={{ margin: "0 0 1rem 0", fontSize: "0.85rem", color: "#8b9bb4" }}>
        Directly interrogate the evidence collected for Case {caseId || "(None Selected)"}. Responses are grounded strictly on admissible case findings.
      </p>

      <form onSubmit={handleAsk} style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <input
          type="text"
          value={question}
          disabled={!caseId || loading}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={caseId ? "e.g. What evidence demonstrates circular movement?" : "Select a case first..."}
          style={{ flex: 1 }}
        />
        <button
          type="submit"
          disabled={!canAskQuestion(caseId, question, loading)}
          style={{
            padding: "8px 16px",
            background: "#3b82f6",
            color: "#fff",
            fontWeight: 600,
          }}
        >
          {loading ? "Asking Gemini..." : "Ask Auditor"}
        </button>
      </form>

      {answer && (
        <div style={{ padding: "1rem", background: "#0d131f", borderRadius: "6px", border: "1px solid #1f293d" }}>
          <div style={{ fontSize: "0.75rem", color: "#38bdf8", marginBottom: "0.4rem" }}>
            Response (Model: {model})
          </div>
          <p style={{ margin: "0 0 0.75rem 0", fontSize: "0.85rem", color: "#e2e8f0", lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
            {answer}
          </p>
          <p style={{ margin: 0, fontSize: "0.75rem", color: "#64748b" }}>
            {formatEvidenceRefs(evidenceRefs)}
          </p>
        </div>
      )}
    </div>
  );
}
