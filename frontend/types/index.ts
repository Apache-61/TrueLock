export type Outcome = "SUPPORTED" | "REJECTED" | "INSUFFICIENT_EVIDENCE";

export interface Lead {
  lead_id: string;
  entity_id: string;
  detector_id: string;
  reason: string;
  risk_score: number;
  signals: string[];
  status: "OPEN" | "FOLLOWED" | "DISCARDED";
  discard_reason?: string | null;
}

export interface InvestigationStep {
  step_id: string;
  lead_id: string;
  action: string;
  tool: string;
  reason: string;
  inputs: Record<string, unknown>;
  result_refs: string[];
  decision: "FOLLOW" | "DISCARD" | "ESCALATE" | "CONCLUDE";
  next_action?: string | null;
}

export interface Evidence {
  evidence_id: string;
  type: "TRANSACTION" | "INVOICE" | "REGULATORY_STATUS" | "RELATIONSHIP" | "DOCUMENT";
  source_type: string;
  source_id: string;
  claim: string;
  strength: "DIRECT" | "CORROBORATING" | "CIRCUMSTANTIAL";
  gathered_by_step_id?: string | null;
  record_hash?: string | null;
}

export interface CaseFile {
  case_id: string;
  status: "SUBSTANTIATED" | "UNSUBSTANTIATED" | "INSUFFICIENT_EVIDENCE";
  hypothesis: string;
  providers_involved: string[];
  amount_involved: number;
  supporting_evidence: string[];
  discarded_leads: Array<{ lead_id: string; reason: string }>;
  confidence_level: "LOW" | "MEDIUM" | "HIGH";
  limitations: string[];
  citations: string[];
  generated_at?: string;
  evidence_hash?: string | null;
}

export interface InvestigationDetails {
  case: CaseFile;
  steps: InvestigationStep[];
  evidence: Evidence[];
}
