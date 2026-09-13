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

export async function fetchMoneyTrail(caseId: string): Promise<{
  case_id: string;
  nodes: Array<{ entity_id: string; canonical_name: string; entity_type: string; rfc?: string }>;
  edges: Array<{
    bank_transaction_id: string;
    component_type: string;
    traced_amount_mxn: number;
    origin_entity_id: string;
    destination_entity_id: string;
    booked_at: string;
  }>;
}> {
  const res = await fetch(`${API_BASE}/api/graph/${caseId}`);
  if (!res.ok) throw new Error(`Failed fetching money trail: ${res.statusText}`);
  return res.json();
}

export async function askQuestion(
  caseId: string,
  question: string
): Promise<{
  case_id: string;
  question: string;
  answer: string;
  model: string;
  evidence_refs?: string[];
  investigation_step_ids?: string[];
}> {
  const res = await fetch(`${API_BASE}/api/cases/${caseId}/questions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error(`Failed asking question: ${res.statusText}`);
  return res.json();
}

export async function fetchInjectionScenarios(): Promise<Array<{ scenario_id: string; description: string }>> {
  const res = await fetch(`${API_BASE}/api/demo/scenarios`);
  if (!res.ok) throw new Error(`Failed fetching injection scenarios: ${res.statusText}`);
  return res.json();
}

export async function injectFraudScenario(scenarioId: string): Promise<{
  scenario_id: string;
  entity_id: string;
  lead_id: string | null;
  message: string;
}> {
  const res = await fetch(`${API_BASE}/demo/inject-fraud`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_id: scenarioId }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || res.statusText);
  }
  return res.json();
}

export async function fetchInvestigationEvents(caseId: string, offset = 0): Promise<
  Array<{ timestamp: string; case_id: string; message: string; step_id?: string | null; event_type?: string }>
> {
  const res = await fetch(`${API_BASE}/api/events?case_id=${encodeURIComponent(caseId)}&offset=${offset}`);
  if (!res.ok) throw new Error(`Failed fetching events: ${res.statusText}`);
  return res.json();
}

export async function importDataset(
  kind: "cfdi" | "bank" | "efos",
  file: File
): Promise<{
  accepted: number;
  rejected: number;
  deduplicated: number;
  reused_prior_import: boolean;
  rejections: Array<{ locator: string; reason: string; error_code: string }>;
}> {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(`${API_BASE}/api/imports/${kind}`, { method: "POST", body });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || res.statusText);
  }
  return res.json();
}

export async function clearAnalysis(removeInjections = true): Promise<{
  status: string;
  message: string;
  lead_count?: number;
  mode?: string;
}> {
  const res = await fetch(`${API_BASE}/api/demo/clear-analysis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ remove_injections: removeInjections }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || res.statusText);
  }
  return res.json();
}

export async function loadDemo(): Promise<{
  status: string;
  message: string;
  lead_count?: number;
  mode?: string;
}> {
  const res = await fetch(`${API_BASE}/api/demo/load-demo`, { method: "POST" });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || res.statusText);
  }
  return res.json();
}
