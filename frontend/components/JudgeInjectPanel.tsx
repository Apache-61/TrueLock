"use client";

import React, { useEffect, useState } from "react";
import { clearAnalysis, fetchInjectionScenarios, injectFraudScenario, loadDemo } from "../lib/api";

interface Props {
  onInjected: () => void;
  onCleared: () => void;
  onDemoLoaded: () => void;
}

export function JudgeInjectPanel({ onInjected, onCleared, onDemoLoaded }: Props) {
  const [scenarios, setScenarios] = useState<Array<{ scenario_id: string; description: string }>>([]);
  const [selected, setSelected] = useState("hidden_pass_through");
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [loadingDemo, setLoadingDemo] = useState(false);

  useEffect(() => {
    fetchInjectionScenarios()
      .then(setScenarios)
      .catch(() =>
        setScenarios([
          { scenario_id: "hidden_pass_through", description: "Opaque vendor rapid pass-through" },
          { scenario_id: "hidden_duplicate_payment", description: "Duplicate root invoice payment" },
        ])
      );
  }, []);

  const busy = loading || clearing || loadingDemo;

  const handleInject = async () => {
    setLoading(true);
    setStatus(null);
    try {
      const result = await injectFraudScenario(selected);
      setStatus(
        `Injected ${result.scenario_id}. New lead candidate: ${result.lead_id || "run detectors"}`
      );
      onInjected();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Injection failed");
    } finally {
      setLoading(false);
    }
  };

  const handleClear = async () => {
    setClearing(true);
    setStatus(null);
    try {
      const result = await clearAnalysis(true);
      setStatus(result.message || "Workspace cleared.");
      onCleared();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Clear failed");
    } finally {
      setClearing(false);
    }
  };

  const handleLoadDemo = async () => {
    setLoadingDemo(true);
    setStatus(null);
    try {
      const result = await loadDemo();
      setStatus(result.message || "Demo loaded.");
      onDemoLoaded();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Load demo failed");
    } finally {
      setLoadingDemo(false);
    }
  };

  return (
    <div style={{ background: "#121824", padding: "1.25rem", borderRadius: "8px", border: "1px solid #7c3aed55" }}>
      <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "1.1rem", color: "#c4b5fd" }}>Judge: Demo Controls</h3>
      <p style={{ margin: "0 0 1rem 0", fontSize: "0.85rem", color: "#8b9bb4" }}>
        Leads stay empty until you <strong style={{ color: "#e2e8f0" }}>Load demo</strong> or upload a dataset.
        Inject adds a hidden fraud pattern on top of loaded data. Clear empties everything again.
      </p>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem", flexWrap: "wrap" }}>
        <button
          type="button"
          disabled={busy}
          onClick={handleLoadDemo}
          style={{ padding: "8px 16px", background: "#0f766e", color: "#fff", fontWeight: 600, borderRadius: "4px", border: "none" }}
        >
          {loadingDemo ? "Loading..." : "Load demo"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={handleClear}
          title="Wipe threads, evidence, imports and leads"
          style={{ padding: "8px 16px", background: "#334155", color: "#e2e8f0", fontWeight: 600, borderRadius: "4px", border: "1px solid #64748b" }}
        >
          {clearing ? "Clearing..." : "Clear workspace"}
        </button>
      </div>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem", flexWrap: "wrap" }}>
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          disabled={busy}
          style={{ flex: 1, minWidth: "12rem", padding: "8px", background: "#0d131f", color: "#e2e8f0", border: "1px solid #232d42", borderRadius: "4px" }}
        >
          {scenarios.map((scenario) => (
            <option key={scenario.scenario_id} value={scenario.scenario_id}>
              {scenario.scenario_id}
            </option>
          ))}
        </select>
        <button
          type="button"
          disabled={busy}
          onClick={handleInject}
          style={{ padding: "8px 16px", background: "#7c3aed", color: "#fff", fontWeight: 600, borderRadius: "4px", border: "none" }}
        >
          {loading ? "Injecting..." : "Inject"}
        </button>
      </div>
      {status && (
        <p style={{ margin: 0, fontSize: "0.8rem", color: "#cbd5e1", whiteSpace: "pre-wrap" }}>
          {status}
        </p>
      )}
    </div>
  );
}
