"use client";

import React, { useState } from "react";
import { importDataset } from "../lib/api";

interface Props {
  onImported: () => void;
}

type DatasetKind = "cfdi" | "bank" | "efos";

export function DatasetUploadPanel({ onImported }: Props) {
  const [kind, setKind] = useState<DatasetKind>("bank");
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleUpload = async () => {
    if (!file) {
      setStatus("Choose a file first (see data/fixtures/ for samples).");
      return;
    }
    setLoading(true);
    setStatus(null);
    try {
      const report = await importDataset(kind, file);
      const rejectionHint =
        report.rejected > 0
          ? ` Rejected ${report.rejected}: ${report.rejections
              .slice(0, 3)
              .map((item) => item.reason)
              .join("; ")}`
          : "";
      setStatus(
        report.reused_prior_import
          ? `Same file already imported (dedup). Accepted ${report.accepted}.${rejectionHint}`
          : `Imported ${kind}: accepted ${report.accepted}, deduplicated ${report.deduplicated}.${rejectionHint}`
      );
      onImported();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Import failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ background: "#121824", padding: "1.25rem", borderRadius: "8px", border: "1px solid #0ea5e955" }}>
      <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "1.1rem", color: "#7dd3fc" }}>Add Dataset</h3>
      <p style={{ margin: "0 0 1rem 0", fontSize: "0.85rem", color: "#8b9bb4" }}>
        Upload CFDI XML, bank CSV, or SAT 69-B (EFOS) CSV. To smoke-test uploads use{" "}
        <code style={{ color: "#cbd5e1" }}>data/fixtures/bank/valid_cycle.csv</code> (Bank),{" "}
        <code style={{ color: "#cbd5e1" }}>data/fixtures/cfdi/valid_invoice.xml</code> (CFDI), or{" "}
        <code style={{ color: "#cbd5e1" }}>data/fixtures/efos/valid_69b.csv</code> (EFOS). For fraud leads,
        prefer <strong style={{ color: "#e2e8f0" }}>Load demo</strong>.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginBottom: "0.75rem" }}>
        <select
          value={kind}
          onChange={(e) => setKind(e.target.value as DatasetKind)}
          disabled={loading}
          style={{ padding: "8px", background: "#0d131f", color: "#e2e8f0", border: "1px solid #232d42", borderRadius: "4px" }}
        >
          <option value="bank">Bank CSV</option>
          <option value="cfdi">CFDI XML</option>
          <option value="efos">EFOS / SAT 69-B CSV</option>
        </select>
        <input
          type="file"
          accept={kind === "cfdi" ? ".xml,text/xml,application/xml" : ".csv,text/csv"}
          disabled={loading}
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          style={{ fontSize: "0.85rem", color: "#cbd5e1" }}
        />
        <button
          type="button"
          disabled={loading || !file}
          onClick={handleUpload}
          style={{
            padding: "8px 16px",
            background: loading || !file ? "#334155" : "#0284c7",
            color: "#fff",
            fontWeight: 600,
            borderRadius: "4px",
            border: "none",
            cursor: loading || !file ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "Uploading..." : "Upload dataset"}
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
