"use client";

import React, { useEffect, useMemo, useState } from "react";
import { fetchMoneyTrail } from "../lib/api";

type Trail = Awaited<ReturnType<typeof fetchMoneyTrail>>;

type LayoutNode = {
  entity_id: string;
  canonical_name: string;
  entity_type: string;
  x: number;
  y: number;
};

function layoutNodes(nodes: Trail["nodes"], width: number, height: number): LayoutNode[] {
  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.min(width, height) * 0.34;
  if (nodes.length === 0) return [];
  if (nodes.length === 1) {
    return [{ ...nodes[0], x: cx, y: cy }];
  }
  return nodes.map((node, index) => {
    const angle = (Math.PI * 2 * index) / nodes.length - Math.PI / 2;
    return {
      ...node,
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
    };
  });
}

function shorten(label: string, max = 22): string {
  if (label.length <= max) return label;
  return `${label.slice(0, max - 1)}…`;
}

export function MoneyTrailGraph({ caseId }: { caseId: string | null }) {
  const [trail, setTrail] = useState<Trail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const width = 720;
  const height = 420;

  useEffect(() => {
    if (!caseId) {
      setTrail(null);
      return;
    }
    fetchMoneyTrail(caseId)
      .then((value) => {
        setTrail(value);
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Money trail unavailable"));
  }, [caseId]);

  const positions = useMemo(
    () => (trail ? layoutNodes(trail.nodes, width, height) : []),
    [trail]
  );
  const byId = useMemo(
    () => Object.fromEntries(positions.map((node) => [node.entity_id, node])),
    [positions]
  );

  return (
    <div style={{ background: "#121824", padding: "1.25rem", borderRadius: "8px", border: "1px solid #232d42" }}>
      <h3 style={{ margin: "0 0 1rem 0", fontSize: "1.1rem" }}>Money Trail Subgraph (Circular Fund Flow)</h3>
      {!caseId && <p style={{ color: "#94a3b8", margin: 0 }}>Select a persisted investigation to load its financial graph.</p>}
      {error && <p style={{ color: "#ef4444", margin: 0 }}>{error}</p>}
      {trail && (
        <div style={{ display: "grid", gap: "0.85rem" }}>
          <svg
            viewBox={`0 0 ${width} ${height}`}
            width="100%"
            role="img"
            aria-label="Money trail graph"
            style={{ background: "#0d131f", borderRadius: "8px", border: "1px solid #1f2a3f" }}
          >
            <defs>
              <marker id="trail-arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
                <path d="M0,0 L8,3 L0,6 Z" fill="#7dd3fc" />
              </marker>
            </defs>
            {trail.edges.map((edge) => {
              const origin = byId[edge.origin_entity_id];
              const dest = byId[edge.destination_entity_id];
              if (!origin || !dest) return null;
              const mx = (origin.x + dest.x) / 2;
              const my = (origin.y + dest.y) / 2 - 24;
              return (
                <g key={edge.bank_transaction_id}>
                  <path
                    d={`M ${origin.x} ${origin.y} Q ${mx} ${my} ${dest.x} ${dest.y}`}
                    fill="none"
                    stroke="#38bdf8"
                    strokeWidth="2"
                    markerEnd="url(#trail-arrow)"
                    opacity={0.85}
                  />
                  <title>
                    {edge.component_type}: {edge.traced_amount_mxn.toLocaleString("es-MX", { style: "currency", currency: "MXN" })}
                  </title>
                </g>
              );
            })}
            {positions.map((node) => (
              <g key={node.entity_id} transform={`translate(${node.x}, ${node.y})`}>
                <circle r="28" fill="#1a2438" stroke="#5eead4" strokeWidth="2" />
                <text textAnchor="middle" dy="4" fill="#e2e8f0" fontSize="11" fontFamily="IBM Plex Sans, Segoe UI, sans-serif">
                  {shorten(node.canonical_name, 14)}
                </text>
                <title>{`${node.canonical_name} (${node.entity_type})`}</title>
              </g>
            ))}
          </svg>
          <div style={{ display: "grid", gap: "0.5rem" }}>
            {trail.edges.map((edge) => (
              <div key={edge.bank_transaction_id} style={{ color: "#cbd5e1", fontSize: "0.9rem" }}>
                <strong>{edge.component_type}</strong>:{" "}
                {edge.traced_amount_mxn.toLocaleString("es-MX", { style: "currency", currency: "MXN" })}
                <span style={{ color: "#64748b" }}> · {new Date(edge.booked_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
