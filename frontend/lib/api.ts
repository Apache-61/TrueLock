import { CaseFile, InvestigationDetails, Lead } from "../types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchHealth(): Promise<{ status: string; gemini: { status: string; model: string } }> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`);
  return res.json();
}

export async function fetchLeads(): Promise<Lead[]> {
  const res = await fetch(`${API_BASE}/api/leads`);
  if (!res.ok) throw new Error(`Failed fetching leads: ${res.statusText}`);
  return res.json();
}

export async function startInvestigation(leadId: string): Promise<InvestigationDetails> {
  const res = await fetch(`${API_BASE}/api/investigations/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lead_id: leadId }),
  });
  if (!res.ok) throw new Error(`Failed starting investigation: ${res.statusText}`);
  return res.json();
}

export async function fetchInvestigation(caseId: string): Promise<InvestigationDetails> {
  const res = await fetch(`${API_BASE}/api/investigations/${caseId}`);
  if (!res.ok) throw new Error(`Failed fetching investigation: ${res.statusText}`);
  return res.json();
}

export async function askQuestion(
  caseId: string,
  question: string
): Promise<{ case_id: string; question: string; answer: string; model: string }> {
  const res = await fetch(`${API_BASE}/api/cases/${caseId}/questions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error(`Failed asking question: ${res.statusText}`);
  return res.json();
}
